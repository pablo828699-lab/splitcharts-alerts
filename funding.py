"""
funding.py
==========

Tasa de funding de los perpetuos, con degradacion elegante.

El funding es el dato que decide DONDE se expresa una posicion larga: si los
largos estan pagando caro, la misma exposicion sale mas barata en spot. Por eso
el tablero lo trata como un semaforo de instrumento, no como un adorno.

Calibracion (Binance, USDT-M):
    El valor POR DEFECTO de Binance es 0,01% cada 8h (~11% anual) cuando el
    premium es cero. NO es un techo: es el punto neutro. Leerlo como "extremo"
    es el error clasico.

        <= 0          los cortos pagan          -> el mejor momento para perps largos
        0 .. 0,01%    normal (default)          -> indistinto
        0,01 .. 0,03% largos amontonandose      -> preferir spot
        > 0,03%       caro (>33% anual)         -> no abrir largos en perps
        > 0,05%       extremo (>55% anual)      -> evaluar cash & carry

Fuentes, en orden. Si una falla se prueba la siguiente; si fallan todas se
devuelve None y el tablero lo muestra como "sin dato" en lugar de romperse.
Binance geobloquea fapi en parte de los runners, de ahi que Bybit sea el
respaldo y no al reves.
"""

from __future__ import annotations

import certs_bootstrap  # noqa: F401

from typing import Dict, Optional

import requests

TIMEOUT = 12

# Umbrales en fraccion por intervalo de 8h.
NEUTRAL = 0.0001      # 0,01% -> default de Binance
CROWDED = 0.0003      # 0,03% -> ~33% anual
EXTREME = 0.0005      # 0,05% -> ~55% anual

_BINANCE = "https://fapi.binance.com/fapi/v1/premiumIndex"
_BYBIT = "https://api.bybit.com/v5/market/tickers"


def _from_binance(symbol: str) -> Optional[float]:
    r = requests.get(_BINANCE, params={"symbol": symbol}, timeout=TIMEOUT)
    r.raise_for_status()
    return float(r.json()["lastFundingRate"])


def _from_bybit(symbol: str) -> Optional[float]:
    r = requests.get(_BYBIT, params={"category": "linear", "symbol": symbol},
                     timeout=TIMEOUT)
    r.raise_for_status()
    lst = r.json().get("result", {}).get("list") or []
    if not lst:
        return None
    return float(lst[0]["fundingRate"])


def fetch_funding(symbol: str) -> Optional[float]:
    """Funding actual (fraccion por 8h) o None si ninguna fuente responde."""
    for name, fn in (("binance", _from_binance), ("bybit", _from_bybit)):
        try:
            v = fn(symbol)
            if v is not None:
                return v
        except Exception as exc:
            print(f"  funding {symbol} via {name} falló: {exc}")
    return None


def annualized(rate: float) -> float:
    """De fraccion por 8h a porcentaje anual (3 cobros por dia)."""
    return rate * 3 * 365 * 100.0


def classify(rate: Optional[float]) -> Dict[str, str]:
    """Semaforo de instrumento a partir del funding."""
    if rate is None:
        return {"nivel": "sin_dato", "instrumento": "spot",
                "texto": "Sin dato de funding: por defecto, spot."}
    if rate <= 0:
        return {"nivel": "negativo", "instrumento": "perp",
                "texto": "Los cortos pagan. Es el momento más barato para un largo apalancado."}
    if rate <= NEUTRAL:
        return {"nivel": "normal", "instrumento": "indistinto",
                "texto": "Funding en zona neutra. Spot o perp, según el setup."}
    if rate <= CROWDED:
        return {"nivel": "cargado", "instrumento": "spot",
                "texto": "Los largos se amontonan. Preferir spot para exposición nueva."}
    if rate <= EXTREME:
        return {"nivel": "caro", "instrumento": "spot",
                "texto": "Caro para estar largo en perp. No abrir largos apalancados."}
    return {"nivel": "extremo", "instrumento": "cash_carry",
            "texto": "Funding extremo: evaluar largo spot + corto perp y ajustar stops."}


def snapshot(symbols) -> Dict[str, dict]:
    """Funding + clasificacion para cada simbolo pedido."""
    out = {}
    for s in symbols:
        rate = fetch_funding(s)
        row = {"rate_8h": rate,
               "anual_pct": round(annualized(rate), 1) if rate is not None else None}
        row.update(classify(rate))
        out[s] = row
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(snapshot(["BTCUSDT", "ETHUSDT", "SOLUSDT"]), indent=2, ensure_ascii=False))
