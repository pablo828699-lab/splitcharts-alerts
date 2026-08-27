"""
portfolio_monitor.py
====================

Motor de seguimiento de la cartera de 300k.

Lee `portfolio.json` (la estrategia como datos), trae los precios con la misma
capa que el resto del repo (`data_source`), evalua el mercado contra la
estrategia y produce DOS salidas:

    1. Alertas a Telegram  -> escalon tocado, take-profit, invalidacion.
    2. `docs/data.json`    -> el estado que consume el tablero estatico.

Corre en el mismo workflow que `telegram_alerts.py` (GitHub Actions cada 5 min),
asi que el tablero publicado en Netlify queda al dia sin servidor propio.

Uso:
    python portfolio_monitor.py --once          # una pasada (cron / Actions)
    python portfolio_monitor.py --once --dry    # sin mandar Telegram
    python portfolio_monitor.py --fake-prices BTCUSDT=60000,ETHUSDT=1800
                                                # inyecta precios para probar
"""

from __future__ import annotations

import certs_bootstrap  # noqa: F401  (bootstrap de certificados, va primero)

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import data_source as ds
import funding as fnd
from oscillators import compute_oscillators
from telegram_alerts import resolve_creds, send_telegram, load_config as load_alerts_config

HERE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_PATH = os.path.join(HERE, "portfolio.json")
STATE_PATH = os.environ.get("PORTFOLIO_STATE", os.path.join(HERE, "portfolio_state.json"))
OUT_PATH = os.path.join(HERE, "docs", "data.json")

# Cuanto puede alejarse un escalon del precio actual y seguir mostrandose como
# "cargado" en el tablero. Mas lejos que esto se marca como durmiente.
FAR_PCT = 45.0


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------
def load_portfolio(path=PORTFOLIO_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ---------------------------------------------------------------------------
# Precios
# ---------------------------------------------------------------------------
def fetch_market(symbol, since_ts=None):
    """Precio actual + minimo/maximo desde `since_ts` + RSI diario.

    El min/max de las velas de 1m posteriores a la ultima corrida evita que un
    pinchazo de 30 segundos hacia un escalon se pierda entre dos pasadas del
    cron (mismo criterio que usa telegram_alerts.py).
    """
    df = ds.get_ohlcv("crypto", symbol, "1m", 300)
    px = float(df["close"].iloc[-1])
    lo = hi = px
    if since_ts:
        w = df[df["time"] > int(since_ts)]
        if len(w):
            lo = min(px, float(w["low"].min()))
            hi = max(px, float(w["high"].max()))

    rsi = None
    try:
        d = ds.get_ohlcv("crypto", symbol, "1d", 200)
        osc = compute_oscillators(d, {"rsi": True, "rsi_period": 14, "macd": False})
        pts = osc.get("rsi", [])
        if pts:
            rsi = round(float(pts[-1]["value"]), 1)
    except Exception as exc:
        _log(f"RSI diario de {symbol} no disponible ({exc})")

    return {"price": px, "low": lo, "high": hi, "rsi_1d": rsi}


def parse_fake(spec):
    out = {}
    for part in (spec or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().upper()] = float(v)
    return out


# ---------------------------------------------------------------------------
# Evaluacion
# ---------------------------------------------------------------------------
def eval_ladders(pf, market, state, fire):
    """Marca escalones tocados y devuelve la vista para el tablero."""
    touched_state = state.setdefault("ladder_touched", {})
    out = {}

    for symbol, rungs in pf.get("ladders", {}).items():
        m = market.get(symbol)
        if not m:
            continue
        px = m["price"]
        rows = []
        for i, rung in enumerate(rungs):
            level = float(rung["price"])
            key = f"{symbol}|{level}"
            already = touched_state.get(key)

            # Tocado = el minimo de la ventana llego al nivel. Contempla la mecha,
            # no solo el precio de cierre de la pasada.
            hit = m["low"] <= level
            if hit and not already:
                touched_state[key] = _now_iso()
                already = touched_state[key]
                fire(
                    f"🎯 <b>ESCALON TOCADO</b> — {symbol.replace('USDT','')} @ "
                    f"<b>{level:,.0f}</b>\n"
                    f"Comprar <b>{rung['usd']:,.0f} USD</b>\n"
                    f"<i>{rung.get('tag','')}</i>\n"
                    f"Precio ahora: {px:,.0f}"
                )

            dist = (level - px) / px * 100.0
            rows.append({
                "price": level,
                "usd": rung["usd"],
                "tag": rung.get("tag", ""),
                "dist_pct": round(dist, 1),
                "touched_at": already,
                "status": ("tocado" if already
                           else "durmiente" if abs(dist) > FAR_PCT
                           else "cargado"),
            })
        out[symbol] = rows
    return out


def eval_take_profit(pf, market, state, fire):
    """Avisa una sola vez por cada peldanio de toma de ganancias."""
    btc = market.get("BTCUSDT")
    if not btc:
        return []
    done = state.setdefault("tp_fired", {})
    rows = []
    for tp in pf.get("rules", {}).get("take_profit", []):
        lvl = float(tp["trigger_btc"])
        key = str(lvl)
        hit = btc["high"] >= lvl
        if hit and key not in done:
            done[key] = _now_iso()
            fire(f"💰 <b>TOMA DE GANANCIAS</b> — BTC alcanzo <b>{lvl:,.0f}</b>\n{tp['accion']}")
        rows.append({
            "trigger_btc": lvl,
            "accion": tp["accion"],
            "dist_pct": round((lvl - btc["price"]) / btc["price"] * 100.0, 1),
            "fired_at": done.get(key),
        })
    return rows


def eval_invalidation(pf, market, state, fire):
    """Regla de invalidacion: BTC bajo el escalon mas profundo."""
    btc = market.get("BTCUSDT")
    if not btc:
        return None
    rungs = pf.get("ladders", {}).get("BTCUSDT", [])
    if not rungs:
        return None
    floor = min(float(r["price"]) for r in rungs)
    below = btc["price"] < floor
    was = state.get("invalidation_active", False)
    if below and not was:
        state["invalidation_active"] = True
        fire(f"🚨 <b>INVALIDACION</b> — BTC bajo <b>{floor:,.0f}</b> ({btc['price']:,.0f})\n"
             f"{pf.get('rules',{}).get('invalidacion','')}")
    elif not below and was:
        state["invalidation_active"] = False
    return {"floor": floor, "active": below,
            "texto": pf.get("rules", {}).get("invalidacion", "")}


def eval_funding(pf, state, fire, fake=None):
    """Semaforo de instrumento por funding, avisando solo al CAMBIAR de regimen.

    Un aviso por corrida seria ruido: el funding se mueve todo el dia dentro de
    la misma banda. Lo que importa operativamente es el cruce de banda, porque
    es lo que cambia DONDE se abre la proxima posicion.
    """
    symbols = list(pf.get("ladders", {}).keys())
    if fake:
        snap = {}
        for s_ in symbols:
            r = fake.get(s_)
            row = {"rate_8h": r,
                   "anual_pct": round(fnd.annualized(r), 1) if r is not None else None}
            row.update(fnd.classify(r))
            snap[s_] = row
    else:
        snap = fnd.snapshot(symbols)
    prev = state.setdefault("funding_nivel", {})

    for sym, row in snap.items():
        nivel = row["nivel"]
        if nivel == "sin_dato":
            continue
        if prev.get(sym) and prev[sym] != nivel:
            asset = sym.replace("USDT", "")
            fire(f"⚖️ <b>FUNDING {asset}</b>: {prev[sym]} → <b>{nivel}</b>\n"
                 f"{row['rate_8h']*100:+.4f}%/8h ({row['anual_pct']:+.1f}% anual)\n"
                 f"<i>{row['texto']}</i>")
        prev[sym] = nivel

    return snap


def cycle_view(pf, market):
    """Contexto de ciclo: caida desde el ATH, rebote desde el minimo, halving."""
    refs = pf.get("cycle", {}).get("refs", {})
    rows = []
    for symbol, r in refs.items():
        m = market.get(symbol)
        if not m:
            continue
        px = m["price"]
        rows.append({
            "symbol": symbol,
            "asset": symbol.replace("USDT", ""),
            "price": px,
            "rsi_1d": m.get("rsi_1d"),
            "ath": r["ath"], "ath_fecha": r.get("ath_fecha"),
            "min_ciclo": r["min_ciclo"], "min_fecha": r.get("min_fecha"),
            "desde_ath_pct": round((px - r["ath"]) / r["ath"] * 100.0, 1),
            "desde_min_pct": round((px - r["min_ciclo"]) / r["min_ciclo"] * 100.0, 1),
        })

    c = pf.get("cycle", {})
    nxt = datetime.strptime(c["next_halving_est"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    last = datetime.strptime(c["last_halving"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return {
        "assets": rows,
        "last_halving": c["last_halving"],
        "next_halving": c["next_halving_est"],
        "dias_al_halving": (nxt - now).days,
        "dias_desde_halving": (now - last).days,
        "pct_del_ciclo": round((now - last).total_seconds() / (nxt - last).total_seconds() * 100.0, 1),
    }


def capital_view(pf, ladders):
    """Cuanto capital sigue esperando y cuanto ya se activo."""
    sleeves = []
    for s in pf["sleeves"]:
        row = {k: s[k] for k in ("id", "label", "usd", "color", "tesis")}
        row["regla_dura"] = s.get("regla_dura", "")
        row["ejecucion"] = s.get("ejecucion", "")
        if s["id"] == "escalones":
            hit = sum(r["usd"] for rows in ladders.values() for r in rows if r["touched_at"])
            row["activado_usd"] = hit
            row["pendiente_usd"] = s["usd"] - hit
        sleeves.append(row)

    core = pf["core"]
    return {
        "core": core,
        "sleeves": sleeves,
        "total": pf["meta"]["capital_total_usd"],
        "en_riesgo_pct": round(
            sum(s["usd"] for s in pf["sleeves"] if s["id"] in ("beta", "discrecional"))
            / pf["meta"]["capital_total_usd"] * 100.0, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(dry=False, fake=None, fake_funding=None):
    pf = load_portfolio()
    state = load_state()
    since = state.get("_last_check")

    # Credenciales: reusa las del motor de alertas (env vars > archivo).
    try:
        tg = resolve_creds(load_alerts_config())
    except Exception:
        tg = {"bot_token": "", "chat_id": ""}

    sent = []

    def fire(msg):
        sent.append(msg)
        plain = (msg.replace("<b>", "").replace("</b>", "")
                    .replace("<i>", "").replace("</i>", "").replace("\n", " | "))
        if dry or not tg.get("bot_token") or not tg.get("chat_id"):
            _log(f"(dry) {plain}")
            return
        ok, detail = send_telegram(tg["bot_token"], tg["chat_id"], msg)
        _log(("✅ " if ok else f"❌ ({detail}) ") + plain)

    # --- precios ---
    symbols = sorted(set(list(pf.get("ladders", {}).keys())
                         + list(pf.get("cycle", {}).get("refs", {}).keys())))
    market, errors = {}, []
    for sym in symbols:
        if fake and sym in fake:
            px = fake[sym]
            market[sym] = {"price": px, "low": px, "high": px, "rsi_1d": None}
            continue
        try:
            market[sym] = fetch_market(sym, since)
        except Exception as exc:
            errors.append(f"{sym}: {exc}")
            _log(f"precio {sym} error: {exc}")

    if not market:
        _log("sin precios: no se genera salida")
        return 1

    # --- evaluacion ---
    ladders = eval_ladders(pf, market, state, fire)
    tps = eval_take_profit(pf, market, state, fire)
    inval = eval_invalidation(pf, market, state, fire)
    funding_snap = eval_funding(pf, state, fire, fake_funding)

    payload = {
        "generado": _now_iso(),
        "meta": pf["meta"],
        "cycle": cycle_view(pf, market),
        "capital": capital_view(pf, ladders),
        "ladders": ladders,
        "dca": pf["sleeves"][0],
        "dca_split": pf["sleeves"][0].get("split", {}),
        "take_profit": tps,
        "invalidacion": inval,
        "funding": funding_snap,
        "trading": pf.get("trading", {}),
        "wallets": pf["wallets"],
        "rules": pf["rules"],
        "alertas_esta_corrida": len(sent),
        "errores": errors,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    state["_last_check"] = int(time.time())
    save_state(state)

    _log(f"tablero actualizado -> {OUT_PATH} "
         f"({len(market)} activos, {len(sent)} alertas)")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Monitor de la cartera de 300k")
    ap.add_argument("--once", action="store_true", help="una pasada y salir")
    ap.add_argument("--dry", action="store_true", help="no enviar a Telegram")
    ap.add_argument("--fake-prices", default=None,
                    help="inyectar precios, ej: BTCUSDT=60000,ETHUSDT=1800")
    ap.add_argument("--fake-funding", default=None,
                    help="inyectar funding por 8h, ej: BTCUSDT=0.0004,ETHUSDT=-0.00001")
    args = ap.parse_args()
    sys.exit(run(dry=args.dry, fake=parse_fake(args.fake_prices),
                 fake_funding=parse_fake(args.fake_funding)))


if __name__ == "__main__":
    main()
