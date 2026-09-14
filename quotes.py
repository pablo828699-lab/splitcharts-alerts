#!/usr/bin/env python3
"""
quotes.py
=========

Imprime una foto rápida del mercado para una lista de símbolos, usando el mismo
data_source.py que usa el monitor de alertas.

Sirve para consultar precios desde un runner de GitHub Actions, donde yfinance
tiene salida a internet (a diferencia de entornos con egress restringido).

Uso:
    python quotes.py MRVL AMD NVDA
    python quotes.py --market crypto BTCUSDT ETHUSDT
"""

from __future__ import annotations

import argparse
import sys

import data_source
from data_source import DataSourceError


def _sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def _rsi(closes, period=14):
    """RSI de Wilder, sin depender de `ta` (mismo criterio que oscillators.py)."""
    if len(closes) <= period:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    up = sum(d for d in deltas[:period] if d > 0) / period
    down = sum(-d for d in deltas[:period] if d < 0) / period
    for d in deltas[period:]:
        up = (up * (period - 1) + max(d, 0.0)) / period
        down = (down * (period - 1) + max(-d, 0.0)) / period
    if down == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + up / down)


def snapshot(symbol: str, market: str) -> dict:
    """Precio actual + estructura diaria (medias, RSI, rango) de un símbolo."""
    df = data_source.get_ohlcv(market, symbol, "1d", limit=220)
    closes = [float(c) for c in df["close"].tolist()]

    try:
        last = data_source.fetch_stock_quote(symbol) if market == "stock" else closes[-1]
    except DataSourceError:
        last = closes[-1]

    prev = closes[-2] if len(closes) >= 2 else last
    return {
        "symbol": symbol,
        "last": last,
        "chg_pct": (last / prev - 1.0) * 100.0 if prev else 0.0,
        "sma20": _sma(closes, 20),
        "sma50": _sma(closes, 50),
        "sma200": _sma(closes, 200),
        "rsi14": _rsi(closes),
        "hi": max(float(h) for h in df["high"].tolist()),
        "lo": min(float(l) for l in df["low"].tolist()),
    }


def _fmt(v, width=9):
    return f"{v:>{width}.2f}" if isinstance(v, (int, float)) else f"{'n/d':>{width}}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Foto de mercado para una lista de símbolos.")
    ap.add_argument("symbols", nargs="+", help="Tickers, ej: MRVL AMD NVDA")
    ap.add_argument("--market", default="stock", choices=["stock", "crypto"],
                    help="Fuente de datos (default: stock).")
    args = ap.parse_args(argv)

    header = (f"{'SIMBOLO':<10}{'ULTIMO':>10}{'DIA %':>9}{'SMA20':>10}"
              f"{'SMA50':>10}{'SMA200':>10}{'RSI14':>8}{'MAX':>10}{'MIN':>10}")
    print(header)
    print("-" * len(header))

    failures = 0
    for symbol in args.symbols:
        try:
            s = snapshot(symbol, args.market)
        except Exception as exc:
            print(f"{symbol:<10}  ERROR: {exc}")
            failures += 1
            continue
        print(f"{s['symbol']:<10}{_fmt(s['last'], 10)}{_fmt(s['chg_pct'], 9)}"
              f"{_fmt(s['sma20'], 10)}{_fmt(s['sma50'], 10)}{_fmt(s['sma200'], 10)}"
              f"{_fmt(s['rsi14'], 8)}{_fmt(s['hi'], 10)}{_fmt(s['lo'], 10)}")

    print("\n(MAX/MIN = rango de las ultimas ~220 ruedas)")
    return 1 if failures == len(args.symbols) else 0


if __name__ == "__main__":
    sys.exit(main())
