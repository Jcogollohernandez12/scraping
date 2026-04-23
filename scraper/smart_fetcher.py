"""
SmartFetcher: auto-selects the right Scrapling fetcher based on strategy.

This version maps to the installed scrapling API:
  http     → Fetcher().get()
  stealth  → StealthyFetcher().fetch()   (Camoufox)
  dynamic  → PlayWrightFetcher().fetch() (Playwright)
"""
from __future__ import annotations

from urllib.parse import urlparse
from rich.console import Console

console = Console()

STEALTH_SIGNALS = [
    "linkedin", "cloudflare", "distil", "akamai", "incapsula",
    "datadome", "perimeterx", "kasada",
]
DYNAMIC_SIGNALS = [
    "twitter", "instagram", "facebook", "tiktok", "youtube",
    "reddit", "airbnb", "zillow", "samayhealth",
]


def _detect_strategy(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(s in host for s in STEALTH_SIGNALS):
        return "stealth"
    if any(s in host for s in DYNAMIC_SIGNALS):
        return "dynamic"
    return "http"


class SmartFetcher:
    def __init__(self, strategy: str = "auto", config: dict | None = None):
        self.strategy = strategy
        self.cfg = config or {}

    def fetch(self, url: str, use_session: bool = False) -> object:
        strategy = self._resolve_strategy(url)
        console.print(f"  [dim]Strategy:[/dim] [cyan]{strategy}[/cyan]  [dim]URL:[/dim] {url}")

        if strategy == "http":
            return self._fetch_http(url)
        elif strategy == "stealth":
            return self._fetch_stealth(url)
        elif strategy == "dynamic":
            return self._fetch_dynamic(url)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _resolve_strategy(self, url: str) -> str:
        if self.strategy == "auto":
            detected = _detect_strategy(url)
            console.print(f"  [dim]Auto-detected:[/dim] [yellow]{detected}[/yellow]")
            return detected
        return self.strategy

    def _fetch_http(self, url: str):
        from scrapling.fetchers import Fetcher
        cfg = self.cfg.get("http", {})
        return Fetcher(
            auto_match=False,
        ).get(url, stealthy_headers=cfg.get("stealthy_headers", True))

    def _fetch_stealth(self, url: str):
        from scrapling.fetchers import StealthyFetcher
        cfg = self.cfg.get("stealth", {})
        headless = self.cfg.get("headless", True)
        return StealthyFetcher(auto_match=False).fetch(
            url,
            headless=headless,
            disable_resources=cfg.get("disable_resources", True),
            google_search=cfg.get("google_search", False),
        )

    def _fetch_dynamic(self, url: str):
        from scrapling.fetchers import PlayWrightFetcher
        cfg = self.cfg.get("dynamic", {})
        headless = self.cfg.get("headless", True)
        return PlayWrightFetcher(auto_match=False).fetch(
            url,
            headless=headless,
            network_idle=False,
            disable_resources=cfg.get("disable_resources", False),
            timeout=60000,
        )

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
