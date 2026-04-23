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
7. [LinkedIn — Health Tech Scraping](#7-linkedin--health-tech-scraping)
8. [Referencia de selectores](#8-referencia-de-selectores)
9. [Formatos de exportación](#9-formatos-de-exportación)
10. [Errores comunes y soluciones](#10-errores-comunes-y-soluciones)

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

## 7. LinkedIn — Health Tech Scraping

Cuatro comandos especializados para extraer datos de LinkedIn con foco en
**lead generation**, **market research** y **recruiting** en el sector health tech.

---

### Gratuitos — requieren tu cuenta de LinkedIn

> Correr `linkedin-login` una sola vez y los demás comandos funcionan solos.

| Comando | Qué hace |
|---|---|
| `linkedin-login` | Inicia sesión y guarda cookies para los demás comandos |
| `linkedin-companies` | Busca empresas health tech por keyword, industria y ubicación |
| `linkedin-people` | Busca personas, filtra por título y seniority, pipeline de recruiting |

### De pago — requieren API key de Proxycurl

> Registrarse en [nubela.co/proxycurl](https://nubela.co/proxycurl) → copiar API key → agregar `PROXYCURL_API_KEY=...` en `.env`.
> Costo: ~$0.01 USD por crédito. Tienen créditos gratuitos al registrarse.
> Ventaja: sin browser, sin riesgo de bloqueo, incluye email/teléfono y datos de funding.

| Comando | Qué hace |
|---|---|
| `linkedin-proxycurl company-search` | Busca empresas por keyword vía API |
| `linkedin-proxycurl person-search` | Busca personas por keyword y título vía API |
| `linkedin-proxycurl company` | Perfil completo de una empresa por URL |
| `linkedin-proxycurl person` | Perfil completo de una persona por URL |
| `linkedin-proxycurl employees` | Lista empleados de una empresa |

### ¿Cuál usar?

| Situación | Comando recomendado |
|---|---|
| Empezar rápido, sin costo | `linkedin-companies` / `linkedin-people` |
| LinkedIn bloquea o pide captcha | `linkedin-proxycurl` |
| Necesito email o teléfono del contacto | `linkedin-proxycurl person-search --enrich` |
| Necesito datos de funding de empresas | `linkedin-proxycurl company-search --funding` |
| Buscar empleados dentro de una empresa | `linkedin-proxycurl employees` |
| Volumen alto (+500 perfiles/día) | `linkedin-proxycurl` |

---

---

### Paso 0 — Setup inicial (hacer una sola vez)

Copiar el archivo de variables de entorno:

```bash
cp .env.example .env
```

El archivo `.env` es donde viven todas las credenciales. Nunca se sube al repo (está en `.gitignore`).

---

### `linkedin-login` — guardar sesión

Abre un browser, hace login en LinkedIn y guarda las cookies en `.env` y `cookies/linkedin.json`
para que todos los demás comandos las usen automáticamente.

```bash
# Opción A — login automático (recomendado)
python3 main.py linkedin-login --email tu@email.com --password tupassword

# Opción B — login manual (tú haces login en el browser que se abre)
python3 main.py linkedin-login
```

Después de correr esto una vez **no necesitas volver a hacerlo** mientras la sesión esté activa
(~1 año). Si LinkedIn te pide verificación de seguridad durante el login, el programa te avisa
para que la completes en el browser y luego presiones Enter.

**Flags disponibles:**

| Flag | Corto | Descripción | Default |
|---|---|---|---|
| `--email` | `-e` | Email de LinkedIn | — |
| `--password` | `-p` | Password de LinkedIn | — |
| `--save / --no-save` | | Guardar cookies en `.env` y `cookies/linkedin.json` | `--save` |

> **Alternativa sin login:** puedes poner la cookie directamente en `.env`:
> ```env
> LINKEDIN_LI_AT=AQEDARxxxxxxxxxxxxxxxxxxxxxxxx
> ```
> Obtén el valor desde Chrome → DevTools → Application → Cookies → `linkedin.com` → `li_at`.

---

### `linkedin-companies` — buscar empresas

Busca empresas en LinkedIn usando la API interna Voyager (intercepción de red).
Útil para **market research**: mapear competidores, encontrar empresas para partnerships o inversión.

```bash
# Básico
python3 main.py linkedin-companies "digital health"
python3 main.py linkedin-companies "telehealth"
python3 main.py linkedin-companies "salud digital"

# Por ubicación
python3 main.py linkedin-companies "digital health" --location usa
python3 main.py linkedin-companies "telehealth" --location mexico
python3 main.py linkedin-companies "health tech" --location latam
python3 main.py linkedin-companies "mental health" --location colombia

# Por industria (se pueden combinar con coma)
python3 main.py linkedin-companies "biotech" --industries biotechnology
python3 main.py linkedin-companies "medtech" --industries biotechnology,medical_devices
python3 main.py linkedin-companies "health app" --industries hospital_healthcare,health_wellness_fitness

# Cuántos resultados
python3 main.py linkedin-companies "digital health" --count 50

# Enriquecer cada empresa con perfil completo (website, tamaño, descripción, fundación)
python3 main.py linkedin-companies "health tech" --enrich

# Exportar en distintos formatos
python3 main.py linkedin-companies "health tech" --output csv
python3 main.py linkedin-companies "health tech" --output all   # json + csv + jsonl

# Ejemplo completo
python3 main.py linkedin-companies "mental health app" \
  --industries mental_health,health_wellness_fitness \
  --location latam \
  --count 50 \
  --enrich \
  --output csv
```

**Flags disponibles:**

| Flag | Corto | Descripción | Default |
|---|---|---|---|
| `--industries` | `-i` | Industrias separadas por coma (ver tabla abajo) | todas las health |
| `--location` | `-l` | Ubicación geográfica (ver tabla abajo) | sin filtro |
| `--count` | `-n` | Número de empresas a buscar | `25` |
| `--enrich` | `-e` | Fetch perfil completo de cada empresa | `false` |
| `--output` | `-o` | Formato: `json` \| `jsonl` \| `csv` \| `all` | `json` |
| `--headless / --no-headless` | | Correr browser en segundo plano | `--no-headless` |

**Valores de `--location`:**

| Clave | País / Región |
|---|---|
| `usa` | Estados Unidos |
| `latam` | Latinoamérica |
| `mexico` | México |
| `colombia` | Colombia |
| `brazil` | Brasil |
| `uk` | Reino Unido |
| `spain` | España |

**Valores de `--industries`:**

| Clave | Industria en LinkedIn |
|---|---|
| `hospital_healthcare` | Hospital & Health Care |
| `health_wellness_fitness` | Health, Wellness and Fitness |
| `biotechnology` | Biotechnology |
| `pharmaceuticals` | Pharmaceuticals |
| `medical_devices` | Medical Devices |
| `mental_health` | Mental Health Care |
| `medical_practice` | Medical Practice |
| `research` | Research |

**Campos en el output:**

| Campo | Siempre | Con `--enrich` |
|---|---|---|
| `name` | ✅ | ✅ |
| `linkedin_url` | ✅ | ✅ |
| `company_id` | ✅ | ✅ |
| `industry_size` | ✅ | ✅ |
| `location` | ✅ | ✅ |
| `description` | | ✅ |
| `website` | | ✅ |
| `employee_count` | | ✅ |
| `headquarters` | | ✅ |
| `founded` | | ✅ |
| `specialties` | | ✅ |
| `followers` | | ✅ |

---

### `linkedin-people` — buscar personas / recruiting

Busca profesionales de health tech. Útil para **recruiting** (CTOs, ingenieros, médicos tech)
y **lead generation** (founders, decision-makers en empresas target).

```bash
# Básico
python3 main.py linkedin-people "digital health"
python3 main.py linkedin-people "telemedicine"

# Por título de trabajo
python3 main.py linkedin-people "digital health" --titles "CTO,Founder,CEO"
python3 main.py linkedin-people "health tech" --titles "VP Engineering,Director of Engineering"
python3 main.py linkedin-people "healthtech" --titles "Product Manager,CPO"
python3 main.py linkedin-people "telemedicine" --titles "Software Engineer,Backend Engineer"

# Por seniority (sin especificar títulos exactos)
python3 main.py linkedin-people "digital health" --seniority "c_suite,vp"
python3 main.py linkedin-people "health tech" --seniority "director,manager"
python3 main.py linkedin-people "health app" --seniority "senior"

# Por ubicación
python3 main.py linkedin-people "digital health" --location usa
python3 main.py linkedin-people "salud digital" --location mexico
python3 main.py linkedin-people "health tech" --location latam

# Cuántos resultados
python3 main.py linkedin-people "digital health" --count 50

# Enriquecer perfiles (agrega experiencia completa, empresa actual, resumen)
python3 main.py linkedin-people "health tech" --titles "CTO" --enrich

# Pipeline completo de recruiting (busca + enriquece + ordena por score de seniority)
python3 main.py linkedin-people "digital health" --recruiting
python3 main.py linkedin-people "telehealth" --recruiting --count 30 --output csv

# Exportar
python3 main.py linkedin-people "health tech" --output csv
python3 main.py linkedin-people "health tech" --output all

# Ejemplo completo
python3 main.py linkedin-people "digital health" \
  --titles "CTO,Founder,CEO" \
  --seniority "c_suite,vp" \
  --location usa \
  --count 40 \
  --output csv
```

**Flags disponibles:**

| Flag | Corto | Descripción | Default |
|---|---|---|---|
| `--titles` | `-t` | Títulos separados por coma | `CTO,Founder,CEO` |
| `--seniority` | `-s` | Nivel de seniority (ver tabla abajo) | `c_suite,vp,director` |
| `--location` | `-l` | Ubicación geográfica (mismas claves que companies) | sin filtro |
| `--count` | `-n` | Número de perfiles a buscar | `25` |
| `--enrich` | `-e` | Fetch perfil completo de cada persona | `false` |
| `--recruiting` | | Pipeline completo: busca + enriquece + score | `false` |
| `--output` | `-o` | Formato: `json` \| `jsonl` \| `csv` \| `all` | `json` |
| `--headless / --no-headless` | | Correr browser en segundo plano | `--no-headless` |

**Valores de `--seniority`:**

| Clave | Nivel |
|---|---|
| `c_suite` | CEO, CTO, CMO, CFO, etc. |
| `vp` | Vice President |
| `director` | Director |
| `manager` | Manager |
| `senior` | Senior |
| `entry` | Entry level |

**`outreach_priority` score** (calculado con `--recruiting`):

| Score | Roles |
|---|---|
| 10 | CEO, CTO, Founder, Co-Founder |
| 9 | COO, CPO, President |
| 8 | CMO, CIO, VP |
| 7 | Director, Head of |
| 6 | Lead, Principal |
| 5 | Senior |

**Campos en el output:**

| Campo | Siempre | Con `--enrich` | Con `--recruiting` |
|---|---|---|---|
| `name` | ✅ | ✅ | ✅ |
| `headline` | ✅ | ✅ | ✅ |
| `location` | ✅ | ✅ | ✅ |
| `linkedin_url` | ✅ | ✅ | ✅ |
| `snippet` | ✅ | ✅ | ✅ |
| `summary` | | ✅ | ✅ |
| `current_title` | | ✅ | ✅ |
| `current_company` | | ✅ | ✅ |
| `connections` | | ✅ | ✅ |
| `experience` | | ✅ | ✅ |
| `outreach_priority` | | | ✅ |

---

### `linkedin-proxycurl` — vía API (sin browser)

Acceso a datos de LinkedIn via [Proxycurl API](https://nubela.co/proxycurl).
Sin browser, sin cookies, sin riesgo de bloqueo. Ideal para volumen alto o producción.
Costo aproximado: **~$0.01 USD por crédito**.

Requiere `PROXYCURL_API_KEY` en `.env`. Obtén tu key en [nubela.co/proxycurl](https://nubela.co/proxycurl).

**5 modos disponibles:** `company-search` · `person-search` · `company` · `person` · `employees`

```bash
# ── Buscar empresas ───────────────────────────────────────────────────────────

# Búsqueda simple
python3 main.py linkedin-proxycurl company-search -q "digital health"
python3 main.py linkedin-proxycurl company-search -q "telehealth" -n 20

# Con filtro de ubicación
python3 main.py linkedin-proxycurl company-search -q "health tech" --location "United States"
python3 main.py linkedin-proxycurl company-search -q "salud digital" --location "Mexico"

# Enriquecer con perfil completo
python3 main.py linkedin-proxycurl company-search -q "digital health" -n 20 --enrich

# Incluir datos de funding (rondas de inversión, inversores)
python3 main.py linkedin-proxycurl company-search -q "healthtech" --enrich --funding

# Exportar
python3 main.py linkedin-proxycurl company-search -q "digital health" -n 30 --enrich --output csv


# ── Perfil completo de una empresa por URL ────────────────────────────────────

python3 main.py linkedin-proxycurl company \
  -q "https://www.linkedin.com/company/nombre-empresa"

# Con datos de funding
python3 main.py linkedin-proxycurl company \
  -q "https://www.linkedin.com/company/nombre-empresa" --funding


# ── Buscar personas ───────────────────────────────────────────────────────────

# Búsqueda simple
python3 main.py linkedin-proxycurl person-search -q "digital health"

# Con filtro de título
python3 main.py linkedin-proxycurl person-search -q "health tech" -t "CTO"
python3 main.py linkedin-proxycurl person-search -q "telemedicine" -t "Founder"
python3 main.py linkedin-proxycurl person-search -q "health app" -t "Product Manager"

# Con filtro de ubicación
python3 main.py linkedin-proxycurl person-search -q "digital health" --location "Mexico"
python3 main.py linkedin-proxycurl person-search -q "health tech" --location "United States"

# Enriquecer con experiencia completa, skills, contacto
python3 main.py linkedin-proxycurl person-search -q "digital health" -t "CTO" --enrich

# Exportar
python3 main.py linkedin-proxycurl person-search -q "health tech" -n 25 --enrich --output csv


# ── Perfil completo de una persona por URL ────────────────────────────────────

python3 main.py linkedin-proxycurl person \
  -q "https://www.linkedin.com/in/username"


# ── Empleados de una empresa ──────────────────────────────────────────────────

# Todos los empleados (hasta N)
python3 main.py linkedin-proxycurl employees \
  -q "https://www.linkedin.com/company/nombre" -n 50

# Filtrar por rol dentro de la empresa
python3 main.py linkedin-proxycurl employees \
  -q "https://www.linkedin.com/company/nombre" --title "engineer" -n 30
python3 main.py linkedin-proxycurl employees \
  -q "https://www.linkedin.com/company/nombre" --title "director" -n 20
python3 main.py linkedin-proxycurl employees \
  -q "https://www.linkedin.com/company/nombre" --title "product" -n 15
```

**Flags disponibles:**

| Flag | Corto | Descripción | Default |
|---|---|---|---|
| `--query` | `-q` | Keyword de búsqueda o URL de LinkedIn | — |
| `--title` | `-t` | Filtro de título (person-search y employees) | sin filtro |
| `--location` | `-l` | Ubicación en texto libre (ej: `"United States"`) | sin filtro |
| `--count` | `-n` | Número de resultados | `10` |
| `--enrich` | `-e` | Enriquecer cada resultado con perfil completo | `false` |
| `--funding` | | Incluir datos de funding (solo modo `company`) | `false` |
| `--output` | `-o` | Formato: `json` \| `jsonl` \| `csv` \| `all` | `json` |

**Campos en perfil de empresa enriquecido:**
`name` · `description` · `website` · `industry` · `specialties` · `employee_count` · `headquarters` · `founded` · `company_type` · `follower_count` · `tagline` · `key_employees` · `funding` (con `--funding`)

**Campos en perfil de persona enriquecido:**
`name` · `headline` · `summary` · `location` · `country` · `current_title` · `current_company` · `connections` · `followers` · `email` · `phone` · `skills` · `experience` · `education`

---

### Flujos completos por caso de uso

#### Market Research — mapear el ecosistema health tech

```bash
# Búsqueda amplia de empresas del sector
python3 main.py linkedin-companies "digital health" --location usa --count 50 --output csv
python3 main.py linkedin-companies "telehealth" --location latam --count 30 --output csv

# Enriquecer con datos completos
python3 main.py linkedin-companies "health tech" --enrich --output all

# Con funding data via Proxycurl
python3 main.py linkedin-proxycurl company-search -q "healthtech" -n 30 --enrich --funding --output csv
```

#### Lead Generation — encontrar decision-makers

```bash
# Buscar CTOs y Founders
python3 main.py linkedin-people "digital health" \
  --titles "CTO,Founder,CEO,CPO" --seniority "c_suite" \
  --location usa --count 40 --output csv

# Con Proxycurl (puede incluir email/teléfono)
python3 main.py linkedin-proxycurl person-search \
  -q "health tech" -t "CTO" -n 25 --enrich --output csv

# Empleados senior de una empresa target específica
python3 main.py linkedin-proxycurl employees \
  -q "https://www.linkedin.com/company/empresa-target" \
  --title "director" -n 20
```

#### Recruiting — pipeline de contratación

```bash
# Pipeline automático (busca + enriquece + ordena por seniority score)
python3 main.py linkedin-people "digital health" \
  --titles "CTO,VP Engineering,Director of Engineering" \
  --recruiting --count 30 --output csv

# Talento técnico en LATAM
python3 main.py linkedin-people "health technology" \
  --titles "Software Engineer,Backend Engineer,Data Engineer" \
  --location latam --count 50

# Perfil completo de un candidato específico
python3 main.py linkedin-proxycurl person -q "https://www.linkedin.com/in/candidato"
```

---

### Dónde se guardan los resultados

Todos los outputs se guardan en `output/` con nombre automático:

```
output/
├── linkedin_companies_digital_health_20260423_143000.json
├── linkedin_people_health_tech_20260423_150000.csv
└── proxycurl_companies_healthtech_20260423_160000.json
```

---

### Estructura de archivos LinkedIn

```
scraper/
├── linkedin_companies.py    ← Módulo A: búsqueda y perfiles de empresas
├── linkedin_profiles.py     ← Módulo B: búsqueda y perfiles de personas
└── linkedin_proxycurl.py    ← Módulo C: integración con Proxycurl API

cookies/
├── linkedin.json            ← Sesión guardada por linkedin-login (NO commitear)
└── HOW_TO_GET_COOKIES.md    ← Instrucciones manuales de setup

.env                         ← Credenciales (NO commitear)
.env.example                 ← Plantilla de variables de entorno
```

---

## 8. Referencia de selectores



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

## 9. Formatos de exportación

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

## 10. Errores comunes y soluciones

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
