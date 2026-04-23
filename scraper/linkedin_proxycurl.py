"""
C) Proxycurl API integration — LinkedIn data without browser automation
Compliant, reliable, no captchas. Requires a Proxycurl API key.
Pricing: ~$0.01/credit | https://nubela.co/proxycurl/pricing
"""
from __future__ import annotations

import os
import time
import random
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()

PROXYCURL_BASE = "https://nubela.co/proxycurl/api"


# ── HTTP client ───────────────────────────────────────────────────────────────

def _get(endpoint: str, params: dict, api_key: str) -> dict | list | None:
    """Make a GET request to Proxycurl API."""
    import requests

    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{PROXYCURL_BASE}{endpoint}"

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return None
        elif resp.status_code == 429:
            console.print("  [yellow]Rate limited — waiting 60s...[/yellow]")
            time.sleep(60)
            return _get(endpoint, params, api_key)
        else:
            console.print(f"  [red]Proxycurl {resp.status_code}:[/red] {resp.text[:200]}")
            return None
    except Exception as e:
        console.print(f"  [red]Request error:[/red] {e}")
        return None


def _load_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key
    key = os.getenv("PROXYCURL_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "Proxycurl API key not found.\n"
            "Set PROXYCURL_API_KEY env var or pass api_key= parameter.\n"
            "Get a key at https://nubela.co/proxycurl"
        )
    return key


# ── Company functions ─────────────────────────────────────────────────────────

def get_company(
    linkedin_url: str,
    api_key: str | None = None,
    extra_fields: list[str] | None = None,
) -> dict | None:
    """
    Fetch full company profile from LinkedIn URL via Proxycurl.

    Args:
        linkedin_url:  LinkedIn company URL (e.g. https://linkedin.com/company/stripe)
        api_key:       Proxycurl API key (None = env var PROXYCURL_API_KEY)
        extra_fields:  Additional fields: ["funding", "exit_data", "extra"]

    Returns:
        Company dict with: name, description, website, industry,
        company_size_on_linkedin, hq, founded_year, specialities,
        follower_count, employees, funding_data (if requested)
    """
    key = _load_api_key(api_key)
    if not linkedin_url.startswith("http"):
        linkedin_url = f"https://www.linkedin.com/company/{linkedin_url}"

    params: dict = {
        "url": linkedin_url,
        "resolve_numeric_id": "true",
    }
    if extra_fields:
        for field in extra_fields:
            params[field] = "include"

    data = _get("/linkedin/company", params, key)
    if not data:
        return None

    return _normalize_company(data, linkedin_url)


def search_companies(
    keyword: str = "health tech",
    location: str = "",
    count: int = 10,
    min_employee_count: int | None = None,
    max_employee_count: int | None = None,
    api_key: str | None = None,
) -> list[dict]:
    """
    Search LinkedIn companies via Proxycurl.

    Args:
        keyword:            Search keyword e.g. "telehealth", "digital health"
        location:           Country/city name e.g. "United States", "Mexico"
        count:              Number of results (max 10 per API call, auto-paginate)
        min_employee_count: Filter by minimum employees
        max_employee_count: Filter by maximum employees
        api_key:            Proxycurl API key

    Returns:
        List of company summary dicts with linkedin_url (use get_company to enrich)
    """
    key = _load_api_key(api_key)

    params: dict = {
        "keyword_string": keyword,
        "page_size": min(count, 10),
    }
    if location:
        params["country"] = location
    if min_employee_count is not None:
        params["min_employee_count"] = min_employee_count
    if max_employee_count is not None:
        params["max_employee_count"] = max_employee_count

    results: list[dict] = []
    next_page = None

    while len(results) < count:
        if next_page:
            params["next_page"] = next_page

        data = _get("/search/company", params, key)
        if not data:
            break

        companies = data.get("results", []) if isinstance(data, dict) else data
        for c in companies:
            results.append({
                "name": c.get("name", ""),
                "linkedin_url": c.get("linkedin_profile_url", ""),
                "website": c.get("website", ""),
                "industry": c.get("industry", ""),
                "employee_count": c.get("company_size_on_linkedin", ""),
                "location": c.get("headquarter", {}).get("city", "") if isinstance(c.get("headquarter"), dict) else "",
                "source": "proxycurl_search",
            })

        next_page = data.get("next_page") if isinstance(data, dict) else None
        if not next_page or len(results) >= count:
            break

        time.sleep(random.uniform(1, 2))

    console.print(f"  [bold green]Companies (Proxycurl):[/bold green] {len(results)}")
    return results[:count]


def _normalize_company(data: dict, linkedin_url: str) -> dict:
    """Normalize Proxycurl company response to standard format."""
    hq = data.get("hq") or {}
    city = hq.get("city", "") if isinstance(hq, dict) else ""
    country = hq.get("country", "") if isinstance(hq, dict) else ""

    employees = data.get("similar_companies") or []
    key_employees = []
    for emp in (data.get("employees") or [])[:10]:
        if isinstance(emp, dict):
            key_employees.append({
                "name": emp.get("first_name", "") + " " + emp.get("last_name", ""),
                "title": emp.get("title", ""),
                "linkedin_url": emp.get("profile_url", ""),
            })

    funding = None
    if data.get("funding_data"):
        funding = {
            "total_raised": data.get("total_funding_amount"),
            "rounds": [
                {
                    "type": r.get("funding_type", ""),
                    "amount": r.get("money_raised", ""),
                    "date": r.get("announced_date", {}).get("year", ""),
                    "investors": [inv.get("name", "") for inv in r.get("lead_investors", [])],
                }
                for r in (data.get("funding_data") or [])
            ],
        }

    return {
        "name": data.get("name", ""),
        "linkedin_url": linkedin_url,
        "website": data.get("website", ""),
        "description": data.get("description", ""),
        "industry": data.get("industries", [data.get("industry", "")])[0] if data.get("industries") else data.get("industry", ""),
        "industries": data.get("industries", []),
        "specialties": data.get("specialities", []),
        "employee_count": data.get("company_size_on_linkedin", ""),
        "headquarters": ", ".join(filter(None, [city, country])),
        "founded": data.get("founded_year", ""),
        "company_type": data.get("type", ""),
        "follower_count": data.get("follower_count", ""),
        "linkedin_id": data.get("linkedin_id", ""),
        "tagline": data.get("tagline", ""),
        "key_employees": key_employees,
        "funding": funding,
        "source": "proxycurl_profile",
    }


# ── People functions ──────────────────────────────────────────────────────────

def get_person(
    linkedin_url: str,
    api_key: str | None = None,
    include_skills: bool = True,
    include_certifications: bool = False,
) -> dict | None:
    """
    Fetch full LinkedIn profile via Proxycurl.

    Args:
        linkedin_url:           LinkedIn profile URL or username
        api_key:                Proxycurl API key
        include_skills:         Include skills list
        include_certifications: Include certifications

    Returns:
        Profile dict with: name, headline, summary, location, connections,
        experience (list), education (list), skills (list), email (if available)
    """
    key = _load_api_key(api_key)

    if not linkedin_url.startswith("http"):
        linkedin_url = f"https://www.linkedin.com/in/{linkedin_url}"

    params: dict = {
        "url": linkedin_url,
        "use_cache": "if-present",
        "fallback_to_cache": "on-error",
    }
    if include_skills:
        params["skills"] = "include"
    if include_certifications:
        params["certifications"] = "include"

    data = _get("/v2/linkedin", params, key)
    if not data:
        return None

    return _normalize_person(data, linkedin_url)


def search_people(
    keyword: str = "health tech",
    title: str = "",
    company: str = "",
    location: str = "",
    count: int = 10,
    api_key: str | None = None,
) -> list[dict]:
    """
    Search LinkedIn profiles via Proxycurl.

    Args:
        keyword:    Search keyword
        title:      Job title filter e.g. "CTO", "Founder"
        company:    Company name filter
        location:   Location filter e.g. "United States", "Mexico City"
        count:      Number of results
        api_key:    Proxycurl API key

    Returns:
        List of profile summary dicts (use get_person to enrich)
    """
    key = _load_api_key(api_key)

    params: dict = {
        "keyword_string": keyword,
        "page_size": min(count, 10),
    }
    if title:
        params["job_title"] = title
    if company:
        params["current_company_name"] = company
    if location:
        params["geo_urn"] = location

    results: list[dict] = []
    next_page = None

    while len(results) < count:
        if next_page:
            params["next_page"] = next_page

        data = _get("/search/person", params, key)
        if not data:
            break

        profiles = data.get("results", []) if isinstance(data, dict) else data
        for p in profiles:
            results.append({
                "name": (p.get("first_name", "") + " " + p.get("last_name", "")).strip(),
                "linkedin_url": p.get("linkedin_profile_url", ""),
                "headline": p.get("headline", ""),
                "location": p.get("location", ""),
                "source": "proxycurl_search",
            })

        next_page = data.get("next_page") if isinstance(data, dict) else None
        if not next_page or len(results) >= count:
            break

        time.sleep(random.uniform(1, 2))

    console.print(f"  [bold green]Profiles (Proxycurl):[/bold green] {len(results)}")
    return results[:count]


def _normalize_person(data: dict, linkedin_url: str) -> dict:
    """Normalize Proxycurl person response to standard format."""
    experience: list[dict] = []
    for exp in (data.get("experiences") or []):
        if not isinstance(exp, dict):
            continue
        start = exp.get("starts_at") or {}
        end = exp.get("ends_at") or {}
        experience.append({
            "title": exp.get("title", ""),
            "company": exp.get("company", ""),
            "location": exp.get("location", ""),
            "start": f"{start.get('year', '')}-{start.get('month', '')}".strip("-"),
            "end": f"{end.get('year', '')}-{end.get('month', '')}".strip("-") if end else "Present",
            "description": (exp.get("description") or "")[:300],
        })

    education: list[dict] = []
    for edu in (data.get("education") or []):
        if not isinstance(edu, dict):
            continue
        education.append({
            "school": edu.get("school", ""),
            "degree": edu.get("degree_name", ""),
            "field": edu.get("field_of_study", ""),
            "end_year": (edu.get("ends_at") or {}).get("year", ""),
        })

    current = experience[0] if experience else {}

    return {
        "name": f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
        "first_name": data.get("first_name", ""),
        "last_name": data.get("last_name", ""),
        "linkedin_url": linkedin_url,
        "headline": data.get("headline", ""),
        "summary": data.get("summary", ""),
        "location": data.get("city", "") or data.get("country_full_name", ""),
        "country": data.get("country_full_name", ""),
        "connections": data.get("connections", ""),
        "followers": data.get("follower_count", ""),
        "current_title": current.get("title", ""),
        "current_company": current.get("company", ""),
        "email": data.get("personal_emails", [None])[0] if data.get("personal_emails") else "",
        "phone": data.get("personal_numbers", [None])[0] if data.get("personal_numbers") else "",
        "skills": [s.get("name", "") if isinstance(s, dict) else str(s) for s in (data.get("skills") or [])],
        "languages": data.get("languages", []),
        "experience": experience,
        "education": education,
        "profile_pic": data.get("profile_pic_url", ""),
        "source": "proxycurl_profile",
    }


# ── Bulk operations ───────────────────────────────────────────────────────────

def bulk_enrich_companies(
    companies: list[dict],
    api_key: str | None = None,
    delay: float = 1.5,
    extra_fields: list[str] | None = None,
) -> list[dict]:
    """
    Enrich a list of company stubs with full Proxycurl data.
    Typically used after search_companies() to get full profiles.

    Args:
        companies:    List of dicts with 'linkedin_url'
        delay:        Seconds between API calls
        extra_fields: e.g. ["funding"] to include funding data

    Returns:
        Enriched company list
    """
    key = _load_api_key(api_key)
    enriched: list[dict] = []

    for i, c in enumerate(companies):
        url = c.get("linkedin_url", "")
        if not url:
            enriched.append(c)
            continue

        console.print(f"  [{i+1}/{len(companies)}] [cyan]{c.get('name', url)}[/cyan]")
        full = get_company(url, api_key=key, extra_fields=extra_fields)
        if full:
            enriched.append({**c, **full})
        else:
            enriched.append(c)

        time.sleep(delay + random.uniform(0, 0.5))

    return enriched


def bulk_enrich_people(
    profiles: list[dict],
    api_key: str | None = None,
    delay: float = 1.5,
) -> list[dict]:
    """
    Enrich a list of profile stubs with full Proxycurl data.
    Adds contact info, full experience, skills, etc.

    Args:
        profiles: List of dicts with 'linkedin_url'
        delay:    Seconds between API calls

    Returns:
        Enriched profile list sorted by seniority
    """
    key = _load_api_key(api_key)
    enriched: list[dict] = []

    for i, p in enumerate(profiles):
        url = p.get("linkedin_url", "")
        if not url:
            enriched.append(p)
            continue

        console.print(f"  [{i+1}/{len(profiles)}] [cyan]{p.get('name', url)}[/cyan]")
        full = get_person(url, api_key=key)
        if full:
            enriched.append({**p, **full})
        else:
            enriched.append(p)

        time.sleep(delay + random.uniform(0, 0.5))

    return enriched


def company_employees(
    linkedin_url: str,
    count: int = 20,
    role_keyword: str = "",
    api_key: str | None = None,
) -> list[dict]:
    """
    Get employees of a specific company, optionally filtered by role.
    Useful for finding decision-makers within target health tech companies.

    Args:
        linkedin_url:  Company LinkedIn URL
        count:         Max number of employees to return
        role_keyword:  Filter by role e.g. "engineer", "product", "clinical"
        api_key:       Proxycurl API key

    Returns:
        List of employee profile stubs
    """
    key = _load_api_key(api_key)

    if not linkedin_url.startswith("http"):
        linkedin_url = f"https://www.linkedin.com/company/{linkedin_url}"

    params: dict = {
        "url": linkedin_url,
        "page_size": min(count, 10),
    }
    if role_keyword:
        params["keyword_string"] = role_keyword

    results: list[dict] = []
    next_page = None

    while len(results) < count:
        if next_page:
            params["next_page"] = next_page

        data = _get("/linkedin/company/employees/", params, key)
        if not data:
            break

        employees = data.get("results", []) if isinstance(data, dict) else data
        for emp in employees:
            if not isinstance(emp, dict):
                continue
            results.append({
                "name": emp.get("name", ""),
                "title": emp.get("title", ""),
                "linkedin_url": emp.get("url", ""),
                "source": "proxycurl_employees",
            })

        next_page = data.get("next_page") if isinstance(data, dict) else None
        if not next_page or len(results) >= count:
            break

        time.sleep(random.uniform(1, 2))

    return results[:count]


# ── Reporting helpers ─────────────────────────────────────────────────────────

def print_companies_table(companies: list[dict], max_rows: int = 20):
    """Print a rich table of company results."""
    table = Table(title=f"Health Tech Companies ({len(companies)} total)", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Company", style="cyan")
    table.add_column("Industry", style="white", overflow="fold")
    table.add_column("Size", justify="right")
    table.add_column("HQ")
    table.add_column("Website", style="dim", overflow="fold")

    for i, c in enumerate(companies[:max_rows]):
        table.add_row(
            str(i + 1),
            c.get("name", "")[:40],
            (c.get("industry") or c.get("industry_size", ""))[:35],
            str(c.get("employee_count", c.get("company_size_on_linkedin", ""))),
            (c.get("headquarters") or c.get("location", ""))[:25],
            (c.get("website", ""))[:35],
        )

    console.print(table)


def print_people_table(profiles: list[dict], max_rows: int = 20):
    """Print a rich table of profile results."""
    table = Table(title=f"Health Tech Professionals ({len(profiles)} total)", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="cyan")
    table.add_column("Title / Headline", overflow="fold")
    table.add_column("Company")
    table.add_column("Location")
    table.add_column("Priority", justify="center", style="green")

    for i, p in enumerate(profiles[:max_rows]):
        headline = p.get("headline") or p.get("current_title", "")
        company = p.get("current_company", "")
        priority = str(p.get("outreach_priority", ""))
        table.add_row(
            str(i + 1),
            p.get("name", "")[:30],
            headline[:45],
            company[:25],
            (p.get("location") or p.get("country", ""))[:20],
            priority,
        )

    console.print(table)
