"""
SmartFetcher: auto-selects the right Scrapling fetcher strategy based on URL and
user-specified mode. Supports HTTP, Stealth, and Dynamic fetchers + sessions.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from rich.console import Console

console = Console()

STEALTH_SIGNALS = [
    "linkedin", "cloudflare", "distil", "akamai", "incapsula",
    "datadome", "perimeterx", "kasada",
]
DYNAMIC_SIGNALS = [
    "twitter", "instagram", "facebook", "tiktok", "youtube",
    "reddit", "airbnb", "zillow",
]


def _detect_strategy(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(s in host for s in STEALTH_SIGNALS):
        return "stealth"
    if any(s in host for s in DYNAMIC_SIGNALS):
        return "dynamic"
    return "http"


class SmartFetcher:
    """
    Wraps all Scrapling fetcher types and picks the best one automatically
    (or uses the one explicitly requested).

    Strategies:
        auto     – detect from URL heuristics
        http     – Fetcher / FetcherSession
        stealth  – StealthyFetcher / StealthySession
        dynamic  – DynamicFetcher / DynamicSession
    """

    def __init__(self, strategy: str = "auto", config: dict | None = None):
        self.strategy = strategy
        self.cfg = config or {}
        self._session = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self, url: str, use_session: bool = False) -> object:
        """Fetch a single URL and return a Scrapling page object."""
        strategy = self._resolve_strategy(url)
        console.print(f"  [dim]Strategy:[/dim] [cyan]{strategy}[/cyan]  [dim]URL:[/dim] {url}")

        if strategy == "http":
            return self._fetch_http(url, use_session)
        elif strategy == "stealth":
            return self._fetch_stealth(url, use_session)
        elif strategy == "dynamic":
            return self._fetch_dynamic(url, use_session)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def close(self):
        if self._session:
            try:
                self._session.__exit__(None, None, None)
            except Exception:
                pass
            self._session = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_strategy(self, url: str) -> str:
        if self.strategy == "auto":
            detected = _detect_strategy(url)
            console.print(f"  [dim]Auto-detected strategy:[/dim] [yellow]{detected}[/yellow]")
            return detected
        return self.strategy

    def _fetch_http(self, url: str, use_session: bool):
        http_cfg = self.cfg.get("http", {})
        impersonate = http_cfg.get("impersonate", "chrome")
        stealthy_headers = http_cfg.get("stealthy_headers", True)
        http3 = http_cfg.get("http3", False)

        if use_session:
            from scrapling.fetchers import FetcherSession
            if not self._session:
                self._session = FetcherSession(
                    impersonate=impersonate,
                    http3=http3,
                )
                self._session.__enter__()
            return self._session.get(url, stealthy_headers=stealthy_headers)
        else:
            from scrapling.fetchers import Fetcher
            return Fetcher(impersonate=impersonate).get(url, stealthy_headers=stealthy_headers)

    def _fetch_stealth(self, url: str, use_session: bool):
        stealth_cfg = self.cfg.get("stealth", {})
        headless = self.cfg.get("headless", True)
        solve_cf = stealth_cfg.get("solve_cloudflare", True)
        disable_res = stealth_cfg.get("disable_resources", True)
        google_search = stealth_cfg.get("google_search", False)

        if use_session:
            from scrapling.fetchers import StealthySession
            if not self._session:
                self._session = StealthySession(
                    headless=headless,
                    disable_resources=disable_res,
                )
                self._session.__enter__()
            return self._session.fetch(url, solve_cloudflare=solve_cf, google_search=google_search)
        else:
            from scrapling.fetchers import StealthyFetcher
            return StealthyFetcher(
                headless=headless,
                disable_resources=disable_res,
            ).fetch(url, solve_cloudflare=solve_cf, google_search=google_search)

    def _fetch_dynamic(self, url: str, use_session: bool):
        dynamic_cfg = self.cfg.get("dynamic", {})
        headless = self.cfg.get("headless", True)
        network_idle = dynamic_cfg.get("network_idle", True)
        disable_res = dynamic_cfg.get("disable_resources", False)
        load_dom = dynamic_cfg.get("load_dom", True)

        if use_session:
            from scrapling.fetchers import DynamicSession
            if not self._session:
                self._session = DynamicSession(
                    headless=headless,
                    network_idle=network_idle,
                    disable_resources=disable_res,
                )
                self._session.__enter__()
            return self._session.fetch(url, load_dom=load_dom)
        else:
            from scrapling.fetchers import DynamicFetcher
            return DynamicFetcher(
                headless=headless,
                network_idle=network_idle,
                disable_resources=disable_res,
            ).fetch(url, load_dom=load_dom)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
