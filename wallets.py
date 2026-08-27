"""
wallets.py
==========

Lectura de saldos on-chain en modo SOLO LECTURA.

Nunca toca claves: una dirección alcanza para consultar saldos, y este módulo
no firma ni construye transacciones. Sólo hace `eth_getBalance` (nativo) y
`eth_call` a `balanceOf` (tokens) contra RPC públicos.

DÓNDE VIVEN LAS DIRECCIONES
    1. Variable de entorno `WALLET_ADDRESSES` con un JSON (para GitHub Secrets).
    2. Archivo `wallets.local.json` (ignorado por git) para uso local.

Nunca en `portfolio.json`: ese archivo se commitea a un repo público, y el
historial de git es permanente.

FORMATO

    {
      "publicar_saldos": false,
      "direcciones": [
        {"addr": "0x...", "wallet": "hot-evm", "nota": "operativa"},
        ...
      ]
    }

`publicar_saldos` en false (por defecto) mantiene los importes fuera de
`docs/data.json`, que sí se publica. Con false los saldos viajan sólo por
Telegram, que es privado.
"""

from __future__ import annotations

import certs_bootstrap  # noqa: F401

import json
import os
import re
from typing import Dict, List, Optional

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_PATH = os.path.join(HERE, "wallets.local.json")

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TIMEOUT = 15

# RPC públicos, sin API key. Se prueban en orden hasta que uno responda.
CHAINS: Dict[str, dict] = {
    "ethereum": {
        "nativo": "ETH",
        "rpc": ["https://eth.llamarpc.com", "https://cloudflare-eth.com",
                "https://rpc.ankr.com/eth"],
        "tokens": {
            "USDC": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
            "USDT": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", 6),
            "WBTC": ("0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", 8),
            "WETH": ("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18),
        },
    },
    "base": {
        "nativo": "ETH",
        "rpc": ["https://mainnet.base.org", "https://base.llamarpc.com"],
        "tokens": {
            "USDC": ("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
            "WETH": ("0x4200000000000000000000000000000000000006", 18),
        },
    },
    "arbitrum": {
        "nativo": "ETH",
        "rpc": ["https://arb1.arbitrum.io/rpc", "https://arbitrum.llamarpc.com"],
        "tokens": {
            "USDC": ("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
            "USDT": ("0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", 6),
            "WBTC": ("0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f", 8),
            "WETH": ("0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", 18),
        },
    },
    "bsc": {
        "nativo": "BNB",
        "rpc": ["https://bsc-dataseed.binance.org", "https://bsc.llamarpc.com"],
        "tokens": {
            "USDT": ("0x55d398326f99059fF775485246999027B3197955", 18),
            "USDC": ("0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18),
            "BTCB": ("0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c", 18),
        },
    },
}

# Con qué par se valúa cada símbolo. Las stables se fijan en 1 USD.
PRECIO = {"ETH": "ETHUSDT", "BNB": "BNBUSDT", "WETH": "ETHUSDT",
          "WBTC": "BTCUSDT", "BTCB": "BTCUSDT"}
STABLES = {"USDC", "USDT"}

BALANCE_OF = "0x70a08231"  # selector de balanceOf(address)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> Optional[dict]:
    """Config desde el entorno (Secret) o el archivo local. None si no hay."""
    raw = os.environ.get("WALLET_ADDRESSES", "").strip()
    if raw:
        try:
            return _validate(json.loads(raw))
        except Exception as exc:
            print(f"  WALLET_ADDRESSES ilegible: {exc}")
            return None
    if os.path.exists(LOCAL_PATH):
        try:
            with open(LOCAL_PATH, encoding="utf-8") as fh:
                return _validate(json.load(fh))
        except Exception as exc:
            print(f"  wallets.local.json ilegible: {exc}")
    return None


def _validate(cfg: dict) -> dict:
    """Descarta direcciones mal formadas antes de salir a la red."""
    out = []
    for d in cfg.get("direcciones", []):
        a = (d.get("addr") or "").strip()
        if not ADDR_RE.match(a):
            print(f"  dirección descartada por formato inválido: {a[:12]}…")
            continue
        out.append({"addr": a.lower(), "wallet": d.get("wallet", "sin-asignar"),
                    "nota": d.get("nota", "")})
    cfg["direcciones"] = out
    return cfg


# ---------------------------------------------------------------------------
# RPC
# ---------------------------------------------------------------------------
def _rpc(urls: List[str], method: str, params: list, _post=None) -> Optional[str]:
    """Una llamada JSON-RPC, probando cada endpoint hasta que uno conteste."""
    post = _post or requests.post
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for u in urls:
        try:
            r = post(u, json=payload, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if "result" in data and data["result"] is not None:
                return data["result"]
        except Exception:
            continue
    return None


def _to_int(hexstr: Optional[str]) -> int:
    if not hexstr or hexstr == "0x":
        return 0
    try:
        return int(hexstr, 16)
    except ValueError:
        return 0


def _balance_of_data(addr: str) -> str:
    """Calldata de balanceOf(address): selector + dirección a 32 bytes."""
    return BALANCE_OF + "0" * 24 + addr[2:].lower()


def fetch_chain(addr: str, chain: str, _post=None) -> Dict[str, float]:
    """Saldos (nativo + tokens) de una dirección en una cadena."""
    c = CHAINS[chain]
    urls = c["rpc"]
    out: Dict[str, float] = {}

    nat = _to_int(_rpc(urls, "eth_getBalance", [addr, "latest"], _post))
    if nat:
        out[c["nativo"]] = nat / 1e18

    for sym, (token, dec) in c["tokens"].items():
        res = _rpc(urls, "eth_call",
                   [{"to": token, "data": _balance_of_data(addr)}, "latest"], _post)
        v = _to_int(res)
        if v:
            out[sym] = v / (10 ** dec)
    return out


# ---------------------------------------------------------------------------
# Agregacion
# ---------------------------------------------------------------------------
def valuar(saldos: Dict[str, float], precios: Dict[str, float]) -> float:
    """Valor en USD de un diccionario simbolo -> cantidad."""
    total = 0.0
    for sym, qty in saldos.items():
        if sym in STABLES:
            total += qty
        elif sym in PRECIO:
            total += qty * precios.get(PRECIO[sym], 0.0)
    return total


def snapshot(precios: Dict[str, float], cfg: Optional[dict] = None,
             _post=None) -> Optional[dict]:
    """Saldos de todas las direcciones, agrupados por billetera del plan."""
    cfg = cfg or load_config()
    if not cfg or not cfg.get("direcciones"):
        return None

    por_wallet: Dict[str, dict] = {}
    detalle = []
    total = 0.0

    for d in cfg["direcciones"]:
        addr, wallet = d["addr"], d["wallet"]
        saldos: Dict[str, float] = {}
        for chain in CHAINS:
            for sym, qty in fetch_chain(addr, chain, _post).items():
                saldos[sym] = saldos.get(sym, 0.0) + qty
        usd = valuar(saldos, precios)
        total += usd

        w = por_wallet.setdefault(wallet, {"usd": 0.0, "activos": {}, "direcciones": 0})
        w["usd"] += usd
        w["direcciones"] += 1
        for sym, qty in saldos.items():
            w["activos"][sym] = w["activos"].get(sym, 0.0) + qty

        detalle.append({
            # Sólo los extremos de la dirección: alcanza para identificarla
            # de un vistazo sin volcarla entera en un archivo publicado.
            "addr_corta": addr[:6] + "…" + addr[-4:],
            "wallet": wallet, "nota": d["nota"],
            "usd": round(usd, 2), "activos": {k: round(v, 8) for k, v in saldos.items()},
        })

    for w in por_wallet.values():
        w["usd"] = round(w["usd"], 2)
        w["activos"] = {k: round(v, 8) for k, v in w["activos"].items()}

    return {"total_usd": round(total, 2), "por_wallet": por_wallet,
            "direcciones": detalle, "publicar": bool(cfg.get("publicar_saldos", False))}


if __name__ == "__main__":
    cfg = load_config()
    if not cfg:
        print("No hay direcciones configuradas (ni WALLET_ADDRESSES ni wallets.local.json).")
    else:
        print(f"{len(cfg['direcciones'])} direcciones · publicar_saldos="
              f"{cfg.get('publicar_saldos', False)}")
        print(json.dumps(snapshot({"BTCUSDT": 79310, "ETHUSDT": 2493, "BNBUSDT": 707}, cfg),
                         indent=2, ensure_ascii=False))
