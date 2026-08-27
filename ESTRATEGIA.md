# Cartera 300k — manual de operación

Estrategia escrita como **datos** (`portfolio.json`), evaluada por un **motor**
(`portfolio_monitor.py`) y publicada como **tablero** (`docs/`). Cambiar la
estrategia es editar el JSON: el motor y el tablero se adaptan solos.

## Foto del mercado que ancla todo (27-ago-2026)

| | Precio | Máximo de ciclo | Mínimo de ciclo | Desde ATH | Desde mínimo |
|---|---|---|---|---|---|
| BTC | 79.310 | 126.287 *(oct-25)* | 57.739 *(jun-26)* | −37% | +37% |
| ETH | 2.493 | 4.956 *(ago-25)* | 1.505 *(jun-26)* | −50% | +66% |
| SOL | 105 | 295 *(ene-25)* | 60,1 *(jun-26)* | −64% | +75% |
| BNB | 708 | 1.375 *(oct-25)* | 537 *(jun-26)* | −49% | +32% |

Halving anterior: abr-2024. Próximo: ~abr-2028. Estamos al ~59% del recorrido
entre ambos.

> **Las órdenes de DCA en 55.000 y 50.000 nunca se ejecutaron.** El mínimo del
> ciclo fue **57.739** en junio-2026: quedaron 4,6% por debajo del piso real, y
> hoy el precio está 37% más arriba. Los escalones de este repo están
> re-anclados a ese mínimo, no a números redondos.

## Reparto de los 300k

| Tramo | USD | Función |
|---|---|---|
| Núcleo BTC | 100.000 | No se toca. Frío. No firma contratos. |
| DCA calendario | 60.000 | Anti-timing: 24 compras quincenales de 2.500. |
| Escalones | 55.000 | Munición para caídas, en órdenes límite ya cargadas. |
| Beta / rotación | 55.000 | El tramo que busca el múltiplo del ciclo. |
| Discrecional | 30.000 | Swings y lo que levante el escáner. Acotado a propósito. |

115.000 (DCA + escalones) arrancan en stablecoins y se convierten con el tiempo.
No es reserva conservadora: es capital **comprometido con reglas**, colocado así
porque entrar de golpe justo después de un rebote del 37% es mala ejecución.

## Las cinco billeteras

Separadas por **lo que pueden firmar**, no por lo que guardan:

1. **Fría BTC** — núcleo. Nunca toca una dApp.
2. **Fría alts** — ETH/SOL/BNB de largo plazo. Dispositivo o cuenta aparte.
3. **Caliente EVM** — la que asumís que se puede vaciar.
4. **Caliente Solana** — igual, separada por cadena.
5. **Exchange** — lugar de ejecución, no de custodia.

La regla que justifica que sean 5 y no 1 ni 8: *una billetera que firma
contratos nunca comparte dispositivo con el núcleo*.

## Cómo corre

```
cron-job.org  ──(repository_dispatch cada 5 min)──►  GitHub Actions
                                                          │
                        telegram_alerts.py --once  ◄──────┤
                        portfolio_monitor.py --once ◄─────┤
                        build_dashboard.py         ◄──────┘
                                   │
                    commit de docs/data.json a main
                                   │
                          Netlify redespliega  ──►  tablero online
```

GitHub Actions es el backend (cron + cómputo), el repo es la base de datos
(JSON versionado, con historial gratis) y Netlify es sólo el CDN.
**Render no hace falta**: sólo tendría sentido para sondeo sub-minuto o una API
real, y a cambio habría que pagar un servicio siempre encendido.

### Puesta en marcha

1. **Netlify** → *Add new site* → *Import from Git* → este repo.
   `netlify.toml` ya fija `publish = "docs"` y desactiva el caché de `data.json`.
   No configurar build command.
2. **Secrets** en GitHub → *Settings* → *Secrets and variables* → *Actions*:
   `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` (los mismos de las alertas).
3. Listo. Cada corrida del workflow actualiza el tablero.

### Uso local

```bash
pip install requests "numpy<2" pandas ta yfinance

python portfolio_monitor.py --once --dry      # sin mandar Telegram
python portfolio_monitor.py --once            # con alertas
python build_dashboard.py                     # empotra el respaldo en el HTML

# probar escenarios sin esperar al mercado:
python portfolio_monitor.py --once --dry --fake-prices BTCUSDT=59000,ETHUSDT=1850
```

Abrir `docs/index.html` con doble clic funciona: el `fetch` de `data.json` falla
por CORS y la página cae al respaldo empotrado por `build_dashboard.py`.

## Qué avisa por Telegram

| Alerta | Cuándo |
|---|---|
| 🎯 Escalón tocado | El precio toca un peldaño — incluye la mecha entre corridas. |
| 💰 Toma de ganancias | BTC alcanza un nivel de `rules.take_profit`. |
| 🚨 Invalidación | BTC pierde el escalón más profundo (46.000). |

Cada una dispara **una sola vez**: el estado vive en `portfolio_state.json`, que
el workflow commitea junto con el tablero.

## Editar la estrategia

Todo sale de `portfolio.json`:

- mover un escalón → `ladders`
- cambiar el reparto → `sleeves[].usd`
- otra regla de salida → `rules.take_profit`
- otra billetera → `wallets`

El tablero se redibuja solo en la siguiente corrida. Los importes de `sleeves`
deben sumar 200.000 y los de `ladders` deben cuadrar con el tramo de escalones.

---

Esto es una herramienta de seguimiento de una estrategia propia, no
asesoramiento financiero. Los niveles son decisiones tomadas de antemano para no
tener que tomarlas en caliente; revisalos cuando cambie la tesis, no cuando
cambie el precio.
