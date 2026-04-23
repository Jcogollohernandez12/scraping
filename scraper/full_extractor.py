"""
A) Full structured extraction:
Extracts ALL content from a page organized by sections, headings,
JSON-LD schema data, forms, buttons, tables, and raw text blocks.
"""
from __future__ import annotations
import json
import re


def extract_full(page) -> dict:
    result = {}

    # ── Title & meta ──────────────────────────────────────────────────
    result["title"] = page.css("title::text").get("").strip()

    # ── JSON-LD structured data ───────────────────────────────────────
    jsonld = []
    for script in page.css('script[type="application/ld+json"]'):
        try:
            text = script.css("::text").get("").strip()
            if text:
                jsonld.append(json.loads(text))
        except Exception:
            pass
    result["structured_data"] = jsonld

    # ── Headings hierarchy ────────────────────────────────────────────
    headings = []
    for tag in ["h1", "h2", "h3", "h4"]:
        for el in page.css(tag):
            text = " ".join(t.strip() for t in el.css("::text").get_all() if t.strip())
            if text:
                headings.append({"level": tag, "text": text})
    result["headings"] = headings

    # ── Text blocks by section ────────────────────────────────────────
    sections = []
    for el in page.css("section, article, main, [class*='section'], [class*='block']"):
        heading_el = el.css("h1, h2, h3")
        heading = ""
        if heading_el:
            heading = " ".join(heading_el[0].css("::text").get_all()).strip()
        texts = [t.strip() for t in el.css("p::text, span::text, li::text").get_all() if t.strip()]
        if texts:
            sections.append({"heading": heading, "content": texts})
    result["sections"] = sections

    # ── All paragraphs ────────────────────────────────────────────────
    result["paragraphs"] = [
        t.strip() for t in page.css("p::text").get_all() if len(t.strip()) > 20
    ]

    # ── Navigation links ──────────────────────────────────────────────
    nav_links = []
    for a in page.css("nav a, header a, [class*='nav'] a, [class*='menu'] a"):
        attrib = getattr(a, "attrib", {}) or {}
        href = attrib.get("href", "")
        text = " ".join(a.css("::text").get_all()).strip()
        if href and text:
            nav_links.append({"text": text, "href": href})
    result["navigation"] = nav_links

    # ── All links ─────────────────────────────────────────────────────
    all_links = []
    for a in page.css("a"):
        attrib = getattr(a, "attrib", {}) or {}
        href = attrib.get("href", "")
        text = " ".join(a.css("::text").get_all()).strip()
        if href:
            all_links.append({"text": text, "href": href})
    result["links"] = all_links

    # ── Images ────────────────────────────────────────────────────────
    images = []
    for img in page.css("img"):
        attrib = getattr(img, "attrib", {}) or {}
        src = attrib.get("src", "") or attrib.get("data-src", "") or attrib.get("data-lazy-src", "")
        alt = attrib.get("alt", "")
        if src:
            images.append({"src": src, "alt": alt})
    result["images"] = images

    # ── Forms ─────────────────────────────────────────────────────────
    forms = []
    for form in page.css("form"):
        attrib = getattr(form, "attrib", {}) or {}
        fields = []
        for inp in form.css("input, textarea, select"):
            inp_attrib = getattr(inp, "attrib", {}) or {}
            fields.append({
                "type": inp_attrib.get("type", "text"),
                "name": inp_attrib.get("name", ""),
                "placeholder": inp_attrib.get("placeholder", ""),
            })
        forms.append({
            "action": attrib.get("action", ""),
            "method": attrib.get("method", "get"),
            "fields": fields,
        })
    result["forms"] = forms

    # ── Buttons & CTAs ────────────────────────────────────────────────
    buttons = []
    for el in page.css("button, a[class*='btn'], a[class*='button'], [class*='cta']"):
        text = " ".join(el.css("::text").get_all()).strip()
        attrib = getattr(el, "attrib", {}) or {}
        href = attrib.get("href", "")
        if text:
            buttons.append({"text": text, "href": href})
    result["buttons_cta"] = buttons

    # ── Tables ────────────────────────────────────────────────────────
    tables = []
    for table in page.css("table"):
        headers = [" ".join(th.css("::text").get_all()).strip() for th in table.css("th")]
        rows = []
        for tr in table.css("tbody tr"):
            cells = [" ".join(td.css("::text").get_all()).strip() for td in tr.css("td")]
            if cells:
                rows.append(dict(zip(headers, cells)) if headers else cells)
        if rows:
            tables.append({"headers": headers, "rows": rows})
    result["tables"] = tables

    # ── Social media links ────────────────────────────────────────────
    social_patterns = ["facebook", "twitter", "instagram", "linkedin", "youtube", "tiktok", "x.com"]
    social = []
    for a in page.css("a"):
        attrib = getattr(a, "attrib", {}) or {}
        href = attrib.get("href", "").lower()
        if any(s in href for s in social_patterns):
            text = " ".join(a.css("::text").get_all()).strip()
            social.append({"platform": next((s for s in social_patterns if s in href), ""), "href": href, "text": text})
    result["social_links"] = social

    # ── Raw full text ─────────────────────────────────────────────────
    all_text = " ".join(t.strip() for t in page.css("body *::text").get_all() if t.strip())
    result["full_text"] = re.sub(r'\s+', ' ', all_text).strip()

    return result
