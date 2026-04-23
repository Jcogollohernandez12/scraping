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
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

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


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app()
