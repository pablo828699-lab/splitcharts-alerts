"""
telegram_alerts.py
==================

Motor de alertas por Telegram para SplitCharts.

Corre en loop, cada `poll_seconds` revisa los precios/indicadores usando la misma
capa de datos del backend (data_source + oscillators) y dispara un mensaje a
Telegram cuando se cumple una regla. Funciona aunque el navegador esté cerrado
(mientras este proceso siga corriendo).

Tipos de alerta soportados:
  * price_alerts -> cruce de un nivel de precio (arriba/abajo) que vos definís.
  * rsi_alerts   -> RSI entra en sobrecompra (>=overbought) o sobreventa (<=oversold).

Configuración: alerts_config.json (pegá ahí tu bot_token, chat_id y las reglas).

Uso:
    python telegram_alerts.py            # corre el loop de alertas
    python telegram_alerts.py --test     # manda un mensaje de prueba y sale
"""

from __future__ import annotations

# Bootstrap del almacén de certificados de Windows ANTES de requests/yfinance.
import certs_bootstrap  # noqa: F401

import argparse
import json
import os
import sys
import time
from datetime import datetime

# La consola de Windows (cp1252) no puede imprimir emojis -> forzar UTF-8 para
# que los print() con 🔔/✅/⚠️ no crasheen. (Los mensajes a Telegram ya van UTF-8.)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import requests

import data_source as ds
from oscillators import compute_oscillators

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts_config.json")


# ---------------------------------------------------------------------------
# Config + Telegram
# ---------------------------------------------------------------------------
def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_creds(cfg):
    """Credenciales: las variables de entorno (GitHub Secrets) tienen prioridad
    sobre el archivo, para no tener que commitear el token en la nube."""
    tg = cfg.get("telegram", {}) or {}
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or tg.get("bot_token") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHAT_ID") or str(tg.get("chat_id") or "")).strip()
    return {"bot_token": token, "chat_id": chat}


# Estado persistente (para modo --once en la nube): guarda el precio previo de
# cada alerta y si el RSI ya está en zona, así no se re-dispara en cada corrida.
STATE_PATH = os.environ.get(
    "ALERTS_STATE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts_state.json"),
)


def _load_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception as exc:
        print(f"[{_now()}] no se pudo guardar el estado: {exc}")


def send_telegram(token, chat_id, text):
    """Enviar un mensaje HTML a Telegram. Devuelve (ok, detalle)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": str(chat_id), "text": text,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        if r.status_code == 200:
            return True, "ok"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.RequestException as exc:
        return False, str(exc)


def get_chat_ids(token):
    """Leer getUpdates y devolver los chat ids que le escribieron al bot."""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
    except Exception as exc:
        return [], str(exc)
    if not data.get("ok"):
        return [], data.get("description", "error")
    found = {}
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is not None:
            name = chat.get("username") or chat.get("first_name") or chat.get("title") or ""
            found[cid] = name
    return [(cid, name) for cid, name in found.items()], None


def _valid_creds(tg):
    token = tg.get("bot_token", "").strip()
    chat = str(tg.get("chat_id", "")).strip()
    if not token or "PEGA" in token or not chat or "PEGA" in chat:
        return False
    return True


# ---------------------------------------------------------------------------
# Lectura de precio / RSI (reusa la capa de datos del backend)
# ---------------------------------------------------------------------------
def get_price(symbol, market):
    if market == "stock":
        return float(ds.fetch_stock_quote(symbol))
    df = ds.get_ohlcv("crypto", symbol, "1m", 3)
    return float(df["close"].iloc[-1])


def _price_window(symbol, market, since_ts, cache):
    """Precio actual + mínimo/máximo desde `since_ts`.

    Mirar solo el precio spot pierde los toques que ocurren ENTRE dos lecturas:
    un pinchazo de 10s es invisible si el poller pasa cada 5 min. Tomando el
    min/max de las velas de 1m posteriores a la última revisión, ningún toque
    del nivel se escapa, sin importar la cadencia.

    Devuelve (precio, minimo, maximo). Sin `since_ts` (primera corrida) o si las
    velas fallan, cae al precio spot -> (px, px, px), el comportamiento previo.
    """
    ck = (symbol, market)
    if ck in cache:
        return cache[ck]
    px = get_price(symbol, market)
    lo = hi = px
    if since_ts:
        try:
            df = ds.get_ohlcv(market, symbol, "1m", 90)
            df = df[df["time"] > int(since_ts)]
            if len(df):
                lo = min(px, float(df["low"].min()))
                hi = max(px, float(df["high"].max()))
        except Exception as exc:
            print(f"[{_now()}] velas 1m de {symbol} no disponibles ({exc}); uso precio spot")
    cache[ck] = (px, lo, hi)
    return cache[ck]


def get_rsi(symbol, market, interval, period=14):
    df = ds.get_ohlcv(market, symbol, interval, 200)
    osc = compute_oscillators(df, {"rsi": True, "rsi_period": period, "macd": False})
    r = osc.get("rsi", [])
    return float(r[-1]["value"]) if r else None


def _fmt(v):
    a = abs(v)
    d = 4 if a < 1 else 3 if a < 10 else 2 if a < 1000 else 0
    return f"{v:,.{d}f}"


# ---------------------------------------------------------------------------
# Evaluación de reglas
# ---------------------------------------------------------------------------
def check_price_alerts(cfg, state, tg, price_cache):
    since = state.get("_last_check")
    for a in cfg.get("price_alerts", []):
        symbol = a["symbol"].upper()
        market = a.get("market", "crypto")
        level = float(a["level"])
        direction = a.get("direction", "above").lower()
        note = a.get("note", "")
        key = f"px|{symbol}|{market}|{level}|{direction}"
        try:
            px, lo, hi = _price_window(symbol, market, since, price_cache)
        except Exception as exc:
            print(f"[{_now()}] precio {symbol} error: {exc}")
            continue

        prev = state.get(key)
        state[key] = px
        if prev is None:
            # Primera lectura de esta alerta. Un cruce solo se detecta comparando
            # dos lecturas, así que si el precio YA está del lado cumplido la
            # alerta nunca dispararía (nace "pasada"): con la nube leyendo cada
            # 5 min, cualquier nivel cerca del precio cae en este caso. Avisar
            # una vez en lugar de armarla muerta en silencio.
            already = ((direction == "above" and px >= level) or
                       (direction == "below" and px <= level))
            if already:
                side = "por encima de" if direction == "above" else "por debajo de"
                msg = (f"⚠️ <b>{symbol}</b> ya estaba {side} <b>{_fmt(level)}</b> "
                       f"al crear la alerta\nPrecio: <b>{_fmt(px)}</b>\n"
                       f"<i>Sin aviso de cruce hasta que vuelva al otro lado y "
                       f"lo cruce de nuevo.</i>")
                if note:
                    msg += f"\n<i>{note}</i>"
                _fire(tg, msg, key)
            continue

        # El nivel cuenta como cruzado si lo tocó en CUALQUIER momento desde la
        # lectura anterior, aunque el precio ya haya rebotado (mecha).
        if direction == "above":
            crossed, extremo = (prev < level and hi >= level), hi
        else:
            crossed, extremo = (prev > level and lo <= level), lo
        if crossed:
            arrow = "⬆️ hacia arriba" if direction == "above" else "⬇️ hacia abajo"
            msg = (f"🔔 <b>{symbol}</b> cruzó <b>{_fmt(level)}</b> {arrow}\n"
                   f"Precio: <b>{_fmt(px)}</b>")
            volvio = ((direction == "above" and px < level) or
                      (direction == "below" and px > level))
            if volvio:
                msg += f"\n<i>Tocó {_fmt(extremo)} y ya volvió.</i>"
            if note:
                msg += f"\n<i>{note}</i>"
            _fire(tg, msg, key)

    # Marca hasta dónde se miraron las velas: la próxima pasada solo evalúa lo
    # ocurrido después, así ningún toque se cuenta (ni avisa) dos veces.
    state["_last_check"] = int(time.time())


def check_rsi_alerts(cfg, state, tg):
    for a in cfg.get("rsi_alerts", []):
        symbol = a["symbol"].upper()
        market = a.get("market", "crypto")
        interval = a.get("interval", "1h")
        period = int(a.get("period", 14))
        overbought = float(a.get("overbought", 70))
        oversold = float(a.get("oversold", 30))
        key = f"rsi|{symbol}|{market}|{interval}"
        try:
            rsi = get_rsi(symbol, market, interval, period)
        except Exception as exc:
            print(f"[{_now()}] RSI {symbol} error: {exc}")
            continue
        if rsi is None:
            continue

        st = state.setdefault(key, {"ob": False, "os": False})
        # Sobrecompra: disparar al ENTRAR, resetear al salir (evita spam).
        if rsi >= overbought and not st["ob"]:
            _fire(tg, f"📈 <b>{symbol}</b> ({interval}) RSI en <b>sobrecompra</b>: "
                      f"{rsi:.1f} (≥ {overbought:.0f})", key + "|ob")
            st["ob"] = True
        elif rsi < overbought:
            st["ob"] = False
        # Sobreventa
        if rsi <= oversold and not st["os"]:
            _fire(tg, f"📉 <b>{symbol}</b> ({interval}) RSI en <b>sobreventa</b>: "
                      f"{rsi:.1f} (≤ {oversold:.0f})", key + "|os")
            st["os"] = True
        elif rsi > oversold:
            st["os"] = False


def _now():
    return datetime.now().strftime("%H:%M:%S")


def _fire(tg, msg, key):
    ok, detail = send_telegram(tg["bot_token"], tg["chat_id"], msg)
    plain = msg.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "").replace("\n", " | ")
    if ok:
        print(f"[{_now()}] ✅ ALERTA enviada: {plain}")
    else:
        print(f"[{_now()}] ❌ fallo Telegram ({detail}) para: {plain}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Alertas de SplitCharts por Telegram")
    ap.add_argument("--test", action="store_true", help="enviar un mensaje de prueba y salir")
    ap.add_argument("--chatid", action="store_true",
                    help="mostrar los chat ids que le escribieron al bot y salir")
    ap.add_argument("--once", action="store_true",
                    help="ejecutar UN solo chequeo y salir (para cron / GitHub Actions)")
    args = ap.parse_args()

    if not os.path.exists(CONFIG_PATH):
        print(f"No existe {CONFIG_PATH}. Creá el archivo de config primero.")
        sys.exit(1)

    cfg = load_config()
    tg = resolve_creds(cfg)

    # --chatid: solo necesita el token. Ayuda a encontrar el ID numérico correcto.
    if args.chatid:
        token = tg["bot_token"].strip()
        if not token or "PEGA" in token:
            print("Primero pegá tu bot_token en alerts_config.json.")
            sys.exit(1)
        ids, err = get_chat_ids(token)
        if err:
            print(f"No se pudo leer getUpdates: {err}")
            sys.exit(1)
        if not ids:
            print("No encontré mensajes. Abrí Telegram, buscá TU bot y mandale "
                  "cualquier mensaje (ej. 'hola'), después corré esto de nuevo.")
            sys.exit(1)
        print("Chat id(s) encontrados (copiá el número al campo 'chat_id'):")
        for cid, name in ids:
            print(f"   chat_id = {cid}    ({name})")
        sys.exit(0)

    if not _valid_creds(tg):
        print("⚠️  Falta 'bot_token' y/o 'chat_id' (en alerts_config.json o en las "
              "variables TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID).")
        sys.exit(1)

    if args.test:
        ok, detail = send_telegram(tg["bot_token"], tg["chat_id"],
                                   "✅ <b>SplitCharts</b>: alertas conectadas correctamente.")
        print("Mensaje de prueba enviado." if ok else f"Falló: {detail}")
        sys.exit(0 if ok else 1)

    # --once: un solo ciclo, con estado persistido en disco. Para cron/GitHub Actions.
    if args.once:
        state = _load_state()
        check_price_alerts(cfg, state, tg, {})
        check_rsi_alerts(cfg, state, tg)
        _save_state(state)
        print(f"[{_now()}] chequeo único completado "
              f"({len(cfg.get('price_alerts', []))} precio · {len(cfg.get('rsi_alerts', []))} RSI).")
        sys.exit(0)

    poll = int(cfg.get("poll_seconds", 60))
    n_px = len(cfg.get("price_alerts", []))
    n_rsi = len(cfg.get("rsi_alerts", []))
    print(f"[{_now()}] Alertas activas: {n_px} de precio, {n_rsi} de RSI. "
          f"Revisando cada {poll}s. (Ctrl+C para salir)")
    send_telegram(tg["bot_token"], tg["chat_id"],
                  f"🟢 <b>SplitCharts</b>: monitor de alertas iniciado "
                  f"({n_px} precio · {n_rsi} RSI, cada {poll}s).")

    state = {}
    while True:
        try:
            cfg = load_config()          # recargar en caliente: editás reglas sin reiniciar
            tg = resolve_creds(cfg)
            price_cache = {}
            check_price_alerts(cfg, state, tg, price_cache)
            check_rsi_alerts(cfg, state, tg)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[{_now()}] error en el ciclo: {exc}")
        time.sleep(poll)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nMonitor de alertas detenido.")
