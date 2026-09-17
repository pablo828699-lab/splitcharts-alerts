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

**El campo `volume` no sirve con el mercado abierto.** Devuelve un acumulado parcial que no es comparable contra el volumen de cierre de ayer — vas a ver 457k contra 16.2M y parece colapso de interés cuando no lo es. Consecuencia práctica: con el mercado abierto **no se puede confirmar una ruptura por volumen**. Decilo en vez de sacar una conclusión falsa; `average_volume` sí es un promedio real y sirve de referencia.

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

**En contra:** [lo que rompe la tesis — valuación, earnings cerca,
divergencia con el consenso, beta alta, el papel ya corrió]

---

### VEREDICTO

**LONG / SHORT / AFUERA**  ·  [a mercado | limit en X | recién si pasa X]

| | |
|---|---|
| Entrada | 234.00 |
| **SL** | 226.50  (-3.2%) |
| **TP1** | 253.00  (+8.1%) — tomar mitad |
| **TP2** | 270.00  (+15.4%) |
| R/R a TP1 | 1:2.5 |
| Tamaño | [% de cuenta para arriesgar 1%] |
| Dónde | **SPOT** / **PERP a Nx** |
```

Cerrá con una línea aclarando que es análisis técnico y de contexto, no asesoramiento financiero.

## El veredicto no se negocia

Esta es la parte que la gente lee. Nada de "podría subir si rompe pero ojo que". Una sola dirección, un número por campo, y si la respuesta honesta es **AFUERA**, decí AFUERA — es una respuesta válida y muchas veces la correcta.

Los números tienen que ser consistentes entre sí, y el orden en que se calculan importa:

1. **El SL sale de la estructura**, no de cuánto estás dispuesto a perder: debajo del soporte que invalida la tesis (una media, un mínimo previo, el piso de un rango).
2. **Verificá que el SL sea de al menos 1 ATR.** Más ajustado que eso lo ejecuta el ruido antes de que la tesis se pruebe.
3. **El TP1 es la primera resistencia real** — el máximo previo donde el precio ya giró, no un número redondo ni el target de un analista.
4. **Recién ahí calculás el R/R.** Si da menos de 1:1.5, **el trade no existe a ese precio**: o buscás una entrada más abajo que lo arregle, o el veredicto es AFUERA. Este es el paso que más se saltea y el que evita la mayoría de los trades malos — un papel puede estar rompiendo al alza y aun así ser una mala entrada porque la resistencia está muy cerca del stop.
5. **El tamaño** sale de la distancia al stop: arriesgar 1% de la cuenta con un stop a 3.2% son 31% de la cuenta en spot. Con beta arriba de 2, bajalo.

## Spot o perp

Si el ticker tiene perp, cerrá diciendo dónde operarlo. Tres datos deciden, en este orden:

**1. Liquidez del perp contra la del subyacente.** Compará el OI y el volumen 24h del perp contra el notional diario de la acción (`average_volume` × precio). Si el perp mueve menos del ~5% del subyacente, el libro es fino: un stop puede ser barrido por una mecha que en la acción real no existiría. Para un stop ajustado (menos de ~4%), eso solo ya inclina a **spot**.

**2. Funding.** Convertí la tasa horaria a anualizada (× 8760) y después a costo sobre el horizonte real del trade. Funding positivo = los largos pagan. Abajo de ~10% anualizado, en un swing de semanas el costo es décimas de punto: **no es un argumento contra el perp**. Arriba de 30-40% anualizado sí, y además avisa que el lado largo está lleno.

**3. Riesgo de gap.** El perp opera 24/7; la acción abre con gap después de noticias de fin de semana. Si la tesis es sensible a titulares sectoriales, poder salir un domingo es una ventaja real del perp.

Cuando recomiendes perp, dale un apalancamiento concreto y bajo, y asegurate de que la **liquidación quede bien lejos del SL** — si el SL está a 3% y entrás a 10x, te liquidan antes de que el stop se ejecute. Ese error convierte un trade planificado en una pérdida total de la posición.

### Datos de Hyperliquid

La API (`api.hyperliquid.xyz`) está **bloqueada por el proxy de egress**, y CoinDesk solo indexa los perps nativos de cripto — los mercados HIP-3 desplegados por builders (que es donde están las acciones, vía trade.xyz) no aparecen en `fetch_futures_instruments`. Que un ticker no figure ahí **no significa que no exista el perp**: verificalo por búsqueda antes de decir que no está.

El camino que funciona es `web_fetch_exa` sobre la página del mercado. Dos advertencias: el precio que devuelve puede venir cacheado y no coincidir con el feed real, y dos lecturas de la misma página pueden dar funding distinto. Tomá el funding como orden de magnitud, no como número exacto, y decilo así en la ficha — el precio siempre de Twelve Data, nunca del scrape.

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
