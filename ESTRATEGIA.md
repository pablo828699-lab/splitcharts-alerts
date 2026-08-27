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

## Manual de operación (perps y spot)

El tramo discrecional es una **mesa de operaciones** de 30.000 con reglas, no un
permiso para improvisar.

### El tamaño sale del stop

```
nocional = riesgo_usd / distancia_al_stop
```

Riesgo fijo de **450 USD** (1,5% de la mesa). Con un stop 8% abajo son 5.625 de
nocional; a 3x, 1.875 de margen. **El apalancamiento es un resultado, nunca una
decisión previa.** El tablero trae la calculadora con los topes cargados.

Topes: 3x máximo, margen aislado siempre, liquidación nunca a menos de 25%,
nocional máximo 10.000 por posición y 30.000 en total. Heat máximo 6% de la mesa
(1.800 USD) — cuatro posiciones a riesgo pleno.

### El funding decide el instrumento

Ojo con la calibración: en Binance **0,01%/8h es el valor por defecto, no un
techo**. Leerlo como "extremo" es el error clásico.

| Funding (8h) | Anual | Lectura | Dónde abrir |
|---|---|---|---|
| ≤ 0% | — | Los cortos pagan | Perp (lo más barato para ir largo) |
| 0 – 0,01% | ≤ 11% | Normal (default) | Indistinto |
| 0,01 – 0,03% | 11–33% | Largos amontonándose | Spot |
| > 0,03% | > 33% | Caro | Spot, no abrir largos apalancados |
| > 0,05% | > 55% | Extremo | Evaluar largo spot + corto perp |

Hoy (27-ago-2026): BTC +8,1% anual, ETH +2,2%, SOL +11,0% — **los tres en zona
neutra**. Y el interés abierto de BTC está plano (+1,2% en 30 días) mientras el
precio subió 23%: el rally fue de spot, no de apalancamiento. Es una subida más
sana que una empujada por leverage, y hoy no hay penalización por usar perps.

### Setups válidos

Sólo se opera lo que entra en uno de estos tres:

1. **Retroceso en tendencia** — sobre la media de 200 días, retroceso a la de 50
   o a un techo que pasó a piso, RSI diario 40–50. Stop bajo el mínimo del retroceso.
2. **Ruptura de rango con volumen** — cierre sobre el máximo de 20 días con
   volumen > 1,5x el promedio. Stop de vuelta adentro. Spot: las rupturas fallan
   seguido y el apalancamiento castiga el reintento.
3. **Reversión desde extremo** — RSI diario < 25, funding negativo y precio en un
   escalón cargado. Spot, sólo a favor de la tesis del ciclo.

### Qué instrumento para qué

| Uso | Instrumento | Nunca |
|---|---|---|
| Exposición direccional del ciclo | Spot | — |
| Swing con stop definido | Spot, o perp ≤3x con funding neutro o negativo | Con funding cargado |
| Cobertura del núcleo | Corto en perp | Más del 30% del núcleo |
| Cosecha de funding | Largo spot + corto perp | Si obliga a mover el núcleo |

**Los cortos son sólo cobertura.** Dentro de una tesis alcista de ciclo no se
especula a la baja. La cobertura del núcleo se activa únicamente si se dispara la
invalidación (cierre mensual bajo 46.000) y permite bajar exposición sin vender
el núcleo ni mover la billetera fría.

### Salidas

- A **1,5R** se cierra la mitad y el stop va a punto de entrada: la operación ya
  no puede perder.
- El resto acompaña con stop bajo la media de 20 días, a cierre diario.
- **Stop temporal**: si a los 15 días no se movió 1R, se cierra. El capital
  quieto también cuesta.
- Nunca se corre un stop hacia abajo. Nunca se promedia a la baja una perdedora.

### Cortacircuitos

- 3 pérdidas seguidas → la mesa para 5 días.
- −10% en un mes → mitad de tamaño hasta hacer un nuevo máximo de capital.
- −30% → se apaga por un trimestre.


## Saldos on-chain (solo lectura)

El monitor puede leer los saldos reales de las billeteras EVM y avisar cuando se
mueven. Nunca toca claves: con una dirección alcanza para consultar, y el módulo
no firma ni arma transacciones.

**Las direcciones no van en `portfolio.json`.** Este repo es público y el
historial de git es permanente. Viven en:

- `wallets.local.json` — ignorado por git, para correr localmente.
- Secret `WALLET_ADDRESSES` — el mismo JSON, para GitHub Actions.

```json
{
  "publicar_saldos": false,
  "direcciones": [
    { "addr": "0x…", "wallet": "hot-evm", "nota": "operativa" }
  ]
}
```

`publicar_saldos: false` (por defecto) mantiene los importes **fuera** de
`docs/data.json`, que se publica. Los números viajan sólo por Telegram. Ponerlo
en `true` sólo tiene sentido si el repo y el sitio pasan a ser privados.

Se leen ETH/BNB nativos y USDC, USDT, WBTC/BTCB y WETH en Ethereum, Base,
Arbitrum y BSC, contra RPC públicos con respaldo. Ojo con los decimales: USDT en
BSC tiene 18, no 6.

Los saldos se refrescan **como mucho cada 30 minutos** (`WALLET_TTL`): no cambian
cada 5 minutos y cada refresco son decenas de llamadas a RPC gratuitos.

### Alerta de movimiento

Compara **cantidades**, no valor en USD — el valor se mueve con el mercado todo
el tiempo, pero un cambio de cantidad significa que hubo una transacción:

| Alerta | Cuándo |
|---|---|
| 👛 Movimiento | Cambió la cantidad de un token en alguna billetera. |

Sirve para confirmar un barrido a frío y, sobre todo, para enterarte de un
movimiento que no hiciste vos.


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
| ⚖️ Funding | El funding de un activo cambia de banda (cambia dónde conviene abrir). |

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
