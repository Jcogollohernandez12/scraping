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

        console.print(f"  [dim]Searching people:[/dim] {base_search[:80]}...")
        try:
            page.goto(base_search, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        if "login" in page.url or "authwall" in page.url:
            console.print("[red]LinkedIn redirigió al login — sesión expirada.[/red]")
            browser.close()
            return []

        # Smart wait: try known selectors first, then fall back to fixed sleep
        result_selectors = [
            "li.reusable-search__result-container",
            "li[class*='result-container']",
            ".entity-result",
            ".search-results-container li",
        ]
        for sel in result_selectors:
            try:
                page.wait_for_selector(sel, timeout=12000)
                break
            except Exception:
                continue
        else:
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(1.5)
            time.sleep(max(wait_seconds - 4, 3))

        time.sleep(2)  # Let JS fully populate cards

        def _extract_people_from_page(pg) -> list[dict]:
            return pg.evaluate("""
            () => {
                const people = [];
                const getText = (el) => {
                    if (!el) return '';
                    const h = el.querySelector('span[aria-hidden="true"]') ||
                               el.querySelector('span[aria-hidden]');
                    return (h ? h.innerText : el.innerText || '').trim();
                };
                const cleanUrl = (href) => href ? href.split('?')[0].replace(/\\/$/, '') : '';

                // Strategy 1: known card containers
                const cardSelectors = [
                    'li.reusable-search__result-container',
                    'li[class*="result-container"]',
                    '.entity-result',
                    '[data-view-name="search-entity-result-universal-template"]',
                    '.search-results-container > ul > li',
                ];
                let cards = [];
                for (const sel of cardSelectors) {
                    cards = Array.from(document.querySelectorAll(sel));
                    if (cards.length > 0) break;
                }

                if (cards.length > 0) {
                    cards.forEach(card => {
                        const linkEl = card.querySelector('a[href*="/in/"]');
                        if (!linkEl) return;
                        const href = cleanUrl(linkEl.href);
                        const name = getText(linkEl) || getText(card.querySelector('h3, h4'));
                        if (!name || name.length < 2) return;

                        const sub1 = card.querySelector(
                            '.entity-result__primary-subtitle, [class*="primary-subtitle"]'
                        );
                        const sub2 = card.querySelector(
                            '.entity-result__secondary-subtitle, [class*="secondary-subtitle"]'
                        );
                        people.push({
                            name, linkedin_url: href,
                            headline: sub1 ? sub1.innerText.trim() : '',
                            location: sub2 ? sub2.innerText.trim() : '',
                            profile_id: '', snippet: '', source: 'dom_card',
                        });
                    });
                    if (people.length > 0) return people;
                }

                // Strategy 2: find /in/ links — accept li OR div containers
                const SKIP_UI = new Set(['Conectar', 'Connect', 'Seguir', 'Follow',
                                          'Mensaje', 'Message', 'Pending', '·', '•']);
                const root = document.querySelector('.scaffold-layout__main') ||
                             document.querySelector('main') || document.body;
                const seen = new Set();
                root.querySelectorAll('a[href*="/in/"]').forEach(link => {
                    const href = cleanUrl(link.href);
                    if (!href || seen.has(href)) return;
                    if (link.closest('nav,header,footer,aside')) return;
                    // Skip messaging and undefined profile links
                    if (href.endsWith('/messaging') || href.includes('/in/undefined')) return;
                    // Only top-level profile URLs (no sub-paths)
                    const tail = href.replace(/.*\\/in\\/[^/]+/, '');
                    if (tail && tail.length > 1) return;
                    seen.add(href);
                    const name = getText(link);
                    if (!name || name.length < 2 || name.length > 80) return;
                    // Container: accept li or div
                    const container = link.closest('li') ||
                                      link.closest('div[class]') ||
                                      link.parentElement;
                    let headline = '', location = '';
                    if (container) {
                        const leaves = [];
                        container.querySelectorAll('span,div,p').forEach(el => {
                            const childElems = Array.from(el.children).filter(
                                c => !['SPAN','A','B','EM'].includes(c.tagName));
                            if (childElems.length > 0) return;
                            const t = el.innerText.trim();
                            if (t && t !== name && t.length > 2 && t.length < 120 &&
                                !SKIP_UI.has(t) && !t.includes('\\n')) leaves.push(t);
                        });
                        const uniq = [...new Set(leaves)];
                        headline = uniq[0] || '';
                        location = uniq[1] || '';
                    }
                    people.push({ name, linkedin_url: href, headline, location,
                                  profile_id: '', snippet: '', source: 'dom_link' });
                });
                return people;
            }
            """) or []

        batch = _extract_people_from_page(page)
        if batch:
            captured.extend(batch)
            console.print(f"  [green]Página 1:[/green] +{len(batch)} perfiles")
        else:
            # Scroll and retry once
            for _ in range(5):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(1.5)
            batch = _extract_people_from_page(page)
            if batch:
                captured.extend(batch)
                console.print(f"  [green]Tras scroll:[/green] +{len(batch)} perfiles")
            else:
                title = page.title()
                snippet = page.evaluate("() => document.body.innerText.slice(0, 300)")
                console.print(f"  [dim]Título: {title}[/dim]")
                console.print(f"  [dim]Página: {snippet!r}[/dim]")

        # Paginate
        page_num = 1
        while len(captured) < count and page_num < 8:
            try:
                next_btn = page.query_selector("button[aria-label='Next']")
                if not next_btn:
                    next_url = base_search + f"&page={page_num + 1}"
                    page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(wait_seconds)
                else:
                    next_btn.click()
                    time.sleep(random.uniform(3, 5))
                batch = _extract_people_from_page(page)
                if not batch:
                    break
                captured.extend(batch)
                console.print(f"  [green]Página {page_num + 1}:[/green] +{len(batch)} (total {len(captured)})")
                page_num += 1
            except Exception as e:
                console.print(f"  [dim]Paginación detenida: {e}[/dim]")
                break

        browser.close()

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for prof in captured:
        key = prof.get("profile_id") or prof.get("linkedin_url") or prof.get("name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(prof)

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
    dom_data: dict = {}

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

        try:
            page.goto(linkedin_url, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        # Scroll to trigger lazy-loaded sections
        for _ in range(5 if include_experience else 2):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            time.sleep(random.uniform(0.8, 1.5))

        time.sleep(wait_seconds)

        # Extract via DOM evaluation
        dom_data = page.evaluate("""
        () => {
            const getText = (sel) => {
                const el = document.querySelector(sel);
                if (!el) return '';
                const h = el.querySelector('span[aria-hidden="true"]') ||
                           el.querySelector('span[aria-hidden]');
                return (h ? h.innerText : el.innerText || '').trim();
            };
            const getAllText = (sel) => Array.from(document.querySelectorAll(sel))
                .map(e => {
                    const h = e.querySelector('span[aria-hidden="true"]');
                    return (h ? h.innerText : e.innerText || '').trim();
                }).filter(Boolean);
            const body = document.body.innerText || '';

            // Name
            const name = getText('h1') || getText('.pv-text-details__left-panel h1');

            // Headline
            const headline = getText('.pv-text-details__left-panel .text-body-medium') ||
                             getText('[data-generated-suggestion-target]') ||
                             getText('.top-card-layout__headline');

            // Location
            const location = getText('.pv-text-details__left-panel .text-body-small[class*="break-words"]') ||
                             getText('.top-card__subline-item');

            // About / summary
            const summary = getText('#about ~ div .visually-hidden') ||
                            getText('.pv-shared-text-with-see-more .visually-hidden') ||
                            getText('.summary');

            // Connections
            const connMatch = body.match(/([\\d,]+)\\s*connections?/i);
            const connections = connMatch ? connMatch[1].replace(/,/g,'') : '';

            // Current company from experience section
            const expSections = document.querySelectorAll(
                '[id="experience"] ~ div li, ' +
                '.pvs-list__item--line-separated'
            );
            let current_title = '', current_company = '';
            if (expSections.length > 0) {
                const first = expSections[0];
                const spans = Array.from(first.querySelectorAll('span[aria-hidden="true"]'))
                    .map(s => s.innerText.trim()).filter(Boolean);
                current_title = spans[0] || '';
                current_company = spans[1] || '';
            }

            // Experience items
            const experience = [];
            expSections.forEach((sec, i) => {
                if (i >= 10) return;
                const spans = Array.from(sec.querySelectorAll('span[aria-hidden="true"]'))
                    .map(s => s.innerText.trim()).filter(Boolean);
                if (spans[0]) {
                    experience.push({
                        title: spans[0] || '',
                        company: spans[1] || '',
                        date_range: spans[2] || '',
                        description: '',
                    });
                }
            });

            return { name, headline, location, summary, connections,
                     current_title, current_company, experience };
        }
        """)

        browser.close()

    if dom_data:
        profile.update({k: v for k, v in dom_data.items() if v and k != "experience"})
        if include_experience and dom_data.get("experience"):
            profile["experience"] = dom_data["experience"]

    return {k: v for k, v in profile.items() if v or v == 0}


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
