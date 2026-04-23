# Scrapling Project — Documentación Completa

> Proyecto creado para scrapear cualquier sitio web con una sola URL.
> Incluye extracción estructurada, crawling profundo, datos de negocio,
> monitoreo de cambios e intercepción de red.

---

## Tabla de Contenidos

1. [Setup inicial](#1-setup-inicial)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Estrategias de fetching](#3-estrategias-de-fetching)
4. [Comandos básicos](#4-comandos-básicos)
5. [Comandos avanzados A–E](#5-comandos-avanzados-ae)
6. [Caso real: CMCSA Yahoo Finance](#6-caso-real-cmcsa-yahoo-finance)
7. [Referencia de selectores](#7-referencia-de-selectores)
8. [Formatos de exportación](#8-formatos-de-exportación)
9. [Errores comunes y soluciones](#9-errores-comunes-y-soluciones)

---

## 1. Setup inicial

> Hacer esto una sola vez antes de usar el proyecto.

```bash
# Ir a la carpeta del proyecto
cd /Users/samaydeveloper/Documents/scraping

# Instalar dependencias de Python
python3 -m pip install -r requirements.txt

# Instalar browsers (Playwright + Camoufox)
python3 main.py install

# O instalar manualmente si el comando anterior falla
python3 -m playwright install chromium
python3 -m camoufox fetch
```

### Verificar que todo funciona

```bash
python3 main.py --help
```

Deberías ver todos los comandos disponibles sin errores.

---

## 2. Estructura del proyecto

```
scraping/
├── main.py                  ← Punto de entrada (todos los comandos)
├── config.yaml              ← Configuración global
├── requirements.txt         ← Dependencias
│
├── scraper/
│   ├── smart_fetcher.py     ← Elige HTTP / Stealth / Dynamic automáticamente
│   ├── extractor.py         ← Aplica selectores CSS y XPath
│   ├── full_extractor.py    ← Extracción estructurada completa (Comando A)
│   ├── deep_crawler.py      ← Crawl profundo siguiendo links (Comando B)
│   ├── business_extractor.py← Datos de negocio: precios, equipo, FAQs (Comando C)
│   ├── monitor.py           ← Snapshots y detección de cambios (Comando D)
│   ├── network_interceptor.py← Intercepción de APIs y red (Comando E)
│   └── exporter.py          ← Guarda resultados en JSON/JSONL/CSV
│
├── output/                  ← Resultados de cada scrape
├── snapshots/               ← Historial de snapshots para monitoreo
├── profiles/                ← Reglas de extracción guardadas
└── crawl_data/              ← Checkpoints de crawls (pause/resume)
```

---

## 3. Estrategias de fetching

El tool tiene 3 modos de conexión. Con `auto` lo detecta solo.

| Estrategia | Cuándo usar | Velocidad |
|---|---|---|
| `auto` | Dejar que el tool decida (recomendado) | Varía |
| `http` | Sitios simples, blogs, datos públicos sin JS | Muy rápido |
| `stealth` | Cloudflare, LinkedIn, sitios con anti-bot | Lento |
| `dynamic` | React, Angular, SPAs, Yahoo Finance, precios en vivo | Medio |

> **Regla práctica:** Si el sitio carga datos con JavaScript (como precios de acciones, dashboards, apps modernas) → usar `dynamic`. Si tiene Cloudflare → `stealth`.

---

## 4. Comandos básicos

### `scrape` — extracción interactiva

```bash
python3 main.py scrape https://cualquier-sitio.com
```

Te hace preguntas:
1. Estrategia (Enter para `auto`)
2. Nombre del campo (ej: `titulo`)
3. Selector CSS o XPath (ej: `h1::text`)
4. ¿Múltiples valores? (y/n)
5. Repetir para más campos, Enter en blanco para terminar

**Sin preguntas (flags automáticos):**

```bash
# Extrae metadata + links + imágenes sin preguntar nada
python3 main.py scrape https://sitio.com --meta --links --images

# Forzar estrategia dynamic
python3 main.py scrape https://sitio.com --meta --links --strategy dynamic

# Exportar en todos los formatos (json + jsonl + csv)
python3 main.py scrape https://sitio.com --meta --output all

# Guardar las reglas de extracción para reutilizar
python3 main.py scrape https://sitio.com --save-profile mi-perfil

# Usar reglas guardadas anteriormente
python3 main.py scrape https://sitio.com --load-profile mi-perfil
```

---

### `extract` — extracción rápida sin preguntas

```bash
# Extraer con selector CSS
python3 main.py extract https://sitio.com output/resultado.json --css "h1::text"

# Extraer con XPath
python3 main.py extract https://sitio.com output/resultado.json --xpath "//h1/text()"

# Con estrategia dynamic (para sitios con JavaScript)
python3 main.py extract https://sitio.com output/resultado.json --strategy dynamic --css ".precio::text"
```

---

### `spider` — crawl con paginación

```bash
# Crawl básico siguiendo paginación automáticamente
python3 main.py spider https://sitio.com

# Limitar a 10 páginas
python3 main.py spider https://sitio.com --max-pages 10

# Con delay entre requests (para no ser bloqueado)
python3 main.py spider https://sitio.com --delay 1.5

# Reanudar crawl pausado
python3 main.py spider https://sitio.com --resume

# Con proxies (archivo con un proxy por línea)
python3 main.py spider https://sitio.com --proxies proxies.txt
```

---

### `profiles` — ver perfiles guardados

```bash
python3 main.py profiles
```

---

### `shell` — REPL interactivo de Scrapling

```bash
python3 main.py shell
```

---

## 5. Comandos avanzados A–E

### A) `full` — Extracción estructurada completa

Extrae **todo** lo que tiene la página: headings, secciones, JSON-LD,
formularios, botones, tablas, links de navegación, redes sociales.

```bash
python3 main.py full https://sitio.com

# Con estrategia dynamic (para SPAs)
python3 main.py full https://sitio.com --strategy dynamic

# Con monitoreo de cambios activado
python3 main.py full https://sitio.com --monitor
```

**Qué extrae:**
- `title` — título de la página
- `headings` — todos los H1/H2/H3/H4
- `sections` — bloques de contenido con su heading
- `paragraphs` — todos los párrafos con más de 20 caracteres
- `navigation` — links del menú de navegación
- `links` — todos los links de la página
- `images` — todas las imágenes con src y alt
- `forms` — formularios con sus campos
- `buttons_cta` — botones y llamadas a la acción
- `tables` — tablas HTML convertidas a datos
- `social_links` — links a redes sociales
- `structured_data` — datos JSON-LD (schema.org)
- `full_text` — todo el texto visible de la página

---

### B) `crawl` — Crawl profundo

Sigue **todos los links internos** del sitio automáticamente y extrae
datos de cada página. Construye un mapa completo del sitio.

```bash
# Crawl básico (máx 20 páginas por defecto)
python3 main.py crawl https://sitio.com

# Hasta 50 páginas
python3 main.py crawl https://sitio.com --max-pages 50

# También extrae datos de negocio en cada página
python3 main.py crawl https://sitio.com --business

# Exportar en todos los formatos
python3 main.py crawl https://sitio.com --output all
```

**Qué produce:**
- `sitemap` — lista de todas las páginas visitadas con título y links encontrados
- `pages` — datos extraídos de cada URL
- `stats` — total de páginas, errores, duración

---

### C) `business` — Datos de negocio

Extrae información estructurada de negocio usando heurísticas inteligentes.

```bash
python3 main.py business https://empresa.com

# Con strategy dynamic para sitios con JS
python3 main.py business https://empresa.com --strategy dynamic
```

**Qué extrae:**
- `contact` — emails, teléfonos, horarios
- `pricing` — precios y planes encontrados
- `services` — servicios u offerings
- `team` — miembros del equipo con rol y foto
- `testimonials` — testimonios y reviews
- `faqs` — preguntas frecuentes
- `locations` — direcciones y ubicaciones
- `stats` — métricas clave (números destacados)

**Ejemplo real (samayhealth.com):**
```bash
python3 main.py business https://www.samayhealth.com --strategy dynamic
```

---

### D) `monitor` — Monitoreo de cambios

Guarda un snapshot de la página y en cada corrida detecta qué cambió:
nuevos links, headings eliminados, cambios de precio, variaciones de texto.

```bash
# Primera corrida → guarda snapshot base
python3 main.py monitor https://sitio.com --strategy dynamic

# Corridas posteriores → compara con snapshot anterior
python3 main.py monitor https://sitio.com --strategy dynamic

# Ver todos los snapshots guardados
python3 main.py monitor https://sitio.com --list
```

**Qué detecta entre snapshots:**
- Título cambiado
- Headings nuevos o eliminados
- Links nuevos o eliminados
- Imágenes nuevas o eliminadas
- Cambios de precio
- Variación de palabras (+/- 50 palabras)

**Snapshots se guardan en:** `snapshots/<dominio>__<timestamp>.json`

---

### E) `intercept` — Interceptar red

Abre un browser real, intercepta **todas las llamadas de red** que hace
el sitio y captura: APIs XHR/fetch, respuestas JSON, operaciones GraphQL,
headers de autenticación, WebSockets, cookies.

```bash
# Intercepción básica (solo llamadas API)
python3 main.py intercept https://sitio.com

# Esperar más tiempo para capturar más requests
python3 main.py intercept https://sitio.com --wait 10

# Capturar absolutamente todas las requests
python3 main.py intercept https://sitio.com --all

# Ver el browser mientras corre (no headless)
python3 main.py intercept https://sitio.com --no-headless
```

**Qué captura:**
- `api_calls` — llamadas XHR/fetch con método, URL y body
- `json_responses` — respuestas JSON de APIs
- `graphql_operations` — queries y mutations de GraphQL
- `auth_headers` — tokens de autenticación encontrados
- `websocket_messages` — mensajes de WebSocket
- `cookies` — cookies de la sesión
- `stats` — resumen total de requests

---

### ALL) `deep` — Los 5 modos a la vez

Ejecuta A + B + C + D + E en una sola corrida. Genera múltiples archivos.

```bash
python3 main.py deep https://sitio.com

# Con más páginas en el crawl
python3 main.py deep https://sitio.com --max-pages 20

# Exportar todo en todos los formatos
python3 main.py deep https://sitio.com --output all
```

---

## 6. Caso real: CMCSA Yahoo Finance

Este es el flujo completo que usamos para analizar el movimiento de precio
de CMCSA (Comcast) después del reporte de Q1 2026.

### Paso 1 — Interceptar las APIs de Yahoo Finance

```bash
python3 main.py intercept "https://finance.yahoo.com/quote/CMCSA/" --wait 5
```

Yahoo Finance carga precios en vivo vía XHR. Este comando capturó:
- El endpoint `v7/finance/quote` con precio real de CMCSA
- El endpoint `v8/finance/chart/CMCSA` con datos del gráfico
- 117 requests en total, 41 respuestas JSON

**Datos capturados del endpoint de precio:**
```json
{
  "symbol": "CMCSA",
  "regularMarketPrice": 31.39,
  "regularMarketChange": 2.02,
  "regularMarketChangePercent": 6.877761,
  "regularMarketPreviousClose": 29.37,
  "preMarketPrice": 30.53,
  "preMarketChangePercent": 3.9496078,
  "regularMarketDayHigh": 31.62,
  "regularMarketDayLow": 30.40,
  "regularMarketVolume": 10101186,
  "fiftyTwoWeekHigh": 34.358,
  "fiftyTwoWeekLow": 24.133
}
```

---

### Paso 2 — Extraer precio con selector CSS

```bash
python3 main.py extract "https://finance.yahoo.com/quote/CMCSA/" output/cmcsa.json \
  --strategy dynamic \
  --css "fin-streamer[data-field='regularMarketPrice']"
```

> **Nota:** Este selector captura todos los `fin-streamer` con ese atributo,
> incluyendo otros instrumentos en la página. El precio real de CMCSA
> está en el primer valor: `31.39`.

---

### Paso 3 — Scrape completo de la página

```bash
python3 main.py scrape "https://finance.yahoo.com/quote/CMCSA/" \
  --strategy dynamic --meta --links
```

---

### Paso 4 — Snapshot para monitoreo futuro

```bash
python3 main.py monitor "https://finance.yahoo.com/quote/CMCSA/" --strategy dynamic
```

Guardado en: `snapshots/finance_yahoo_com__quote_CMCSA__<timestamp>.json`

---

### Paso 5 — Análisis de analistas

```bash
python3 main.py full "https://finance.yahoo.com/quote/CMCSA/analysis" \
  --strategy dynamic
```

---

### Selectores útiles para Yahoo Finance

| Dato | Selector CSS |
|---|---|
| Precio actual | `fin-streamer[data-field="regularMarketPrice"]::attr(value)` |
| Cambio ($) | `fin-streamer[data-field="regularMarketChange"]::attr(value)` |
| Cambio (%) | `fin-streamer[data-field="regularMarketChangePercent"]::attr(value)` |
| After-hours precio | `fin-streamer[data-field="postMarketPrice"]::attr(value)` |
| After-hours cambio | `fin-streamer[data-field="postMarketChange"]::attr(value)` |
| Volumen | `fin-streamer[data-field="regularMarketVolume"]::attr(value)` |

---

### Conclusión del análisis CMCSA Q1 2026

| Métrica | Valor | Señal |
|---|---|---|
| Precio el día del reporte | $31.39 | — |
| Cierre día anterior | $29.37 | — |
| Movimiento total del día | +$2.02 (+6.88%) | ✅ Fuerte |
| Pre-market (antes apertura) | +3.95% | ✅ Anticipado |
| Razón del alza | Super Bowl + Olimpiadas ad revenue | ✅ Beat estimados |
| EPS 2026 vs 2025 | -18% | ⚠️ Cae |
| Analistas bajaron estimados (30d) | 10 de 23 | ⚠️ Cautela |
| Crecimiento ingresos Q2 2026 | -2.83% | ⚠️ Negativo |
| Recuperación esperada | 2027 (+8.57% EPS) | 🟡 Futuro |

---

## 7. Referencia de selectores

### CSS Selectors

| Qué quieres extraer | Selector |
|---|---|
| Texto dentro de `<h1>` | `h1::text` |
| Texto de todos los `<p>` | `p::text` + multiple=yes |
| Atributo href de un link | `a::attr(href)` |
| Elemento por clase | `.mi-clase::text` |
| Elemento por ID | `#mi-id::text` |
| Atributo específico | `img::attr(src)` |
| Elemento anidado | `.card .titulo::text` |
| Atributo data | `[data-field="price"]::attr(value)` |

### XPath

| Qué quieres extraer | Selector |
|---|---|
| Texto de H1 | `//h1/text()` |
| Todos los links | `//a/@href` |
| Elemento con clase | `//*[@class="precio"]/text()` |
| Elemento con texto específico | `//*[contains(text(),"Precio")]` |
| Segundo elemento de lista | `//ul/li[2]/text()` |

---

## 8. Formatos de exportación

Todos los resultados se guardan en `output/` con nombre:
`<dominio>_<fecha_hora>.json`

```bash
# Solo JSON (default)
python3 main.py scrape https://sitio.com

# Solo JSONL (una línea por item, bueno para big data)
python3 main.py scrape https://sitio.com --output jsonl

# Solo CSV
python3 main.py scrape https://sitio.com --output csv

# Todos los formatos a la vez
python3 main.py scrape https://sitio.com --output all
```

---

## 9. Errores comunes y soluciones

### `command not found: python`
```bash
# Usar python3 en lugar de python
python3 main.py scrape https://sitio.com

# O crear alias permanente
echo 'alias python=python3' >> ~/.zshrc && source ~/.zshrc
```

---

### `TimeoutError: Timeout 30000ms exceeded`

El sitio nunca termina de cargar (requests en vivo continuos como Yahoo Finance).

```bash
# Solución: NO usar network_idle, ya está corregido en smart_fetcher.py
# Simplemente usa --strategy dynamic directamente
python3 main.py scrape https://finance.yahoo.com --strategy dynamic
```

---

### `ImportError: cannot import name 'DynamicFetcher'`

La versión instalada de Scrapling usa nombres diferentes.

| Nombre viejo (documentación) | Nombre real instalado |
|---|---|
| `DynamicFetcher` | `PlayWrightFetcher` |
| `StealthyFetcher` | `StealthyFetcher` ✅ |
| `FetcherSession` | `Fetcher` ✅ |

Esto ya está corregido en `smart_fetcher.py`. No requiere acción.

---

### `AttributeError: 'Adaptors' object has no attribute 'getall'`

La API de Scrapling usa `get_all()` no `getall()`.

```python
# Incorrecto
page.css(".clase").getall()

# Correcto
page.css(".clase").get_all()
```

Esto ya está corregido en todos los archivos del proyecto.

---

### `TypeError: Object of type Adaptor is not JSON serializable`

Cuando `.css()` devuelve elementos en vez de texto. Agregar `::text` al selector.

```bash
# Incorrecto
--css "h1"

# Correcto
--css "h1::text"
```

---

### `No module named scrapling.__main__`

Scrapling no tiene módulo `__main__`. Instalar browsers directamente:

```bash
python3 -m playwright install chromium
python3 -m camoufox fetch
```

---

### `Executable doesn't exist` (Playwright)

```bash
python3 -m playwright install chromium
```

---

### Sitio devuelve poco contenido (solo metadata vacía)

El sitio necesita JavaScript para cargar. Usar `--strategy dynamic`.

```bash
# Antes (no funciona para SPAs)
python3 main.py scrape https://app-react.com --meta

# Correcto
python3 main.py scrape https://app-react.com --meta --strategy dynamic
```

---

## Flujo recomendado para un sitio nuevo

```bash
# 1. Ver qué APIs usa el sitio
python3 main.py intercept https://nuevo-sitio.com --wait 8

# 2. Extracción completa estructurada
python3 main.py full https://nuevo-sitio.com --strategy dynamic

# 3. Datos de negocio
python3 main.py business https://nuevo-sitio.com --strategy dynamic

# 4. Guardar snapshot base para monitoreo
python3 main.py monitor https://nuevo-sitio.com --strategy dynamic

# 5. (Opcional) Crawl profundo de todo el sitio
python3 main.py crawl https://nuevo-sitio.com --max-pages 30
```
