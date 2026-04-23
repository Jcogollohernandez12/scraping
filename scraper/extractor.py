"""
Extractor: applies CSS/XPath/text selectors to a Scrapling page object.
Also handles adaptive element tracking and selector generation.
"""
from __future__ import annotations

import re
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console()


class Extractor:
    """
    Runs structured extraction rules against a fetched page.

    A rule is a dict:
        {
            "field": "title",
            "selector": "h1::text",          # CSS or XPath
            "multiple": False,               # get() vs getall()
            "regex": r"\\d+",               # optional post-filter
            "attr": None,                   # e.g. "href" to get attribute
        }
    """

    def __init__(self, page):
        self.page = page

    # ------------------------------------------------------------------
    # Single-rule extraction
    # ------------------------------------------------------------------

    def extract(self, rules: list[dict]) -> dict[str, Any]:
        result = {}
        for rule in rules:
            field = rule.get("field", "data")
            value = self._apply_rule(rule)
            result[field] = value
        return result

    def _apply_rule(self, rule: dict) -> Any:
        selector = rule.get("selector", "")
        multiple = rule.get("multiple", False)
        regex = rule.get("regex")
        attr = rule.get("attr")

        if not selector:
            return None

        is_xpath = selector.startswith("//") or selector.startswith("(//")

        if is_xpath:
            elements = self.page.xpath(selector)
        else:
            # Handle ::text and ::attr pseudo-elements
            if attr:
                sel = selector.rstrip()
                elements = self.page.css(f"{sel}::attr({attr})")
            elif "::text" in selector or "::attr" in selector:
                elements = self.page.css(selector)
            else:
                elements = self.page.css(selector)

        raw = elements.get_all() if multiple else [elements.get()]
        raw = [r for r in raw if r is not None]

        if regex:
            filtered = []
            for item in raw:
                match = re.search(regex, str(item))
                if match:
                    filtered.append(match.group(0))
            raw = filtered

        if not multiple:
            return raw[0] if raw else None
        return raw

    # ------------------------------------------------------------------
    # Convenience extractors
    # ------------------------------------------------------------------

    def extract_all_text(self) -> list[str]:
        """Extract all visible text nodes."""
        return self.page.css("*::text").get_all()

    def extract_links(self) -> list[dict]:
        """Extract all anchor tags with href and text."""
        links = []
        for a in self.page.css("a"):
            attrib = getattr(a, 'attrib', {}) or {}
            href = attrib.get("href", "")
            text = a.css("::text").get() or ""
            if href:
                links.append({"text": text.strip(), "href": href.strip()})
        return links

    def extract_images(self) -> list[dict]:
        """Extract all images with src and alt."""
        images = []
        for img in self.page.css("img"):
            attrib = getattr(img, 'attrib', {}) or {}
            src = attrib.get("src", "") or attrib.get("data-src", "")
            alt = attrib.get("alt", "")
            if src:
                images.append({"src": src.strip(), "alt": alt.strip()})
        return images

    def extract_table(self, table_css: str = "table") -> list[dict]:
        """Extract first matching HTML table into list of dicts."""
        table = self.page.css(table_css)
        if not table:
            return []

        headers = [th.css("::text").get("").strip() for th in table.css("th")]
        rows = []
        for tr in table.css("tbody tr"):
            cells = [td.css("::text").get("").strip() for td in tr.css("td")]
            if headers and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
            elif cells:
                rows.append({"col_" + str(i): v for i, v in enumerate(cells)})
        return rows

    def extract_meta(self) -> dict:
        """Extract common page metadata."""
        def _get(selector):
            els = self.page.css(selector)
            if not els:
                return ""
            el = els[0] if hasattr(els, '__getitem__') else els
            attrib = getattr(el, 'attrib', {}) or {}
            return attrib.get("content", "")

        def _attr(selector, attr):
            els = self.page.css(selector)
            if not els:
                return ""
            el = els[0] if hasattr(els, '__getitem__') else els
            attrib = getattr(el, 'attrib', {}) or {}
            return attrib.get(attr, "")

        return {
            "title": self.page.css("title::text").get(""),
            "description": _get('meta[name="description"]'),
            "og_title": _get('meta[property="og:title"]'),
            "og_description": _get('meta[property="og:description"]'),
            "og_image": _get('meta[property="og:image"]'),
            "canonical": _attr('link[rel="canonical"]', "href"),
        }

    def find_by_text(self, text: str, tag: str = "*") -> list[str]:
        """Find elements containing specific text."""
        elements = self.page.find_by_text(text, tag=tag)
        return [el.css("::text").get("") for el in elements]

    def generate_selector_for(self, text: str) -> str | None:
        """Find an element by text and generate a CSS selector for it."""
        elements = self.page.find_by_text(text)
        if elements:
            try:
                return elements[0].generate_selector()
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def preview(self, rules: list[dict], max_chars: int = 120):
        """Print a Rich table preview of extracted data."""
        data = self.extract(rules)
        table = Table(title="Extraction Preview", show_lines=True)
        table.add_column("Field", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        for field, value in data.items():
            display = str(value)
            if len(display) > max_chars:
                display = display[:max_chars] + "..."
            table.add_row(field, display)

        console.print(table)
        return data
