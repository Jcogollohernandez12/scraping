#!/usr/bin/env python3
"""
Scrapling CLI — just give a URL and extraction instructions.

Usage:
    python main.py scrape <url>
    python main.py spider <url> [url2 ...]
    python main.py shell
    python main.py extract <url> <output_file>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

# Load .env at startup so LINKEDIN_LI_AT, PROXYCURL_API_KEY, etc. are available
load_dotenv(Path(__file__).parent / ".env")

app = typer.Typer(help="Scrapling-powered scraper — tell it what URL and what to extract.")
console = Console()

CONFIG_PATH = Path(__file__).parent / "config.yaml"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _print_banner():
    console.print(Panel.fit(
        "[bold cyan]Scrapling[/bold cyan] [dim]— Adaptive Web Scraper[/dim]\n"
        "[dim]HTTP · Stealth · Dynamic · Spider · AI-ready[/dim]",
        border_style="cyan",
    ))


def _ask_selectors() -> list[dict]:
    """Interactive prompt to build extraction rules."""
    console.print("\n[bold]Define what to extract[/bold] [dim](leave blank to finish)[/dim]")
    console.print("[dim]Selector examples:  h1::text  |  .price::text  |  //h1/text()  |  a::attr(href)[/dim]\n")

    rules = []
    idx = 1
    while True:
        field = Prompt.ask(f"  [cyan]Field {idx} name[/cyan] [dim](e.g. title)[/dim]", default="")
        if not field:
            break
        selector = Prompt.ask(f"  [cyan]Selector for '{field}'[/cyan]", default="")
        if not selector:
            break
        multiple = Confirm.ask(f"  Extract [cyan]multiple[/cyan] values for '{field}'?", default=False)
        attr = ""
        if "::" not in selector and not selector.startswith("//"):
            attr = Prompt.ask(f"  Attribute to extract [dim](leave blank for text)[/dim]", default="")
        regex = Prompt.ask(f"  Regex filter [dim](optional)[/dim]", default="")

        rule = {"field": field, "selector": selector, "multiple": multiple}
        if attr:
            rule["attr"] = attr
        if regex:
            rule["regex"] = regex
        rules.append(rule)
        idx += 1

    return rules


def _choose_strategy(cfg: dict) -> str:
    default = cfg.get("defaults", {}).get("strategy", "auto")
    strategy = Prompt.ask(
        "\n[bold]Fetcher strategy[/bold]",
        choices=["auto", "http", "stealth", "dynamic"],
        default=default,
    )
    return strategy


def _display_result(data: dict | list, max_rows: int = 10):
    if isinstance(data, dict):
        table = Table(show_lines=True, title="Extracted Data")
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="white", overflow="fold")
        for k, v in data.items():
            table.add_row(str(k), str(v)[:200])
        console.print(table)
    elif isinstance(data, list):
        if not data:
            console.print("[yellow]No items extracted.[/yellow]")
            return
        first = data[0] if isinstance(data[0], dict) else {"value": data[0]}
        table = Table(show_lines=True, title=f"Extracted Data ({len(data)} items)")
        for col in first.keys():
            table.add_column(str(col), style="white", overflow="fold")
        for row in data[:max_rows]:
            row = row if isinstance(row, dict) else {"value": row}
            table.add_row(*[str(row.get(c, ""))[:150] for c in first.keys()])
        if len(data) > max_rows:
            console.print(f"  [dim]... and {len(data) - max_rows} more rows (see output file)[/dim]")
        console.print(table)


# ──────────────────────────────────────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def scrape(
    url: str = typer.Argument(..., help="URL to scrape"),
    strategy: str = typer.Option("auto", "--strategy", "-s",
                                  help="Fetcher: auto | http | stealth | dynamic"),
    output: str = typer.Option("json", "--output", "-o",
                                help="Export format: json | jsonl | csv | all"),
    session: bool = typer.Option(False, "--session", help="Use persistent session"),
    extract_links: bool = typer.Option(False, "--links", help="Also extract all links"),
    extract_images: bool = typer.Option(False, "--images", help="Also extract all images"),
    extract_meta: bool = typer.Option(False, "--meta", help="Also extract page metadata"),
    extract_tables: bool = typer.Option(False, "--tables", help="Also extract HTML tables"),
    save_profile: str = typer.Option("", "--save-profile", help="Save extraction rules as a profile name"),
    load_profile: str = typer.Option("", "--load-profile", help="Load saved extraction rules profile"),
):
    """Scrape a single URL interactively."""
    _print_banner()
    cfg = _load_config()

    auto_mode = any([extract_links, extract_images, extract_meta, extract_tables])

    if strategy == "auto" and not auto_mode:
        strategy = _choose_strategy(cfg)

    # Load or build extraction rules
    rules: list[dict] = []
    if load_profile:
        profile_path = Path("profiles") / f"{load_profile}.json"
        if profile_path.exists():
            rules = json.loads(profile_path.read_text())
            console.print(f"[green]Loaded profile:[/green] {load_profile} ({len(rules)} rules)")
        else:
            console.print(f"[red]Profile not found:[/red] {load_profile}")
            raise typer.Exit(1)
    elif not auto_mode:
        rules = _ask_selectors()

    if not rules and not any([extract_links, extract_images, extract_meta, extract_tables]):
        console.print("[yellow]No extraction rules defined. Extracting full page text by default.[/yellow]")

    if save_profile and rules:
        profile_path = Path("profiles") / f"{save_profile}.json"
        profile_path.parent.mkdir(exist_ok=True)
        profile_path.write_text(json.dumps(rules, indent=2))
        console.print(f"[green]Profile saved:[/green] {save_profile}")

    # Fetch
    console.print(f"\n[bold]Fetching[/bold] {url}")
    from scraper.smart_fetcher import SmartFetcher
    from scraper.extractor import Extractor
    from scraper.exporter import Exporter

    fetcher = SmartFetcher(strategy=strategy, config=cfg)
    page = fetcher.fetch(url, use_session=session)

    if page is None:
        console.print("[red]Failed to fetch page.[/red]")
        raise typer.Exit(1)

    extractor = Extractor(page)

    result: dict = {}

    if rules:
        result.update(extractor.extract(rules))

    if extract_meta or not rules:
        result["_meta"] = extractor.extract_meta()

    if extract_links:
        result["_links"] = extractor.extract_links()

    if extract_images:
        result["_images"] = extractor.extract_images()

    if extract_tables:
        result["_tables"] = extractor.extract_table()

    if not rules and not any([extract_links, extract_images, extract_meta, extract_tables]):
        result["text"] = extractor.extract_all_text()

    # Display
    console.print()
    _display_result(result)

    # Export
    exporter = Exporter(cfg.get("defaults", {}).get("output_dir", "./output"))
    exporter.save(result, url, fmt=output)

    fetcher.close()


@app.command()
def spider(
    urls: list[str] = typer.Argument(..., help="Seed URL(s) to crawl"),
    strategy: str = typer.Option("http", "--strategy", "-s",
                                  help="http | stealth | dynamic"),
    output: str = typer.Option("json", "--output", "-o",
                                help="json | jsonl | csv | all"),
    concurrent: int = typer.Option(10, "--concurrent", "-c", help="Parallel requests"),
    delay: float = typer.Option(0.5, "--delay", "-d", help="Delay between requests (seconds)"),
    max_pages: int = typer.Option(0, "--max-pages", "-m", help="Max pages (0 = unlimited)"),
    no_pagination: bool = typer.Option(False, "--no-pagination", help="Don't follow pagination"),
    pagination_css: str = typer.Option(".next a, a[rel='next']", "--pagination-css",
                                        help="CSS selector for next-page link"),
    resume: bool = typer.Option(False, "--resume", help="Resume from last checkpoint"),
    proxies_file: str = typer.Option("", "--proxies", help="Path to file with one proxy per line"),
    load_profile: str = typer.Option("", "--load-profile", help="Load saved extraction rules profile"),
):
    """Crawl multiple pages using the Spider framework."""
    _print_banner()
    cfg = _load_config()

    proxies = []
    if proxies_file:
        p = Path(proxies_file)
        if p.exists():
            proxies = [l.strip() for l in p.read_text().splitlines() if l.strip()]

    rules: list[dict] = []
    if load_profile:
        profile_path = Path("profiles") / f"{load_profile}.json"
        if profile_path.exists():
            rules = json.loads(profile_path.read_text())
    else:
        rules = _ask_selectors()

    selectors = {r["field"]: r["selector"] for r in rules} if rules else {"text": "*::text"}

    console.print(f"\n[bold]Starting spider[/bold] — {len(urls)} seed URL(s)")

    from scraper.spider_runner import run_spider
    from scraper.exporter import Exporter

    items: list[dict] = []

    def on_item(item):
        items.append(item)
        console.print(f"  [green]+[/green] [dim]{item.get('_url', '')}[/dim]  ({len(items)} items)")

    crawldir = cfg.get("spider", {}).get("crawldir", "./crawl_data") if resume else "./crawl_data"

    results = run_spider(
        start_urls=list(urls),
        selectors=selectors,
        follow_pagination=not no_pagination,
        pagination_css=pagination_css,
        concurrent_requests=concurrent,
        download_delay=delay,
        crawldir=crawldir,
        strategy=strategy,
        max_pages=max_pages,
        proxies=proxies,
        on_item=on_item,
    )

    all_items = results or items
    console.print(f"\n[bold green]Done![/bold green] {len(all_items)} total items")
    _display_result(all_items)

    exporter = Exporter(cfg.get("defaults", {}).get("output_dir", "./output"))
    exporter.save(all_items, urls[0], fmt=output)


@app.command()
def extract(
    url: str = typer.Argument(..., help="URL to extract from"),
    output_file: str = typer.Argument(..., help="Output file path (e.g. result.json)"),
    strategy: str = typer.Option("auto", "--strategy", "-s"),
    css: str = typer.Option("", "--css", help="CSS selector"),
    xpath: str = typer.Option("", "--xpath", help="XPath selector"),
    impersonate: str = typer.Option("chrome", "--impersonate", help="Browser profile"),
    solve_cloudflare: bool = typer.Option(False, "--solve-cloudflare"),
):
    """Quick one-liner extraction (no interactive prompts)."""
    _print_banner()
    cfg = _load_config()

    console.print(f"\n[bold]Fetching[/bold] {url}")
    from scraper.smart_fetcher import SmartFetcher
    from scraper.exporter import Exporter

    fetcher = SmartFetcher(strategy=strategy, config=cfg)
    page = fetcher.fetch(url)

    if page is None:
        console.print("[red]Failed to fetch page.[/red]")
        raise typer.Exit(1)

    def _to_str(val):
        if hasattr(val, 'attrib'):
            attrib = getattr(val, 'attrib', {}) or {}
            text = " ".join(val.css("::text").get_all()).strip()
            return text or str(val)
        return str(val) if val is not None else ""

    data: dict = {}

    if css:
        raw = page.css(css).get_all()
        data["results"] = [_to_str(r) for r in raw]
    elif xpath:
        raw = page.xpath(xpath).get_all()
        data["results"] = [_to_str(r) for r in raw]
    else:
        from scraper.extractor import Extractor
        ex = Extractor(page)
        data["meta"] = ex.extract_meta()
        data["links"] = ex.extract_links()
        data["text_preview"] = ex.extract_all_text()[:20]

    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    import json as _json
    out.write_text(_json.dumps(data, ensure_ascii=False, indent=2))
    console.print(f"\n[green]Saved to[/green] {out}")

    _display_result(data)
    fetcher.close()


@app.command()
def shell():
    """Launch the native Scrapling interactive shell."""
    console.print("[cyan]Launching Scrapling shell...[/cyan]")
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "scrapling", "shell"], check=False)


@app.command()
def profiles():
    """List saved extraction profiles."""
    p = Path("profiles")
    files = list(p.glob("*.json")) if p.exists() else []
    if not files:
        console.print("[yellow]No profiles saved yet.[/yellow]")
        console.print("[dim]Use --save-profile <name> when running scrape to save rules.[/dim]")
        return
    table = Table(title="Saved Profiles")
    table.add_column("Name", style="cyan")
    table.add_column("Rules", justify="right")
    for f in files:
        try:
            rules = json.loads(f.read_text())
            table.add_row(f.stem, str(len(rules)))
        except Exception:
            table.add_row(f.stem, "?")
    console.print(table)


@app.command()
def install():
    """Install Scrapling browsers (Playwright + Camoufox)."""
    import subprocess, sys
    console.print("[cyan]Installing Playwright browsers...[/cyan]")
    subprocess.run([sys.executable, "-m", "playwright", "install"], check=False)
    console.print("[cyan]Installing Camoufox browser...[/cyan]")
    subprocess.run([sys.executable, "-m", "camoufox", "fetch"], check=False)
    console.print("[green]All browsers installed![/green]")


# ── A) Full structured extraction ─────────────────────────────────────────────
@app.command()
def full(
    url: str = typer.Argument(..., help="URL to extract fully"),
    strategy: str = typer.Option("dynamic", "--strategy", "-s"),
    output: str = typer.Option("json", "--output", "-o", help="json | jsonl | csv | all"),
    monitor: bool = typer.Option(False, "--monitor", "-m", help="Compare with previous snapshot"),
):
    """[A] Extract ALL structured content: headings, sections, links, images, forms, JSON-LD."""
    _print_banner()
    cfg = _load_config()
    from scraper.smart_fetcher import SmartFetcher
    from scraper.full_extractor import extract_full
    from scraper.exporter import Exporter

    console.print(f"\n[bold]Full extraction[/bold] → {url}")
    fetcher = SmartFetcher(strategy=strategy, config=cfg)
    page = fetcher.fetch(url)
    data = extract_full(page)

    if monitor:
        from scraper.monitor import take_snapshot, compare_snapshots, print_diff_report
        diff = compare_snapshots(url, data)
        print_diff_report(diff)
        take_snapshot(url, data)

    _display_result({k: v for k, v in data.items() if k != "full_text"})
    Exporter(cfg.get("defaults", {}).get("output_dir", "./output")).save(data, url, fmt=output)
    fetcher.close()


# ── B) Deep crawl ─────────────────────────────────────────────────────────────
@app.command()
def crawl(
    url: str = typer.Argument(..., help="Seed URL to crawl from"),
    strategy: str = typer.Option("dynamic", "--strategy", "-s"),
    max_pages: int = typer.Option(20, "--max-pages", "-m", help="Max pages to visit"),
    delay: float = typer.Option(0.5, "--delay", "-d"),
    output: str = typer.Option("json", "--output", "-o"),
    business: bool = typer.Option(False, "--business", help="Also run business extraction on each page"),
):
    """[B] Deep crawl: follow ALL internal links and extract data from every page."""
    _print_banner()
    cfg = _load_config()
    from scraper.deep_crawler import deep_crawl
    from scraper.exporter import Exporter

    extract_fn = None
    if business:
        from scraper.full_extractor import extract_full
        from scraper.business_extractor import extract_business
        def extract_fn(page):
            data = extract_full(page)
            data["business"] = extract_business(page)
            return data

    console.print(f"\n[bold]Deep crawl[/bold] → {url}  [dim](max {max_pages} pages)[/dim]")
    result = deep_crawl(url, strategy=strategy, max_pages=max_pages, delay=delay,
                        extract_fn=extract_fn, config=cfg)

    stats = result["stats"]
    console.print(f"\n[bold green]Done![/bold green] {stats['total_pages']} pages | {stats['errors']} errors | {stats['duration_seconds']}s")

    table = Table(title="Sitemap", show_lines=True)
    table.add_column("URL", style="cyan", overflow="fold")
    table.add_column("Title", style="white")
    table.add_column("Links", justify="right")
    for entry in result["sitemap"][:30]:
        table.add_row(entry["url"][:80], entry.get("title", "")[:50], str(entry.get("internal_links_found", 0)))
    console.print(table)

    Exporter(cfg.get("defaults", {}).get("output_dir", "./output")).save(result, url, fmt=output)


# ── C) Business data extraction ───────────────────────────────────────────────
@app.command()
def business(
    url: str = typer.Argument(..., help="URL to extract business data from"),
    strategy: str = typer.Option("dynamic", "--strategy", "-s"),
    output: str = typer.Option("json", "--output", "-o"),
):
    """[C] Extract business data: prices, services, team, testimonials, FAQs, contact."""
    _print_banner()
    cfg = _load_config()
    from scraper.smart_fetcher import SmartFetcher
    from scraper.business_extractor import extract_business
    from scraper.exporter import Exporter

    console.print(f"\n[bold]Business extraction[/bold] → {url}")
    fetcher = SmartFetcher(strategy=strategy, config=cfg)
    page = fetcher.fetch(url)
    data = extract_business(page)
    data["_url"] = url

    _display_result(data)
    Exporter(cfg.get("defaults", {}).get("output_dir", "./output")).save(data, url, fmt=output)
    fetcher.close()


# ── D) Change monitor ─────────────────────────────────────────────────────────
@app.command()
def monitor(
    url: str = typer.Argument(..., help="URL to monitor for changes"),
    strategy: str = typer.Option("dynamic", "--strategy", "-s"),
    list_snaps: bool = typer.Option(False, "--list", "-l", help="List all saved snapshots"),
):
    """[D] Monitor changes: compare current page with previous snapshot."""
    _print_banner()
    cfg = _load_config()
    from scraper.monitor import take_snapshot, compare_snapshots, print_diff_report, list_snapshots

    if list_snaps:
        snaps = list_snapshots(url if url != "list" else None)
        table = Table(title="Saved Snapshots")
        table.add_column("File", style="cyan")
        table.add_column("URL", style="dim", overflow="fold")
        table.add_column("Timestamp")
        table.add_column("Hash", style="dim")
        for s in snaps:
            table.add_row(s["file"], s["url"][:60], s["timestamp"], s["hash"])
        console.print(table)
        return

    from scraper.smart_fetcher import SmartFetcher
    from scraper.full_extractor import extract_full
    from scraper.business_extractor import extract_business

    console.print(f"\n[bold]Monitoring[/bold] → {url}")
    fetcher = SmartFetcher(strategy=strategy, config=cfg)
    page = fetcher.fetch(url)
    data = extract_full(page)
    data["business"] = extract_business(page)

    diff = compare_snapshots(url, data)
    print_diff_report(diff)
    take_snapshot(url, data)
    fetcher.close()


# ── E) Network interceptor ────────────────────────────────────────────────────
@app.command()
def intercept(
    url: str = typer.Argument(..., help="URL to intercept network traffic"),
    output: str = typer.Option("json", "--output", "-o"),
    all_requests: bool = typer.Option(False, "--all", help="Capture all requests, not just API"),
    wait: int = typer.Option(5, "--wait", "-w", help="Extra seconds to wait after page load"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
):
    """[E] Intercept ALL network requests: API calls, JSON responses, GraphQL, auth tokens."""
    _print_banner()
    cfg = _load_config()
    from scraper.network_interceptor import intercept as do_intercept, print_network_report
    from scraper.exporter import Exporter

    console.print(f"\n[bold]Network interception[/bold] → {url}")
    data = do_intercept(url, headless=headless, wait_seconds=wait,
                        filter_api_only=not all_requests)
    print_network_report(data)
    Exporter(cfg.get("defaults", {}).get("output_dir", "./output")).save(data, url, fmt=output)


# ── Combined: run A+B+C+D+E all at once ──────────────────────────────────────
@app.command()
def deep(
    url: str = typer.Argument(..., help="URL — runs all 5 extraction modes"),
    strategy: str = typer.Option("dynamic", "--strategy", "-s"),
    max_pages: int = typer.Option(10, "--max-pages", "-m"),
    output: str = typer.Option("all", "--output", "-o"),
):
    """[ALL] Run full + business + crawl + monitor + intercept on a single URL."""
    _print_banner()
    cfg = _load_config()
    from scraper.smart_fetcher import SmartFetcher
    from scraper.full_extractor import extract_full
    from scraper.business_extractor import extract_business
    from scraper.monitor import take_snapshot, compare_snapshots, print_diff_report
    from scraper.network_interceptor import intercept as do_intercept, print_network_report
    from scraper.deep_crawler import deep_crawl
    from scraper.exporter import Exporter

    exporter = Exporter(cfg.get("defaults", {}).get("output_dir", "./output"))
    fetcher = SmartFetcher(strategy=strategy, config=cfg)

    console.rule("[bold cyan]A) Full structured extraction[/bold cyan]")
    page = fetcher.fetch(url)
    full_data = extract_full(page)
    exporter.save(full_data, url + "_full", fmt=output)

    console.rule("[bold cyan]C) Business data[/bold cyan]")
    biz_data = extract_business(page)
    biz_data["_url"] = url
    _display_result(biz_data)
    exporter.save(biz_data, url + "_business", fmt=output)

    console.rule("[bold cyan]D) Change monitoring[/bold cyan]")
    combined = {**full_data, "business": biz_data}
    diff = compare_snapshots(url, combined)
    print_diff_report(diff)
    take_snapshot(url, combined)

    console.rule("[bold cyan]E) Network interception[/bold cyan]")
    net_data = do_intercept(url, headless=True, wait_seconds=5)
    print_network_report(net_data)
    exporter.save(net_data, url + "_network", fmt=output)

    console.rule("[bold cyan]B) Deep crawl[/bold cyan]")
    crawl_result = deep_crawl(url, strategy=strategy, max_pages=max_pages,
                               delay=0.5, config=cfg)
    exporter.save(crawl_result, url + "_crawl", fmt=output)

    fetcher.close()
    console.rule("[bold green]All done![/bold green]")


# ── LinkedIn: Login / session setup ──────────────────────────────────────────
@app.command(name="linkedin-login")
def linkedin_login(
    email: str = typer.Option("", "--email", "-e", help="LinkedIn email (o dejar vacío para login manual)"),
    password: str = typer.Option("", "--password", "-p", help="LinkedIn password"),
    save: bool = typer.Option(True, "--save/--no-save", help="Guardar cookies en cookies/linkedin.json y .env"),
):
    """Iniciar sesión en LinkedIn y guardar la sesión para todos los comandos.

    \b
    Modos:
      Auto   →  python3 main.py linkedin-login --email tu@email.com --password tupass
      Manual →  python3 main.py linkedin-login        (abre browser, tú haces login)

    Guarda las cookies en cookies/linkedin.json y actualiza .env con li_at.
    Después de correr esto UNA VEZ no necesitas volver a hacerlo.
    """
    import os
    import time
    from playwright.sync_api import sync_playwright

    _print_banner()
    console.print("\n[bold cyan]LinkedIn Login Setup[/bold cyan]")

    # Try loading from env first if no args given
    if not email:
        email = os.getenv("LINKEDIN_EMAIL", "").strip()
    if not password:
        password = os.getenv("LINKEDIN_PASSWORD", "").strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = context.new_page()

        console.print("  [dim]Abriendo LinkedIn...[/dim]")

        # Use networkidle so the page is fully rendered before interacting
        try:
            page.goto(
                "https://www.linkedin.com/login",
                wait_until="networkidle",
                timeout=60000,
            )
        except Exception:
            # networkidle can time out on slow connections — page is still usable
            pass

        # Dismiss cookie/GDPR banners if present
        for banner_sel in [
            "button[action-type='ACCEPT']",
            "button#onetrust-accept-btn-handler",
            "button[data-control-name='accept_cookies']",
        ]:
            try:
                btn = page.query_selector(banner_sel)
                if btn:
                    btn.click()
                    time.sleep(0.5)
            except Exception:
                pass

        if email and password:
            # ── Auto-login ────────────────────────────────────────────
            console.print(f"  [dim]Ingresando credenciales para:[/dim] [cyan]{email}[/cyan]")

            # Wait until the username field is visible and enabled
            try:
                page.wait_for_selector("#username", state="visible", timeout=30000)
            except Exception:
                # Fallback selectors LinkedIn has used historically
                for sel in ["input[name='session_key']", "input[autocomplete='username']", "input[type='email']"]:
                    el = page.query_selector(sel)
                    if el:
                        page.locator(sel).fill(email)
                        break
            else:
                page.locator("#username").fill(email)

            time.sleep(0.6)

            # Password field
            try:
                page.wait_for_selector("#password", state="visible", timeout=10000)
                page.locator("#password").fill(password)
            except Exception:
                for sel in ["input[name='session_password']", "input[type='password']"]:
                    el = page.query_selector(sel)
                    if el:
                        page.locator(sel).fill(password)
                        break

            time.sleep(0.6)

            # Submit
            for submit_sel in ["button[type='submit']", "button[data-litms-control-urn*='login']", ".login__form_action_container button"]:
                btn = page.query_selector(submit_sel)
                if btn:
                    btn.click()
                    break

            console.print("  [dim]Esperando respuesta de LinkedIn...[/dim]")

            # Wait for redirect away from /login
            try:
                page.wait_for_url(lambda url: "/login" not in url, timeout=20000)
            except Exception:
                time.sleep(6)

            # Handle security verification / captcha
            current_url = page.url
            if any(k in current_url for k in ["checkpoint", "challenge", "verification", "captcha"]):
                console.print("\n[yellow]LinkedIn pidió verificación de seguridad.[/yellow]")
                console.print("[bold]Completa la verificación en el browser y luego presiona Enter aquí.[/bold]")
                input("  → Presiona Enter cuando hayas completado la verificación: ")
                time.sleep(3)
        else:
            # ── Manual login ──────────────────────────────────────────
            console.print("\n[bold yellow]Login manual:[/bold yellow]")
            console.print("  1. Ingresa tu email y contraseña en el browser que se abrió")
            console.print("  2. Completa cualquier verificación que aparezca")
            console.print("  3. Espera hasta ver tu feed de LinkedIn")
            console.print("  4. Vuelve aquí y presiona Enter\n")
            input("  → Presiona Enter cuando estés logueado en LinkedIn: ")
            time.sleep(2)

        # Verify login succeeded
        current_url = page.url
        if "feed" not in current_url and "mynetwork" not in current_url and "linkedin.com/in/" not in current_url:
            # Try navigating to feed to confirm
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)
            current_url = page.url

        if "login" in current_url or "checkpoint" in current_url:
            console.print("\n[red]Login no exitoso. Verifica tus credenciales.[/red]")
            browser.close()
            raise typer.Exit(1)

        console.print("\n[bold green]✓ Login exitoso![/bold green]")

        # Extract cookies
        cookies = context.cookies()
        browser.close()

    # Find the important cookies
    cookie_dict = {c["name"]: c["value"] for c in cookies}
    li_at = cookie_dict.get("li_at", "")
    jsessionid = cookie_dict.get("JSESSIONID", "")

    if not li_at:
        console.print("[red]No se encontró la cookie li_at. Intenta de nuevo.[/red]")
        raise typer.Exit(1)

    console.print(f"  [dim]li_at:[/dim] [green]{li_at[:30]}...[/green]")

    if save:
        # Save to cookies/linkedin.json
        cookies_dir = Path("cookies")
        cookies_dir.mkdir(exist_ok=True)
        cookies_path = cookies_dir / "linkedin.json"
        cookies_path.write_text(json.dumps(cookies, indent=2, ensure_ascii=False))
        console.print(f"  [green]Cookies guardadas en:[/green] {cookies_path}")

        # Update or create .env file
        env_path = Path(".env")
        env_lines: list[str] = []

        if env_path.exists():
            env_lines = env_path.read_text().splitlines()

        # Update or add LINKEDIN_LI_AT
        li_at_set = False
        js_set = False
        new_lines: list[str] = []
        for line in env_lines:
            if line.startswith("LINKEDIN_LI_AT="):
                new_lines.append(f"LINKEDIN_LI_AT={li_at}")
                li_at_set = True
            elif line.startswith("LINKEDIN_JSESSIONID=") and jsessionid:
                new_lines.append(f"LINKEDIN_JSESSIONID={jsessionid}")
                js_set = True
            else:
                new_lines.append(line)

        if not li_at_set:
            new_lines.append(f"LINKEDIN_LI_AT={li_at}")
        if not js_set and jsessionid:
            new_lines.append(f"LINKEDIN_JSESSIONID={jsessionid}")

        env_path.write_text("\n".join(new_lines) + "\n")
        console.print(f"  [green]LINKEDIN_LI_AT guardado en:[/green] .env")

        # Reload env so current process picks it up immediately
        load_dotenv(env_path, override=True)

    console.print("\n[bold green]Setup completo.[/bold green]")
    console.print("[dim]Ahora puedes usar linkedin-companies, linkedin-people, etc. sin configuración adicional.[/dim]")


# ── LinkedIn: Company search (Module A) ───────────────────────────────────────
@app.command(name="linkedin-companies")
def linkedin_companies(
    keywords: str = typer.Argument("health tech", help="Search keywords e.g. 'digital health'"),
    industries: str = typer.Option(
        "", "--industries", "-i",
        help="Comma-separated industry keys: hospital_healthcare,health_wellness_fitness,"
             "biotechnology,pharmaceuticals,medical_devices,mental_health",
    ),
    location: str = typer.Option("", "--location", "-l", help="GEO key: usa,latam,mexico,colombia,brazil,uk,spain"),
    count: int = typer.Option(25, "--count", "-n", help="Number of companies to find"),
    enrich: bool = typer.Option(False, "--enrich", "-e", help="Fetch full profile for each company"),
    headless: bool = typer.Option(False, "--headless/--no-headless", help="Run browser headless"),
    output: str = typer.Option("json", "--output", "-o", help="json | jsonl | csv | all"),
):
    """[A] Search LinkedIn for health tech companies via Voyager API."""
    _print_banner()
    cfg = _load_config()

    from scraper.linkedin_companies import search_companies, bulk_enrich_companies
    from scraper.linkedin_proxycurl import print_companies_table
    from scraper.exporter import Exporter

    ind_list = [i.strip() for i in industries.split(",") if i.strip()] if industries else None

    console.print(f"\n[bold]LinkedIn Company Search[/bold] — [cyan]{keywords}[/cyan]")
    if ind_list:
        console.print(f"  Industries: {ind_list}")
    if location:
        console.print(f"  Location: {location}")

    companies = search_companies(
        keywords=keywords,
        industries=ind_list,
        location=location,
        count=count,
        headless=headless,
    )

    if enrich and companies:
        console.print(f"\n[bold]Enriching {len(companies)} company profiles...[/bold]")
        companies = bulk_enrich_companies(companies, headless=headless)

    print_companies_table(companies)

    exporter = Exporter(cfg.get("defaults", {}).get("output_dir", "./output"))
    exporter.save(companies, f"linkedin_companies_{keywords.replace(' ', '_')}", fmt=output)


# ── LinkedIn: People search (Module B) ───────────────────────────────────────
@app.command(name="linkedin-people")
def linkedin_people(
    keywords: str = typer.Argument("digital health", help="Search keywords"),
    titles: str = typer.Option(
        "CTO,Founder,CEO",
        "--titles", "-t",
        help="Comma-separated job titles to filter by",
    ),
    seniority: str = typer.Option(
        "c_suite,vp,director",
        "--seniority", "-s",
        help="c_suite | vp | director | manager | senior | entry",
    ),
    location: str = typer.Option("", "--location", "-l", help="GEO key: usa,latam,mexico,colombia,uk"),
    count: int = typer.Option(25, "--count", "-n", help="Number of profiles to find"),
    enrich: bool = typer.Option(False, "--enrich", "-e", help="Fetch full profile for each person"),
    recruiting: bool = typer.Option(False, "--recruiting", help="Run full recruiting pipeline (search+enrich+score)"),
    headless: bool = typer.Option(False, "--headless/--no-headless", help="Run browser headless"),
    output: str = typer.Option("json", "--output", "-o", help="json | jsonl | csv | all"),
):
    """[B] Search LinkedIn for health tech professionals (recruiting + market research)."""
    _print_banner()
    cfg = _load_config()

    from scraper.exporter import Exporter
    from scraper.linkedin_proxycurl import print_people_table

    exporter = Exporter(cfg.get("defaults", {}).get("output_dir", "./output"))

    titles_list = [t.strip() for t in titles.split(",") if t.strip()] if titles else None
    seniority_list = [s.strip() for s in seniority.split(",") if s.strip()] if seniority else None

    console.print(f"\n[bold]LinkedIn People Search[/bold] — [cyan]{keywords}[/cyan]")
    if titles_list:
        console.print(f"  Titles: {titles_list}")

    if recruiting:
        from scraper.linkedin_profiles import build_recruiting_list
        profiles = build_recruiting_list(
            keywords=keywords,
            titles=titles_list,
            location=location,
            count=count,
            enrich=enrich,
            headless=headless,
        )
    else:
        from scraper.linkedin_profiles import search_people, get_person_profile
        from scraper.linkedin_companies import load_linkedin_cookies

        cookies = load_linkedin_cookies()
        profiles = search_people(
            keywords=keywords,
            titles=titles_list,
            seniority=seniority_list,
            location=location,
            count=count,
            headless=headless,
            cookies=cookies,
        )

        if enrich and profiles:
            console.print(f"\n[bold]Enriching {len(profiles)} profiles...[/bold]")
            enriched = []
            import time, random
            for i, p in enumerate(profiles):
                url = p.get("linkedin_url", "")
                if not url:
                    enriched.append(p)
                    continue
                console.print(f"  [{i+1}/{len(profiles)}] [cyan]{p.get('name', url)}[/cyan]")
                try:
                    full = get_person_profile(url, cookies=cookies, headless=headless)
                    enriched.append({**p, **full})
                except Exception as e:
                    console.print(f"    [red]{e}[/red]")
                    enriched.append(p)
                time.sleep(cfg.get("linkedin", {}).get("rate_limit_delay", 3.5) + random.uniform(0, 1))
            profiles = enriched

    print_people_table(profiles)
    exporter.save(profiles, f"linkedin_people_{keywords.replace(' ', '_')}", fmt=output)


# ── LinkedIn: Proxycurl API (Module C) ────────────────────────────────────────
@app.command(name="linkedin-proxycurl")
def linkedin_proxycurl(
    mode: str = typer.Argument(
        ...,
        help="Mode: company-search | person-search | company | person | employees",
    ),
    query: str = typer.Option("", "--query", "-q", help="Search keyword or LinkedIn URL"),
    title: str = typer.Option("", "--title", "-t", help="Job title filter (person-search)"),
    location: str = typer.Option("", "--location", "-l", help="Location filter"),
    count: int = typer.Option(10, "--count", "-n", help="Number of results"),
    enrich: bool = typer.Option(False, "--enrich", "-e", help="Enrich each result with full profile"),
    funding: bool = typer.Option(False, "--funding", help="Include funding data (company mode)"),
    output: str = typer.Option("json", "--output", "-o", help="json | jsonl | csv | all"),
):
    """[C] LinkedIn data via Proxycurl API (requires PROXYCURL_API_KEY).

    \b
    Modes:
      company-search  Search companies by keyword
      person-search   Search people by keyword/title
      company         Get full company profile from URL
      person          Get full person profile from URL
      employees       List employees of a company (URL)

    \b
    Examples:
      python main.py linkedin-proxycurl company-search -q "digital health" -n 20 --enrich
      python main.py linkedin-proxycurl person-search -q "telemedicine" -t "CTO" --enrich
      python main.py linkedin-proxycurl company -q "https://linkedin.com/company/stripe" --funding
      python main.py linkedin-proxycurl employees -q "https://linkedin.com/company/apple" -n 50
    """
    _print_banner()
    cfg = _load_config()

    from scraper import linkedin_proxycurl as pc
    from scraper.linkedin_proxycurl import print_companies_table, print_people_table
    from scraper.exporter import Exporter

    exporter = Exporter(cfg.get("defaults", {}).get("output_dir", "./output"))
    extra = ["funding"] if funding else None
    slug = query.replace(" ", "_").replace("/", "_")[:40]

    console.print(f"\n[bold]Proxycurl[/bold] — mode=[cyan]{mode}[/cyan]  query={query}")

    if mode == "company-search":
        results = pc.search_companies(keyword=query or "health tech", location=location, count=count)
        if enrich and results:
            results = pc.bulk_enrich_companies(results, extra_fields=extra)
        print_companies_table(results)
        exporter.save(results, f"proxycurl_companies_{slug}", fmt=output)

    elif mode == "person-search":
        results = pc.search_people(keyword=query or "health tech", title=title, location=location, count=count)
        if enrich and results:
            results = pc.bulk_enrich_people(results)
        print_people_table(results)
        exporter.save(results, f"proxycurl_people_{slug}", fmt=output)

    elif mode == "company":
        if not query:
            console.print("[red]Provide --query with the LinkedIn company URL[/red]")
            raise typer.Exit(1)
        result = pc.get_company(query, extra_fields=extra)
        if result:
            _display_result(result)
            exporter.save(result, f"proxycurl_company_{slug}", fmt=output)
        else:
            console.print("[yellow]No data returned.[/yellow]")

    elif mode == "person":
        if not query:
            console.print("[red]Provide --query with the LinkedIn profile URL[/red]")
            raise typer.Exit(1)
        result = pc.get_person(query)
        if result:
            _display_result(result)
            exporter.save(result, f"proxycurl_person_{slug}", fmt=output)
        else:
            console.print("[yellow]No data returned.[/yellow]")

    elif mode == "employees":
        if not query:
            console.print("[red]Provide --query with the LinkedIn company URL[/red]")
            raise typer.Exit(1)
        results = pc.company_employees(query, count=count, role_keyword=title)
        print_people_table(results)
        exporter.save(results, f"proxycurl_employees_{slug}", fmt=output)

    else:
        console.print(f"[red]Unknown mode:[/red] {mode}")
        console.print("[dim]Valid modes: company-search | person-search | company | person | employees[/dim]")
        raise typer.Exit(1)


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app()
