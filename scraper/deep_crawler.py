"""
B) Deep crawler: follows ALL internal links from a seed URL,
visits every page of the site, and extracts structured data from each.
Builds a complete site map with per-page content.
"""
from __future__ import annotations

import time
from collections import deque
from urllib.parse import urljoin, urlparse

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

console = Console()


def _same_domain(base: str, url: str) -> bool:
    base_host = urlparse(base).netloc
    url_host = urlparse(url).netloc
    return url_host == "" or url_host == base_host


def _normalize(base: str, href: str) -> str | None:
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    url = urljoin(base, href)
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def deep_crawl(
    start_url: str,
    strategy: str = "dynamic",
    max_pages: int = 50,
    delay: float = 0.5,
    extract_fn=None,
    config: dict | None = None,
) -> dict:
    """
    Crawl an entire site starting from start_url.

    Args:
        start_url: seed URL
        strategy: http | stealth | dynamic
        max_pages: maximum pages to visit (0 = unlimited)
        delay: seconds between requests
        extract_fn: optional function(page) -> dict for per-page extraction
        config: scrapling config dict

    Returns:
        {
            "sitemap": [{"url": ..., "title": ..., "links": [...]}],
            "pages": {"url": extracted_data},
            "stats": {"total": ..., "errors": ..., "duration_s": ...}
        }
    """
    from scraper.smart_fetcher import SmartFetcher
    from scraper.full_extractor import extract_full

    extractor = extract_fn or extract_full

    visited: set[str] = set()
    queue: deque[str] = deque([start_url])
    sitemap = []
    pages = {}
    errors = []
    start_time = time.time()

    fetcher = SmartFetcher(strategy=strategy, config=config or {})

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Crawling...", total=max_pages or 100)

        while queue and (not max_pages or len(visited) < max_pages):
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            progress.update(task, description=f"[cyan]{len(visited)}/{max_pages or '∞'}[/cyan] {url[:60]}")

            try:
                page = fetcher.fetch(url)
                data = extractor(page)
                data["_url"] = url
                pages[url] = data

                title = data.get("title", "")
                internal_links = []

                for link in data.get("links", []):
                    href = link.get("href", "")
                    normalized = _normalize(url, href)
                    if normalized and _same_domain(start_url, normalized) and normalized not in visited:
                        internal_links.append(normalized)
                        if normalized not in queue:
                            queue.append(normalized)

                sitemap.append({
                    "url": url,
                    "title": title,
                    "internal_links_found": len(internal_links),
                    "depth": len(url.replace(start_url, "").split("/")) - 1,
                })

                console.print(f"  [green]✓[/green] [dim]{url}[/dim]  [cyan]{title[:50]}[/cyan]  ({len(internal_links)} new links)")
                progress.advance(task)

                if delay:
                    time.sleep(delay)

            except Exception as e:
                errors.append({"url": url, "error": str(e)})
                console.print(f"  [red]✗[/red] [dim]{url}[/dim]  {e}")

    duration = round(time.time() - start_time, 1)

    return {
        "sitemap": sitemap,
        "pages": pages,
        "stats": {
            "total_pages": len(visited),
            "successful": len(pages),
            "errors": len(errors),
            "error_details": errors,
            "duration_seconds": duration,
        },
    }
