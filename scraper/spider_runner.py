"""
Spider runner: builds and executes a Scrapling Spider from user instructions.
Supports multi-session, pagination, pause/resume, proxy rotation, and streaming.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def run_spider(
    start_urls: list[str],
    selectors: dict[str, str],
    follow_pagination: bool = True,
    pagination_css: str = ".next a, a[rel='next'], .pagination .next",
    concurrent_requests: int = 10,
    download_delay: float = 0.5,
    crawldir: str = "./crawl_data",
    robots_txt_obey: bool = False,
    proxies: list[str] | None = None,
    strategy: str = "http",
    max_pages: int = 0,
    on_item: Callable | None = None,
) -> list[dict]:
    """
    Run a spider across one or more start URLs.

    Args:
        start_urls: list of seed URLs
        selectors: dict of {field_name: css_or_xpath_selector}
        follow_pagination: automatically follow pagination links
        pagination_css: CSS selector for the next-page link
        concurrent_requests: parallelism level
        download_delay: seconds between requests
        crawldir: directory for checkpoint persistence (pause/resume)
        robots_txt_obey: respect robots.txt
        proxies: optional list of proxy URLs
        strategy: http | stealth | dynamic
        max_pages: 0 = unlimited
        on_item: optional callback called per extracted item

    Returns:
        list of extracted dicts
    """
    from scrapling.spiders import Spider, Request, Response

    # Build session factories based on strategy
    def _make_sessions(manager):
        if strategy == "stealth":
            from scrapling.fetchers import AsyncStealthySession
            manager.add("default", AsyncStealthySession(headless=True), lazy=True)
        elif strategy == "dynamic":
            from scrapling.fetchers import DynamicSession
            manager.add("default", DynamicSession(headless=True), lazy=True)
        else:
            from scrapling.fetchers import FetcherSession
            session_kwargs = {"impersonate": "chrome"}
            if proxies:
                from scrapling.fetchers import ProxyRotator
                session_kwargs["proxy_rotator"] = ProxyRotator(proxies, strategy="cyclic")
            manager.add("default", FetcherSession(**session_kwargs))

    pages_visited = [0]
    items: list[dict] = []

    class DynamicSpider(Spider):
        name = "dynamic_spider"
        start_urls = []
        concurrent_requests = concurrent_requests
        download_delay = download_delay
        robots_txt_obey = robots_txt_obey

        configure_sessions = _make_sessions

        async def parse(self, response: Response):
            if max_pages and pages_visited[0] >= max_pages:
                return

            pages_visited[0] += 1
            item = {"_url": response.url}

            for field, selector in selectors.items():
                if selector.startswith("//") or selector.startswith("(//"):
                    values = response.xpath(selector).get_all()
                else:
                    values = response.css(selector).get_all()
                item[field] = values[0] if len(values) == 1 else values

            if on_item:
                on_item(item)
            items.append(item)
            yield item

            if follow_pagination and (not max_pages or pages_visited[0] < max_pages):
                next_links = response.css(pagination_css)
                if next_links:
                    href = next_links[0].attrib.get("href", "")
                    if href:
                        yield response.follow(href, sid="default")

    DynamicSpider.start_urls = start_urls

    console.print(f"  [dim]Spider starting with[/dim] [cyan]{len(start_urls)}[/cyan] [dim]seed URL(s)[/dim]")
    console.print(f"  [dim]Concurrency:[/dim] [cyan]{concurrent_requests}[/cyan]  [dim]Delay:[/dim] [cyan]{download_delay}s[/cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Crawling...", total=None)
        result = DynamicSpider(crawldir=crawldir).start()
        progress.update(task, description=f"Done — {len(items)} items collected")

    if hasattr(result, "items") and result.items is not None:
        try:
            return result.items.to_list() if hasattr(result.items, "to_list") else items
        except Exception:
            pass

    return items
