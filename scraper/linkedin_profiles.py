"""
B) LinkedIn Profile Extractor — Health Tech Recruiting
Dual strategy:
  1. Voyager API interception (requires li_at cookie)
  2. HTML fallback for public profiles
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

# Health tech roles for recruiting
HEALTH_TECH_TITLES = [
    "CTO", "Chief Technology Officer",
    "VP Engineering", "Head of Engineering",
    "CEO", "Founder", "Co-Founder",
    "CPO", "Chief Product Officer",
    "CMO", "Chief Medical Officer",
    "CIO", "Chief Information Officer",
    "Director of Engineering",
    "VP Product",
    "Health Informatics",
    "Digital Health",
    "Medical Director",
    "Clinical Informatics",
    "Healthcare IT",
    "Telemedicine",
    "Health Technology",
]

# Seniority filter codes (LinkedIn internal)
SENIORITY_CODES = {
    "c_suite": "10",
    "vp": "9",
    "director": "8",
    "manager": "7",
    "senior": "6",
    "entry": "3",
}

# Industry codes (same as companies)
HEALTH_INDUSTRIES = {
    "hospital_healthcare": "14",
    "health_wellness_fitness": "96",
    "biotechnology": "42",
    "pharmaceuticals": "82",
    "medical_devices": "74",
    "mental_health": "139",
    "medical_practice": "54",
}

GEO_URNS = {
    "usa": "urn:li:geo:103644278",
    "latam": "urn:li:geo:91000001",
    "mexico": "urn:li:geo:103323778",
    "colombia": "urn:li:geo:100876405",
    "brazil": "urn:li:geo:106057199",
    "uk": "urn:li:geo:101165590",
    "spain": "urn:li:geo:105646813",
}


# ── Voyager parsers ───────────────────────────────────────────────────────────

def _parse_voyager_people_search(json_data: dict) -> list[dict]:
    """Parse Voyager blended search response into people records."""
    people: list[dict] = []

    top_level = (
        json_data.get("data", {}).get("elements", [])
        or json_data.get("elements", [])
    )

    for group in top_level:
        hits = group.get("elements", [group]) if isinstance(group, dict) else []
        for hit in hits:
            entity = (
                hit.get("entityResult")
                or hit.get("member")
                or hit.get("entityLockupView")
                or hit
            )
            if not entity or not isinstance(entity, dict):
                continue

            name = (
                (entity.get("title") or {}).get("text", "")
                or entity.get("firstName", "")
                or (entity.get("primaryText") or {}).get("text", "")
            )
            if not name or name.lower() == "linkedin member":
                continue

            headline = (
                (entity.get("primarySubtitle") or {}).get("text", "")
                or (entity.get("subtitle") or {}).get("text", "")
            )
            location = (entity.get("secondarySubtitle") or {}).get("text", "")

            nav_url = entity.get("navigationUrl", "") or entity.get("url", "")
            if nav_url and not nav_url.startswith("http"):
                nav_url = f"https://www.linkedin.com{nav_url}"

            # Extract profile ID from tracking URN
            tracking = hit.get("trackingUrn", "") or entity.get("trackingUrn", "")
            profile_id = ""
            if tracking:
                m = re.search(r":member:(\d+)", tracking)
                if m:
                    profile_id = m.group(1)

            # Snippet (summary teaser)
            snippet = ""
            for snap in entity.get("insightViewModel", {}).get("insightComponents", []):
                text = (snap.get("lockupViewModel") or {}).get("title", {}).get("text", "")
                if text:
                    snippet = text
                    break

            people.append({
                "profile_id": profile_id,
                "name": name.strip(),
                "headline": headline,
                "location": location,
                "linkedin_url": nav_url,
                "snippet": snippet,
                "source": "voyager_search",
            })

    return people


def _parse_profile_voyager(data: dict) -> dict:
    """Parse a Voyager /identity/profiles/{id} response."""
    out: dict = {}

    out["first_name"] = data.get("firstName", "")
    out["last_name"] = data.get("lastName", "")
    out["name"] = f"{out['first_name']} {out['last_name']}".strip()
    out["headline"] = data.get("headline", "")
    out["summary"] = data.get("summary", "")
    out["location"] = (data.get("locationName") or data.get("geoLocationName", ""))
    out["connections"] = data.get("connectionsCount", "")

    geo = data.get("geoCountryName") or data.get("geoRegionName", "")
    if geo:
        out["country"] = geo

    industry = data.get("industryName", "")
    if industry:
        out["industry"] = industry

    return {k: v for k, v in out.items() if v or v == 0}


def _parse_profile_html(html_page) -> dict:
    """HTML fallback parser for public LinkedIn profile pages."""
    out: dict = {}
    full_text = " ".join(html_page.css("body *::text").get_all())

    name_el = html_page.css("h1").first
    if name_el:
        out["name"] = " ".join(name_el.css("::text").get_all()).strip()

    headline_els = html_page.css(
        ".top-card-layout__headline, "
        ".pv-text-details__left-panel .text-body-medium, "
        "[data-generated-suggestion-target='headline']"
    )
    if headline_els:
        out["headline"] = " ".join(headline_els.first.css("::text").get_all()).strip()

    location_els = html_page.css(
        ".top-card__subline-item, "
        ".pv-text-details__left-panel .text-body-small"
    )
    if location_els:
        out["location"] = " ".join(location_els.first.css("::text").get_all()).strip()

    about_els = html_page.css(
        ".core-section-container__content .pv-shared-text-with-see-more, "
        "#about ~ div .visually-hidden, "
        ".summary"
    )
    if about_els:
        out["summary"] = " ".join(about_els.first.css("::text").get_all()).strip()[:1000]

    # Connections count
    conn_m = re.search(r"([\d,]+)\s*connections?", full_text, re.I)
    if conn_m:
        out["connections"] = conn_m.group(1).replace(",", "")

    # Current position
    experience_els = html_page.css(
        ".experience-item, "
        ".pvs-list__item--line-separated:first-child"
    )
    if experience_els:
        title_el = experience_els.first.css("span[aria-hidden='true']").first
        if title_el:
            out["current_title"] = " ".join(title_el.css("::text").get_all()).strip()

    return {k: v for k, v in out.items() if v}


def _parse_experience_voyager(positions_data: dict) -> list[dict]:
    """Parse Voyager positions/experience response."""
    positions: list[dict] = []

    elements = (
        positions_data.get("elements", [])
        or (positions_data.get("data", {}) or {}).get("elements", [])
    )

    for pos in elements:
        entity = pos.get("entityLockupView") or pos
        title = (entity.get("title") or {}).get("text", "")
        company_el = (entity.get("subtitle") or {}).get("text", "")
        date_range = (entity.get("metadata") or {}).get("text", "")
        desc_el = (entity.get("description") or {}).get("text", "")

        if title:
            positions.append({
                "title": title,
                "company": company_el,
                "date_range": date_range,
                "description": desc_el[:300] if desc_el else "",
            })

    return positions


# ── Public API ────────────────────────────────────────────────────────────────

def search_people(
    keywords: str = "health tech",
    titles: list[str] | None = None,
    industries: list[str] | None = None,
    seniority: list[str] | None = None,
    location: str = "",
    count: int = 25,
    headless: bool = False,
    cookies: dict | None = None,
    wait_seconds: int = 8,
) -> list[dict]:
    """
    Search LinkedIn for health tech professionals via Voyager API interception.

    Args:
        keywords:   Search terms e.g. "digital health startup", "telemedicine"
        titles:     Job title filters e.g. ["CTO", "VP Engineering"] (None = no filter)
        industries: Keys from HEALTH_INDUSTRIES (None = all health industries)
        seniority:  Keys from SENIORITY_CODES e.g. ["c_suite", "vp"]
        location:   Key from GEO_URNS or raw URN string
        count:      Target results count
        headless:   False = visible browser
        cookies:    LinkedIn session cookies (None = auto-load)
        wait_seconds: Wait time for API responses

    Returns:
        List of profile dicts with: profile_id, name, headline, location,
        linkedin_url, snippet
    """
    from playwright.sync_api import sync_playwright
    from scraper.linkedin_companies import load_linkedin_cookies, _cookies_to_playwright

    if cookies is None:
        cookies = load_linkedin_cookies()

    if not cookies.get("li_at"):
        console.print("[yellow]No li_at cookie found — people search requires login.[/yellow]")
        console.print("[dim]Set LINKEDIN_LI_AT env var or add cookies/linkedin.json[/dim]")

    # Build search URL
    encoded_kw = keywords.replace(" ", "%20")
    base_search = f"https://www.linkedin.com/search/results/people/?keywords={encoded_kw}"

    if titles:
        title_filter = "%2C".join(t.replace(" ", "%20") for t in titles[:3])
        base_search += f"&titleFreeText={title_filter}"

    if industries:
        codes = [HEALTH_INDUSTRIES.get(i, i) for i in industries]
        base_search += "&" + "&".join(f"facetIndustry={c}" for c in codes)
    else:
        all_codes = list(HEALTH_INDUSTRIES.values())
        base_search += "&" + "&".join(f"facetIndustry={c}" for c in all_codes)

    if seniority:
        codes = [SENIORITY_CODES.get(s, s) for s in seniority]
        base_search += "&" + "&".join(f"facetSeniority={c}" for c in codes)

    if location:
        geo = GEO_URNS.get(location, location)
        base_search += f"&geoUrn={geo.replace(':', '%3A')}"

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
                    hits = _parse_voyager_people_search(data)
                    captured.extend(hits)
                    console.print(f"  [green]Voyager:[/green] +{len(hits)} profiles (total {len(captured)})")
                except Exception:
                    pass

        page.on("response", on_response)

        console.print(f"  [dim]Searching people:[/dim] {base_search[:80]}...")
        page.goto(base_search, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        time.sleep(wait_seconds)

        pages_loaded = 1
        while len(captured) < count and pages_loaded < 5:
            for _ in range(4):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(random.uniform(1.0, 2.0))

            next_btn = page.query_selector("button[aria-label='Next']")
            if next_btn:
                next_btn.click()
                time.sleep(random.uniform(3.0, 5.0))
                pages_loaded += 1
            else:
                break

        browser.close()

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for p in captured:
        key = p.get("profile_id") or p["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(p)

    console.print(f"  [bold green]Profiles found:[/bold green] {len(unique)}")
    return unique[:count]


def get_person_profile(
    linkedin_url: str,
    cookies: dict | None = None,
    headless: bool = False,
    wait_seconds: int = 6,
    include_experience: bool = True,
) -> dict:
    """
    Fetch full profile from a LinkedIn person URL.
    Combines Voyager API + HTML fallback.

    Args:
        linkedin_url:       Full LinkedIn profile URL or username slug
        cookies:            LinkedIn session cookies
        headless:           Run browser headless
        include_experience: Also capture work experience history

    Returns:
        Profile dict with: name, headline, summary, location, connections,
        current_title, industry, experience (list)
    """
    from playwright.sync_api import sync_playwright
    from scraper.linkedin_companies import load_linkedin_cookies, _cookies_to_playwright

    if cookies is None:
        cookies = load_linkedin_cookies()

    if not linkedin_url.startswith("http"):
        linkedin_url = f"https://www.linkedin.com/in/{linkedin_url}"

    profile: dict = {"linkedin_url": linkedin_url, "source": "person_profile"}
    voyager_identity: dict = {}
    voyager_positions: dict = {}
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
            if "voyager/api/identity/profiles" in url and "/profileView" not in url:
                try:
                    data = json.loads(response.body())
                    voyager_identity.update(data)
                except Exception:
                    pass
            if "voyager/api/identity/profiles" in url and "positions" in url:
                try:
                    data = json.loads(response.body())
                    voyager_positions.update(data)
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(linkedin_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Scroll to trigger experience section load
        if include_experience:
            for _ in range(5):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(random.uniform(0.8, 1.5))

        time.sleep(wait_seconds)
        page_html = page.content()
        browser.close()

    # Parse HTML fallback
    try:
        from scrapling.parser import Adaptor
        page_obj = Adaptor(page_html, auto_match=False)
        html_data = _parse_profile_html(page_obj)
        profile.update(html_data)
    except Exception:
        pass

    # Overlay Voyager identity
    if voyager_identity:
        voyager_data = _parse_profile_voyager(voyager_identity)
        profile.update({k: v for k, v in voyager_data.items() if v})

    # Parse experience
    if include_experience and voyager_positions:
        positions = _parse_experience_voyager(voyager_positions)
        if positions:
            profile["experience"] = positions
            if positions and not profile.get("current_title"):
                profile["current_title"] = positions[0].get("title", "")
                profile["current_company"] = positions[0].get("company", "")

    return profile


def build_recruiting_list(
    keywords: str = "digital health",
    titles: list[str] | None = None,
    location: str = "",
    count: int = 20,
    enrich: bool = True,
    cookies: dict | None = None,
    headless: bool = False,
    delay: float = 4.0,
) -> list[dict]:
    """
    High-level recruiting pipeline: search + enrich profiles for health tech hiring.

    Searches for people, then optionally enriches each profile with full details.
    Adds an 'outreach_priority' score based on title seniority.

    Args:
        keywords:   Search keywords
        titles:     Filter by job titles (None = all health tech titles)
        location:   GEO_URNS key or URN
        count:      Number of profiles to find
        enrich:     Fetch full profile for each result
        delay:      Seconds between profile fetches

    Returns:
        Sorted list of profile dicts (highest seniority first)
    """
    from scraper.linkedin_companies import load_linkedin_cookies

    if cookies is None:
        cookies = load_linkedin_cookies()

    if titles is None:
        titles = ["CTO", "Founder", "CEO", "VP Engineering", "CPO"]

    console.print(f"[bold]Recruiting search:[/bold] {keywords} | titles: {titles}")
    profiles = search_people(
        keywords=keywords,
        titles=titles,
        location=location,
        count=count,
        headless=headless,
        cookies=cookies,
    )

    if enrich and profiles:
        console.print(f"\n[bold]Enriching {len(profiles)} profiles...[/bold]")
        enriched: list[dict] = []
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
            time.sleep(delay + random.uniform(0, 2.0))
        profiles = enriched

    # Score by seniority
    SENIORITY_SCORE = {
        "ceo": 10, "cto": 10, "coo": 9, "cpo": 9, "cmo": 8, "cio": 8,
        "founder": 10, "co-founder": 10, "cofounder": 10,
        "president": 9, "vp": 8, "vice president": 8,
        "director": 7, "head": 7, "lead": 6, "senior": 5, "principal": 6,
    }

    def _score(p: dict) -> int:
        headline = (p.get("headline") or p.get("current_title") or "").lower()
        for kw, score in SENIORITY_SCORE.items():
            if kw in headline:
                return score
        return 1

    profiles.sort(key=_score, reverse=True)
    for p in profiles:
        p["outreach_priority"] = _score(p)

    return profiles
