---
name: analizar
description: Ficha de análisis de una acción o ETF combinando precio y técnicos en vivo (Twelve Data), rank/estimaciones/valuación (Zacks) y noticias recientes, y cierra con un plan de trade concreto — entrada, stop, objetivos y relación riesgo/beneficio. Usar SIEMPRE que se pregunte por un ticker con intención operativa: "largo en X?", "entro a X?", "cómo viene X", "analizá X", "qué hago con X", "conviene comprar X", "X está caro?", o cuando se pide comparar candidatos ("algún largo? NFLX o TSLA?"). También cuando se pregunta por un sector ("oportunidad en semiconductores?") — ahí se corre la ficha sobre los nombres del sector y se rankean. Aplicar aunque no se diga "analizá" textualmente: cualquier pregunta que espere una decisión de compra/venta sobre un símbolo cotizante cuenta.
---

# Analizar un ticker

El objetivo es una ficha corta y accionable, no un research report. Quien pregunta ya sabe qué es la empresa: quiere saber **a qué precio entra, dónde pone el stop y qué puede salir mal**. Todo lo que no sirva para tomar esa decisión sobra.

## Regla que ordena todo lo demás

**Nunca inventes un precio ni un indicador.** Si una fuente no responde o está limitada por plan, decilo y seguí con las que sí funcionan. Una ficha con un dato inventado es peor que una ficha incompleta — alguien puede operar con eso. Cuando un número viene de una nota periodística y no de un feed, marcalo como aproximado.

## Paso 1 — Precio y estructura (Twelve Data)

Esta es la única fuente de esta sesión con **cotización en tiempo real**. Empezá siempre acá.

```
get_quote(symbol="MRVL")
```

Fijate en `is_market_open`: si es `false`, lo que tenés es el último cierre, y la ficha tiene que decirlo. `percent_change` se calcula contra `previous_close`, que es el cierre anterior, no el de hace un rato.

Después, las medias y el RSI. Pedí el diario para la estructura y el horario para el timing de entrada:

```
get_technical_indicator(indicator="SMA",  symbol="MRVL", interval="1day", time_period=20, outputsize=2)
get_technical_indicator(indicator="SMA",  symbol="MRVL", interval="1day", time_period=50, outputsize=2)
get_technical_indicator(indicator="RSI",  symbol="MRVL", interval="1day", time_period=14, outputsize=2)
get_technical_indicator(indicator="RSI",  symbol="MRVL", interval="1h",   time_period=14, outputsize=4)
get_technical_indicator(indicator="ATR",  symbol="MRVL", interval="1day", time_period=14, outputsize=2)
```

El ATR es el que dimensiona el stop: un stop más ajustado que un ATR diario se ejecuta por ruido, no por tesis.

Para ubicar soportes y resistencias reales necesitás las velas, no solo las medias — `get_time_series(symbol, interval="1day", outputsize=60)`. Los niveles que importan son los máximos y mínimos donde el precio ya giró, y los gaps de earnings sin cerrar. Un número redondo no es un nivel.

## Paso 2 — El contrapeso fundamental (Zacks)

```
get_zacks_metrics(ticker="MRVL")
```

Devuelve Zacks Rank (1 Strong Buy a 5 Sell), recomendación, target price, style scores V/G/M/VGM, PE, P/S, beta, ranking de industria, estimaciones de EPS y ventas por año, fecha del próximo earnings y peers con su rank.

Tres cosas de acá cambian un trade y hay que mirarlas siempre:

- **El target contra el precio actual.** Si el precio ya está arriba del target, el consenso dice que no hay upside — eso no invalida una ruptura técnica pero sí achica el objetivo realista.
- **La fecha del próximo earnings.** Un swing que cruza un reporte es una moneda al aire, no un trade. Decilo explícitamente si el earnings cae dentro del horizonte.
- **La beta.** Arriba de 2 el tamaño de posición importa más que el punto de entrada.

Los style scores en F con Rank 3 y estimaciones subiendo es una combinación común en papeles de momentum caros: el papel puede seguir subiendo, pero no es "barato" bajo ningún criterio. Presentalo como la tensión que es, no lo escondas.

## Paso 3 — Qué pasó (noticias)

Ojo con la fuente: `get_company_news` de Twelve Data devuelve **press releases de la empresa**, no cobertura de mercado, y puede estar meses desactualizado — no sirve para explicar el movimiento del día. Para eso usá `get_real_time_news` de Zacks o una búsqueda web.

Vale la pena buscar el driver siempre que el movimiento del día supere un ATR. Un -7% por una nota sectorial y un -7% por guidance propio son situaciones distintas: la primera suele revertir, la segunda no.

## Paso 4 — La ficha

Este es el formato. Mantenelo corto; si algo no aporta a la decisión, borralo.

```
## TICKER — 242.47  +5.55%   [mercado abierto | último cierre]

| | |
|---|---|
| SMA20 / SMA50 | 227.90 / 216.31 |
| RSI 14 diario / 1h | 55.5 / 66.3 |
| ATR14 | 12.40 (5.1%) |
| Rango 52s | 68.36 – 329.88 |
| Zacks Rank | 3 (Hold) · target 238 |
| Scores V/G/M | F / C / F |
| Beta | 2.25 |
| Próximo earnings | 01/12/2026 |

**Estructura:** [dónde está parado respecto de sus medias y de los niveles
previos, en dos o tres frases]

**Plan:**
- Entrada: [nivel y por qué ahí]
- Stop: [nivel, debajo de qué referencia, y a cuántos ATR]
- Objetivos: [el primero realista, el segundo si extiende]
- R/R: [riesgo vs recorrido al primer objetivo]

**En contra:** [lo que rompe la tesis — valuación, earnings cerca,
divergencia con el consenso, beta alta, el papel ya corrió]
```

Cerrá con una línea aclarando que es análisis técnico y de contexto, no asesoramiento financiero.

## Cuando la pregunta es por un sector

Corré `get_quote` sobre los nombres del sector más su ETF de referencia (semis: SMH o SOXX; y el ETF manda — si el ETF está abajo de su SMA50, ningún componente es un largo cómodo). Después rankealos por alineación de medias y armá la ficha completa solo del mejor y del peor, con una tabla para el resto. Quien pregunta por un sector quiere un nombre, no diez fichas.

## Enganche con las alertas del repo

Este repo corre un monitor de alertas (`telegram_alerts.py`, configurado en `alerts_config.json`). Cuando la ficha define niveles, ofrecé cargarlos como alertas en ese formato:

```json
{"symbol": "MRVL", "market": "stock", "level": 242.0, "direction": "above", "note": "ruptura, long"}
```

`market` es `"stock"` (yfinance) o `"crypto"` (Binance). Cuidado: un ticker de acción cargado como `crypto` va a Binance, devuelve HTTP 400 y la alerta **nunca dispara** — es un error que ya apareció en este config.

## Qué funciona y qué no

Probado en esta sesión, para no perder tiempo re-descubriéndolo:

| Fuente | Estado |
|---|---|
| Twelve Data — quote, indicadores, series, news, earnings | ✅ tiempo real |
| Twelve Data — `get_analyst_data(data_type="price_target")` | ❌ requiere plan ultra |
| Zacks — metrics, research, news | ✅ |
| Alpha Vantage — cierres, series diarias, fundamentals | ✅ pero solo EOD |
| Alpha Vantage — intradiario y realtime | ❌ endpoint premium |
| FMP — `quote` | ❌ requiere plan superior |
| yfinance directo desde el contenedor | ❌ Yahoo bloqueado por el proxy de egress |

Twelve Data no cubre **índices** (SPX, NDX, DJI), opciones ni bonos. Para un índice usá su ETF: SPY, QQQ, DIA, IWM.

Si los conectores se caen, queda el camino largo: `quotes.py` del repo corrido vía GitHub Actions (`workflow_dispatch` en `alerts.yml` con el input `quotes`), que usa yfinance desde un runner sin el bloqueo. Es lento (~90s) pero funciona.
