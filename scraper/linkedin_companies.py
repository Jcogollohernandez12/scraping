"""
A) LinkedIn Company Extractor — Health Tech
Dual strategy:
  1. Voyager API interception (requires li_at cookie)
  2. HTML fallback for public company pages
"""
from __future__ import annotations

import json
import os
import re
import time
import random
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()

VOYAGER = "https://www.linkedin.com/voyager/api"

# LinkedIn industry codes relevant to health tech
HEALTH_INDUSTRIES = {
    "hospital_healthcare": "14",
    "health_wellness_fitness": "96",
    "biotechnology": "42",
    "pharmaceuticals": "82",
    "medical_devices": "74",
    "mental_health": "139",
    "medical_practice": "54",
    "research": "87",
}

# Common geo URNs for location filtering
GEO_URNS = {
    "usa": "urn:li:geo:103644278",
    "latam": "urn:li:geo:91000001",
    "mexico": "urn:li:geo:103323778",
    "colombia": "urn:li:geo:100876405",
    "brazil": "urn:li:geo:106057199",
    "uk": "urn:li:geo:101165590",
    "spain": "urn:li:geo:105646813",
}


# ── Cookie management ─────────────────────────────────────────────────────────

def load_linkedin_cookies() -> dict[str, str]:
    """Load LinkedIn session cookies from env vars or cookies/linkedin.json."""
    cookies: dict[str, str] = {}

    li_at = os.getenv("LINKEDIN_LI_AT", "").strip()
    jsessionid = os.getenv("LINKEDIN_JSESSIONID", "").strip()

    if li_at:
        cookies["li_at"] = li_at
    if jsessionid:
        cookies["JSESSIONID"] = f'"{jsessionid}"' if not jsessionid.startswith('"') else jsessionid

    cookies_file = Path("cookies/linkedin.json")
    if cookies_file.exists() and not li_at:
        try:
            raw = json.loads(cookies_file.read_text())
            if isinstance(raw, list):
                for c in raw:
                    if isinstance(c, dict) and "name" in c:
                        cookies[c["name"]] = c["value"]
            elif isinstance(raw, dict):
                cookies.update(raw)
        except Exception as e:
            console.print(f"  [yellow]Cookie file error:[/yellow] {e}")

    return cookies


def _cookies_to_playwright(cookies: dict[str, str]) -> list[dict]:
    return [
        {"name": k, "value": v, "domain": ".linkedin.com", "path": "/"}
        for k, v in cookies.items()
        if v
    ]


# ── Voyager response parsers ──────────────────────────────────────────────────

def _parse_voyager_search(json_data: dict) -> list[dict]:
    """Parse Voyager blended search response into company records."""
    companies: list[dict] = []

    top_level = (
        json_data.get("data", {}).get("elements", [])
        or json_data.get("elements", [])
    )

    for group in top_level:
        hits = group.get("elements", [group]) if isinstance(group, dict) else []
        for hit in hits:
            entity = (
                hit.get("entityResult")
                or hit.get("company")
                or hit.get("entityLockupView")
                or hit
            )
            if not entity or not isinstance(entity, dict):
                continue

            name = (
                (entity.get("title") or {}).get("text", "")
                or entity.get("name", "")
                or (entity.get("primaryText") or {}).get("text", "")
            )
            if not name:
                continue

            nav_url = entity.get("navigationUrl", "") or entity.get("url", "")
            if nav_url and not nav_url.startswith("http"):
                nav_url = f"https://www.linkedin.com{nav_url}"

            industry_size = (
                (entity.get("primarySubtitle") or {}).get("text", "")
                or (entity.get("subtitle") or {}).get("text", "")
            )
            location = (entity.get("secondarySubtitle") or {}).get("text", "")

            tracking = hit.get("trackingUrn", "") or entity.get("trackingUrn", "")
            company_id = ""
            if tracking:
                m = re.search(r":company:(\d+)", tracking)
                if m:
                    company_id = m.group(1)

            companies.append({
                "company_id": company_id,
                "name": name.strip(),
                "linkedin_url": nav_url,
                "industry_size": industry_size,
                "location": location,
                "source": "voyager_api",
            })

    return companies


def _parse_company_voyager_profile(data: dict) -> dict:
    """Parse a Voyager /organization/companies/{id} response."""
    out: dict = {}

    out["name"] = data.get("name") or data.get("localizedName", "")
    out["description"] = data.get("description") or data.get("localizedDescription", "")
    out["website"] = data.get("companyPageUrl") or data.get("websiteUrl", "")
    out["employee_count"] = data.get("staffCount") or data.get("employeeCount", "")
    out["founded"] = (data.get("foundedOn") or {}).get("year", "")
    out["company_type"] = data.get("companyType", {}).get("localizedName", "")
    out["specialties"] = data.get("specialities", [])

    hq = data.get("headquarter") or {}
    city = hq.get("city", "")
    country = hq.get("country", "")
    out["headquarters"] = ", ".join(filter(None, [city, country]))

    follower_data = data.get("followingInfo") or {}
    out["followers"] = follower_data.get("followerCount", "")

    industries = data.get("industries", [])
    out["industries"] = [ind.get("localizedName", "") for ind in industries if isinstance(ind, dict)]

    return {k: v for k, v in out.items() if v or v == 0}


def _parse_company_html(html_page) -> dict:
    """HTML fallback parser for public LinkedIn company pages."""
    out: dict = {}

    full_text = " ".join(html_page.css("body *::text").get_all())

    name_el = html_page.css("h1").first
    if name_el:
        out["name"] = " ".join(name_el.css("::text").get_all()).strip()

    about_selectors = [
        ".org-about-us-organization-description__text",
        "[data-test-id='about-us__description']",
        ".org-about-module__description",
        "section.about p",
    ]
    for sel in about_selectors:
        els = html_page.css(sel)
        if els:
            out["description"] = " ".join(els.css("::text").get_all()).strip()
            break

    follower_m = re.search(r"([\d,]+)\s*follower", full_text, re.I)
    if follower_m:
        out["followers"] = int(follower_m.group(1).replace(",", ""))

    size_m = re.search(
        r"(\d[\d,]*\s*[-–]\s*\d[\d,]*|\d[\d,]+\+?)\s*employees?", full_text, re.I
    )
    if size_m:
        out["employee_count"] = size_m.group(0).strip()

    website_els = html_page.css(
        "a[data-control-name='visit_company_website'], "
        ".org-about-us-organization-description a[href*='http']"
    )
    if website_els:
        out["website"] = website_els.first.attrib.get("href", "")

    return {k: v for k, v in out.items() if v}


# ── Public API ────────────────────────────────────────────────────────────────

def search_companies(
    keywords: str = "health tech",
    industries: list[str] | None = None,
    location: str = "",
    count: int = 25,
    headless: bool = False,
    cookies: dict | None = None,
    wait_seconds: int = 8,
) -> list[dict]:
    """
    Search LinkedIn for health tech companies via Voyager API interception.

    Args:
        keywords:   Search terms e.g. "digital health", "telehealth", "healthtech"
        industries: Keys from HEALTH_INDUSTRIES (None = all health industries)
        location:   Key from GEO_URNS or raw URN string
        count:      Target number of results (LinkedIn paginates at 10)
        headless:   False = visible browser (recommended for first run / login)
        cookies:    LinkedIn session cookies (None = auto-load from env/file)
        wait_seconds: Wait time for Voyager API responses

    Returns:
        List of company dicts with: company_id, name, linkedin_url,
        industry_size, location, source
    """
    from playwright.sync_api import sync_playwright

    if cookies is None:
        cookies = load_linkedin_cookies()

    if not cookies.get("li_at"):
        console.print("[yellow]No li_at cookie found.[/yellow]")
        console.print("[dim]Set LINKEDIN_LI_AT env var or add cookies/linkedin.json[/dim]")
        console.print("[dim]Running with --no-headless allows manual login.[/dim]")

    geo_urn = GEO_URNS.get(location, location) if location else ""
    ind_filter = ""
    if industries:
        codes = [HEALTH_INDUSTRIES.get(i, i) for i in industries]
        ind_filter = "&".join(f"facetIndustry={c}" for c in codes)
    else:
        all_codes = list(HEALTH_INDUSTRIES.values())
        ind_filter = "&".join(f"facetIndustry={c}" for c in all_codes)

    encoded_kw = keywords.replace(" ", "%20")
    base_search = (
        f"https://www.linkedin.com/search/results/companies/"
        f"?keywords={encoded_kw}&{ind_filter}"
    )
    if geo_urn:
        base_search += f"&geoUrn={geo_urn.replace(':', '%3A')}"

    captured: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )

        if cookies:
            context.add_cookies(_cookies_to_playwright(cookies))

        page = context.new_page()

        def on_response(response):
            url = response.url
            if "voyager/api/search/blended" in url or "voyager/api/search/cluster" in url:
                try:
                    body = response.body()
                    data = json.loads(body)
                    hits = _parse_voyager_search(data)
                    captured.extend(hits)
                    console.print(f"  [green]Voyager:[/green] +{len(hits)} companies (total {len(captured)})")
                except Exception:
                    pass

        page.on("response", on_response)

        console.print(f"  [dim]Searching:[/dim] {base_search[:80]}...")
        page.goto(base_search, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        time.sleep(wait_seconds)

        # Scroll to load more results
        pages_loaded = 1
        while len(captured) < count and pages_loaded < 5:
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(random.uniform(1.0, 2.0))

            # Click "Next" pagination if present
            next_btn = page.query_selector("button[aria-label='Next']")
            if next_btn:
                next_btn.click()
                time.sleep(random.uniform(2.5, 4.0))
                pages_loaded += 1
            else:
                break

        browser.close()

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for c in captured:
        key = c.get("company_id") or c["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    console.print(f"  [bold green]Companies found:[/bold green] {len(unique)}")
    return unique[:count]


def get_company_profile(
    linkedin_url: str,
    cookies: dict | None = None,
    headless: bool = False,
    wait_seconds: int = 6,
) -> dict:
    """
    Fetch full company profile from a LinkedIn company URL.
    Combines Voyager API data with HTML fallback.

    Args:
        linkedin_url: Full LinkedIn company URL or just the slug (e.g. "stripe")
        cookies:      LinkedIn session cookies
        headless:     Run browser headless

    Returns:
        Company dict with: name, description, website, employee_count,
        headquarters, founded, specialties, industries, followers
    """
    from playwright.sync_api import sync_playwright

    if cookies is None:
        cookies = load_linkedin_cookies()

    if not linkedin_url.startswith("http"):
        linkedin_url = f"https://www.linkedin.com/company/{linkedin_url}"

    company: dict = {"linkedin_url": linkedin_url, "source": "company_profile"}
    voyager_profile: dict = {}
    page_html: str = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        if cookies:
            context.add_cookies(_cookies_to_playwright(cookies))

        page = context.new_page()

        def on_response(response):
            url = response.url
            if (
                "voyager/api/organization/companies" in url
                or "voyager/api/entities?ids=List" in url
                or "voyager/api/organization/companiesV2" in url
            ):
                try:
                    data = json.loads(response.body())
                    voyager_profile.update(data)
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(linkedin_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        time.sleep(wait_seconds)

        # Navigate to /about for extra company details
        about_url = linkedin_url.rstrip("/") + "/about/"
        page.goto(about_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        page_html = page.content()
        browser.close()

    # Parse HTML fallback
    try:
        from scrapling.parser import Adaptor
        page_obj = Adaptor(page_html, auto_match=False)
        html_data = _parse_company_html(page_obj)
        company.update(html_data)
    except Exception:
        pass

    # Overlay with Voyager data (higher quality)
    if voyager_profile:
        voyager_parsed = _parse_company_voyager_profile(voyager_profile)
        company.update({k: v for k, v in voyager_parsed.items() if v})

    return company


def bulk_enrich_companies(
    companies: list[dict],
    cookies: dict | None = None,
    headless: bool = False,
    delay: float = 3.0,
) -> list[dict]:
    """
    Enrich a list of company stubs (from search_companies) with full profiles.
    Adds: description, website, employee_count, headquarters, founded, specialties.

    Args:
        companies:  List of dicts with at least 'linkedin_url'
        delay:      Seconds between requests (respect rate limits)

    Returns:
        List of enriched company dicts
    """
    if cookies is None:
        cookies = load_linkedin_cookies()

    enriched: list[dict] = []
    for i, c in enumerate(companies):
        url = c.get("linkedin_url", "")
        if not url:
            enriched.append(c)
            continue

        console.print(f"  [{i+1}/{len(companies)}] Enriching: [cyan]{c.get('name', url)}[/cyan]")
        try:
            profile = get_company_profile(url, cookies=cookies, headless=headless)
            merged = {**c, **profile}
            enriched.append(merged)
        except Exception as e:
            console.print(f"    [red]Error:[/red] {e}")
            enriched.append(c)

        time.sleep(delay + random.uniform(0, 1.5))

    return enriched
