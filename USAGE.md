# Scrapling Project — Usage Guide

## Setup (once)

```bash
cd /Users/samaydeveloper/Documents/scraping

# Install dependencies
pip install -r requirements.txt

# Install browsers (needed for stealth/dynamic)
python main.py install
```

---

## Commands

### `scrape` — single URL, interactive
```bash
python main.py scrape https://example.com
```
- Asks you which strategy to use (auto/http/stealth/dynamic)
- Asks you what fields to extract (CSS or XPath selectors)
- Saves results to `output/`

**With flags:**
```bash
# Force stealth mode + export everything
python main.py scrape https://example.com --strategy stealth --output all

# Extract links + images + metadata automatically
python main.py scrape https://example.com --links --images --meta

# Save extraction rules as a profile for reuse
python main.py scrape https://example.com --save-profile ecommerce

# Reuse saved profile next time
python main.py scrape https://shop.com --load-profile ecommerce
```

### `spider` — crawl multiple pages
```bash
# Crawl a site following pagination automatically
python main.py spider https://quotes.toscrape.com/

# Multiple seed URLs
python main.py spider https://site.com/page1 https://site.com/page2

# Limit to 5 pages, use stealth
python main.py spider https://example.com --strategy stealth --max-pages 5

# Resume a paused crawl
python main.py spider https://example.com --resume

# With proxies
python main.py spider https://example.com --proxies proxies.txt
```

### `extract` — quick one-liner (no prompts)
```bash
# Extract with CSS selector
python main.py extract https://quotes.toscrape.com result.json --css ".quote .text::text"

# Extract with XPath
python main.py extract https://example.com result.json --xpath "//h1/text()"

# Bypass Cloudflare
python main.py extract https://protected-site.com out.json --strategy stealth --solve-cloudflare
```

### `shell` — interactive Scrapling REPL
```bash
python main.py shell
```

### `profiles` — list saved extraction profiles
```bash
python main.py profiles
```

---

## Selector Reference

| What you want | Selector |
|---|---|
| Text inside `<h1>` | `h1::text` |
| All `<p>` texts | `p::text` (multiple=yes) |
| Link href | `a::attr(href)` or use `--attr href` |
| Element by class | `.classname::text` |
| XPath text | `//h1/text()` |
| XPath attribute | `//a/@href` |

---

## Strategies

| Strategy | When to use |
|---|---|
| `auto` | Let the tool decide based on the URL |
| `http` | Fast sites, no JS required |
| `stealth` | Cloudflare, bot protection, LinkedIn |
| `dynamic` | SPAs, React/Angular apps, infinite scroll |

---

## Output

Results are saved in `output/` as:
- `<domain>_<timestamp>.json`
- `<domain>_<timestamp>.jsonl` (if format=jsonl or all)
- `<domain>_<timestamp>.csv` (if format=csv or all)
