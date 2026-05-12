"""
A) LinkedIn Company Extractor — Health Tech
Strategy: Playwright browser + DOM extraction from rendered page.
LinkedIn renders results client-side; we let the page fully render then extract.
"""
from __future__ import annotations

import json
import os
import re
import time
import random
from pathlib import Path

from rich.console import Console

console = Console()

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
    """
    Load LinkedIn session cookies.
    Merges file (all 48+ cookies) + env vars, env vars take priority.
    """
    cookies: dict[str, str] = {}

    # Load ALL cookies from file for a complete session
    cookies_file = Path("cookies/linkedin.json")
    if cookies_file.exists():
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

    # Env vars override file
    li_at = os.getenv("LINKEDIN_LI_AT", "").strip()
    jsessionid = os.getenv("LINKEDIN_JSESSIONID", "").strip()
    if li_at:
        cookies["li_at"] = li_at
    if jsessionid:
        cookies["JSESSIONID"] = f'"{jsessionid}"' if not jsessionid.startswith('"') else jsessionid

    return cookies


def _cookies_to_playwright(cookies: dict[str, str]) -> list[dict]:
    return [
        {"name": k, "value": v, "domain": ".linkedin.com", "path": "/"}
        for k, v in cookies.items()
        if v
    ]


# ── DOM extraction from rendered page ────────────────────────────────────────

def _extract_companies_from_page(page) -> list[dict]:
    """
    Extract company cards from a rendered LinkedIn search results page.
    Uses baseCompanyUrl() to normalize all link variants to the same slug URL.
    """
    results = page.evaluate("""
    () => {
        // Strip sub-paths and query params → linkedin.com/company/slug only
        const baseUrl = (href) => {
            if (!href) return '';
            const m = href.match(
                /(https?:\\/\\/(?:www\\.)?linkedin\\.com\\/company\\/[A-Za-z0-9_%-]+)/i
            );
            return m ? m[1] : '';
        };
        const getAriaText = (el) => {
            if (!el) return '';
            const h = el.querySelector('span[aria-hidden="true"]') ||
                       el.querySelector('span[aria-hidden]');
            return (h ? h.innerText : el.innerText || '').trim();
        };
        const SKIP = new Set(['Seguir','Follow','Conectar','Connect',
                               'Pending','Pendiente','·','•','Ver más','See more',
                               'Reactivar','Premium','Mensaje','Message']);

        // ── Strategy 1: known card-container class selectors ──────────────
        const cardSelectors = [
            'li.reusable-search__result-container',
            'li[class*="result-container"]',
            '.entity-result',
            '[data-view-name="search-entity-result-universal-template"]',
            'div[data-chameleon-result-urn]',
        ];
        for (const sel of cardSelectors) {
            const cards = Array.from(document.querySelectorAll(sel));
            if (cards.length === 0) continue;
            const out = [];
            cards.forEach(card => {
                const linkEl = card.querySelector('a[href*="/company/"]');
                if (!linkEl) return;
                const href = baseUrl(linkEl.href);
                if (!href) return;
                const name = getAriaText(linkEl) || getAriaText(card.querySelector('h3,h4'));
                if (!name || name.length < 2) return;
                const sub1 = card.querySelector(
                    '.entity-result__primary-subtitle,[class*="primary-subtitle"]');
                const sub2 = card.querySelector(
                    '.entity-result__secondary-subtitle,[class*="secondary-subtitle"]');
                out.push({ name, linkedin_url: href,
                           industry_size: sub1 ? sub1.innerText.trim() : '',
                           location: sub2 ? sub2.innerText.trim() : '',
                           company_id: '', source: 'card' });
            });
            if (out.length > 0) return out;
        }

        // ── Strategy 2: scan main content for ALL /company/ links ─────────
        // baseUrl() normalizes /company/slug/life/?trk=... → /company/slug
        // so all link variants for the same company collapse to one entry.
        const root = document.querySelector('.scaffold-layout__main') ||
                     document.querySelector('main') || document.body;

        const seen = new Set();
        const out = [];

        root.querySelectorAll('a[href*="/company/"]').forEach(link => {
            if (link.closest('nav,header,footer')) return;
            const href = baseUrl(link.href);
            if (!href || seen.has(href)) return;
            seen.add(href);

            const name = getAriaText(link);
            if (!name || name.length < 2 || name.length > 120) return;

            // Accept li OR any classed div as the card container
            const container = link.closest('li') ||
                              link.closest('div[class]') ||
                              link.parentElement;
            let industry_size = '', location = '';
            if (container) {
                const leaves = [];
                container.querySelectorAll('span,div,p').forEach(el => {
                    // Only process leaf-ish elements (no block sub-elements)
                    const hasBlock = Array.from(el.children).some(
                        c => !['SPAN','A','B','EM','STRONG','I'].includes(c.tagName));
                    if (hasBlock) return;
                    const t = el.innerText.trim();
                    if (t && t !== name && t.length > 2 && t.length < 100 &&
                        !SKIP.has(t) && !t.includes('\\n')) leaves.push(t);
                });
                const uniq = [...new Set(leaves)];
                industry_size = uniq[0] || '';
                location = uniq[1] || '';
            }
            out.push({ name, linkedin_url: href, industry_size, location,
                       company_id: '', source: 'link_scan' });
        });

        return out;
    }
    """)

    return results or []


def _extract_total_results(page) -> int:
    """Get the total number of results shown by LinkedIn."""
    try:
        text = page.evaluate("""
        () => {
            const el = document.querySelector(
                '.search-results-container h2, ' +
                '.pb2.t-black--light.t-14, ' +
                'div[class*="results"] h2'
            );
            return el ? el.innerText : '';
        }
        """)
        m = re.search(r"([\d,\.]+)", text or "")
        if m:
            return int(m.group(1).replace(",", "").replace(".", ""))
    except Exception:
        pass
    return 0


# ── Public API ────────────────────────────────────────────────────────────────

def search_companies(
    keywords: str = "health tech",
    industries: list[str] | None = None,
    location: str = "",
    count: int = 25,
    headless: bool = False,
    cookies: dict | None = None,
    wait_seconds: int = 10,
) -> list[dict]:
    """
    Search LinkedIn for health tech companies.
    Uses a real browser to let the page render, then extracts from the DOM.

    Args:
        keywords:     Search terms e.g. "digital health", "telehealth"
        industries:   Keys from HEALTH_INDUSTRIES (None = no industry filter)
        location:     Key from GEO_URNS or raw URN string
        count:        Number of results to return
        headless:     True = hidden browser, False = visible (default)
        wait_seconds: Seconds to wait for page to render results (default 10)

    Returns:
        List of company dicts: company_id, name, linkedin_url,
        industry_size, location, source
    """
    from playwright.sync_api import sync_playwright

    if cookies is None:
        cookies = load_linkedin_cookies()

    has_li_at = bool(cookies.get("li_at"))
    console.print(f"  [dim]Cookies:[/dim] {len(cookies)} | li_at: {'✅' if has_li_at else '❌'}")

    if not has_li_at:
        console.print("[red]No hay cookie li_at.[/red]")
        console.print("[dim]Corre: python3 main.py linkedin-login --email EMAIL --password PASS[/dim]")
        return []

    # Build search URL (keywords only — simple and reliable)
    import urllib.parse
    base_search = (
        f"https://www.linkedin.com/search/results/companies/"
        f"?keywords={urllib.parse.quote(keywords)}&origin=GLOBAL_SEARCH_HEADER"
    )

    # Industry filter: LinkedIn URL format is facetIndustry=["14","96"]
    if industries:
        codes = [HEALTH_INDUSTRIES.get(i, i) for i in industries]
        base_search += f"&facetIndustry={urllib.parse.quote(json.dumps(codes))}"

    if location:
        geo = GEO_URNS.get(location, location)
        base_search += f"&geoUrn={urllib.parse.quote(geo)}"

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
        context.add_cookies(_cookies_to_playwright(cookies))
        page = context.new_page()

        console.print(f"  [dim]Abriendo:[/dim] {base_search[:90]}...")
        try:
            page.goto(base_search, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            pass

        # Check for login wall
        current_url = page.url
        if "login" in current_url or "authwall" in current_url:
            console.print("[red]LinkedIn redirigió al login — sesión expirada.[/red]")
            console.print("[dim]Corre: python3 main.py linkedin-login --email EMAIL --password PASS[/dim]")
            browser.close()
            return []

        # Wait for results to appear — try smart wait first, fall back to fixed sleep
        console.print("  [dim]Esperando resultados...[/dim]")
        result_selectors = [
            "li.reusable-search__result-container",
            "li[class*='result-container']",
            ".entity-result",
            "div[data-chameleon-result-urn]",
            ".search-results-container li",
        ]
        smart_wait_ok = False
        for sel in result_selectors:
            try:
                page.wait_for_selector(sel, timeout=15000)
                console.print(f"  [dim]Resultados detectados con: {sel}[/dim]")
                smart_wait_ok = True
                break
            except Exception:
                continue

        if not smart_wait_ok:
            # Results not detected via selector — scroll to trigger lazy-load and wait
            console.print(f"  [dim]No detectados via selector. Scroll + espera {wait_seconds}s...[/dim]")
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 600)")
                time.sleep(1.5)
            time.sleep(max(wait_seconds - 4, 3))
        else:
            # Give JS a moment to fully populate all cards
            time.sleep(2)

        # Show how many results LinkedIn found
        total = _extract_total_results(page)
        if total:
            console.print(f"  [dim]LinkedIn reporta ~{total:,} resultados totales[/dim]")

        # Extract first page
        batch = _extract_companies_from_page(page)
        if batch:
            captured.extend(batch)
            console.print(f"  [green]Página 1:[/green] +{len(batch)} empresas")
        else:
            # Scroll + retry once
            console.print("  [yellow]Sin resultados en página 1. Scrolleando...[/yellow]")
            for _ in range(6):
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(1.5)
            batch = _extract_companies_from_page(page)
            if batch:
                captured.extend(batch)
                console.print(f"  [green]Tras scroll:[/green] +{len(batch)} empresas")
            else:
                # Diagnostic: show what links actually exist in the DOM
                diag = page.evaluate("""
                () => {
                    const allA = Array.from(document.querySelectorAll('a[href]'));
                    const companyLinks = allA.filter(a => a.href.includes('/company/'));
                    const searchLinks = allA.filter(a => a.href.includes('/search/'));
                    const sampleHrefs = allA.slice(0, 30).map(a => a.href.substring(0, 80));
                    const companyHrefs = companyLinks.slice(0, 15).map(a =>
                        ({href: a.href.substring(0, 80), text: (a.innerText||'').substring(0,40)}));
                    return {
                        total_links: allA.length,
                        company_links: companyLinks.length,
                        search_links: searchLinks.length,
                        company_hrefs: companyHrefs,
                        sample_hrefs: sampleHrefs,
                    };
                }
                """)
                console.print(f"  [yellow]DIAGNÓSTICO DOM:[/yellow]")
                console.print(f"  Total <a> tags: {diag['total_links']}")
                console.print(f"  Links /company/: {diag['company_links']}")
                console.print(f"  Links /search/ : {diag['search_links']}")
                console.print(f"  Links empresa encontrados:")
                for item in diag['company_hrefs']:
                    console.print(f"    {item['href']}  →  '{item['text']}'")
                if not diag['company_hrefs']:
                    console.print("  [red]NINGÚN link /company/ en el DOM[/red]")
                    console.print("  Primeros 10 links de la página:")
                    for h in diag['sample_hrefs'][:10]:
                        console.print(f"    {h}")

        # Paginate for more results
        page_num = 1
        while len(captured) < count and page_num < 10:
            # Try clicking "Next" button
            try:
                next_btn = page.query_selector("button[aria-label='Next']")
                if not next_btn:
                    # Try via URL pagination
                    next_url = base_search + f"&page={page_num + 1}"
                    page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(wait_seconds)
                else:
                    next_btn.click()
                    time.sleep(random.uniform(3, 5))

                batch = _extract_companies_from_page(page)
                if not batch:
                    break
                captured.extend(batch)
                console.print(f"  [green]Página {page_num + 1}:[/green] +{len(batch)} empresas (total {len(captured)})")
                page_num += 1
            except Exception as e:
                console.print(f"  [dim]Paginación detenida: {e}[/dim]")
                break

        browser.close()

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for c in captured:
        key = c.get("linkedin_url") or c.get("name", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(c)

    if not unique:
        console.print("[red]No se encontraron empresas.[/red]")
        console.print("[dim]Causas posibles:[/dim]")
        console.print("[dim]  1. Sesión expirada → corre linkedin-login de nuevo[/dim]")
        console.print("[dim]  2. LinkedIn mostró captcha → aumenta --wait o corre visible[/dim]")
        console.print("[dim]  3. Rate limit → espera unos minutos y reintenta[/dim]")

    console.print(f"  [bold green]Total empresas:[/bold green] {len(unique)}")
    return unique[:count]


def get_company_profile(
    linkedin_url: str,
    cookies: dict | None = None,
    headless: bool = False,
    wait_seconds: int = 6,
) -> dict:
    """
    Fetch full company profile from a LinkedIn company /about page.

    Args:
        linkedin_url: Full LinkedIn company URL or slug
        cookies:      LinkedIn session cookies

    Returns:
        Company dict with name, description, website, employee_count,
        headquarters, founded, specialties, followers
    """
    from playwright.sync_api import sync_playwright

    if cookies is None:
        cookies = load_linkedin_cookies()

    if not linkedin_url.startswith("http"):
        linkedin_url = f"https://www.linkedin.com/company/{linkedin_url}"

    about_url = linkedin_url.rstrip("/") + "/about/"
    profile: dict = {"linkedin_url": linkedin_url}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        context.add_cookies(_cookies_to_playwright(cookies))
        page = context.new_page()

        try:
            page.goto(about_url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

        time.sleep(wait_seconds)

        data = page.evaluate("""
        () => {
            const getText = (sel) => {
                const el = document.querySelector(sel);
                return el ? el.innerText.trim() : '';
            };
            const getAllText = (sel) => {
                return Array.from(document.querySelectorAll(sel))
                    .map(e => e.innerText.trim()).filter(Boolean);
            };

            const fullText = document.body.innerText || '';

            // Name
            const name = getText('h1') || getText('.org-top-card-summary__title');

            // Description
            const desc = getText('.org-about-us-organization-description__text') ||
                         getText('[data-test-id="about-us__description"]') ||
                         getText('.org-about-module__description') ||
                         getText('section.about-us p');

            // Website
            const webEl = document.querySelector('a[data-control-name="visit_company_website"]') ||
                          document.querySelector('.org-about-us-organization-description a[href*="http"]');
            const website = webEl ? webEl.href : '';

            // Followers
            const followerMatch = fullText.match(/([\\d,]+)\\s*follower/i);
            const followers = followerMatch ? parseInt(followerMatch[1].replace(/,/g,'')) : '';

            // Employee count
            const empMatch = fullText.match(/(\\d[\\d,]*\\s*[-–]\\s*\\d[\\d,]*|\\d[\\d,]+\\+?)\\s*employees?/i);
            const employee_count = empMatch ? empMatch[0].trim() : '';

            // Specialties
            const specEl = document.querySelector('.org-about-us-organization-description__text--specialties');
            const specialties = specEl ? specEl.innerText.split(',').map(s=>s.trim()).filter(Boolean) : [];

            // Founded / HQ from about page dl list
            const details = {};
            document.querySelectorAll('dl dt, dl dd').forEach((el, i, arr) => {
                if (el.tagName === 'DT') {
                    const key = el.innerText.trim().toLowerCase();
                    const val = arr[i+1] ? arr[i+1].innerText.trim() : '';
                    details[key] = val;
                }
            });

            return { name, description: desc, website, followers, employee_count,
                     specialties, details };
        }
        """)

        browser.close()

    if data:
        profile["name"] = data.get("name", "")
        profile["description"] = data.get("description", "")
        profile["website"] = data.get("website", "")
        profile["followers"] = data.get("followers", "")
        profile["employee_count"] = data.get("employee_count", "")
        profile["specialties"] = data.get("specialties", [])
        details = data.get("details", {})
        profile["headquarters"] = details.get("headquarters", "") or details.get("sede", "")
        profile["founded"] = details.get("founded", "") or details.get("fundada", "")
        profile["industry"] = details.get("industry", "") or details.get("sector", "")

    return {k: v for k, v in profile.items() if v or v == 0}


def bulk_enrich_companies(
    companies: list[dict],
    cookies: dict | None = None,
    headless: bool = False,
    delay: float = 3.0,
) -> list[dict]:
    """
    Enrich a list of company stubs with full profiles (website, description, etc).

    Args:
        companies: List of dicts with at least 'linkedin_url'
        delay:     Seconds between requests to avoid rate limiting

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

        console.print(f"  [{i+1}/{len(companies)}] [cyan]{c.get('name', url)}[/cyan]")
        try:
            profile = get_company_profile(url, cookies=cookies, headless=headless)
            enriched.append({**c, **profile})
        except Exception as e:
            console.print(f"    [red]Error:[/red] {e}")
            enriched.append(c)

        time.sleep(delay + random.uniform(0, 1.5))

    return enriched
