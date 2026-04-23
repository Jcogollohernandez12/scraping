"""
C) Business data extractor:
Uses heuristics + regex to find structured business information:
prices, services, team members, testimonials, contact info, FAQs,
opening hours, locations, and plans/packages.
"""
from __future__ import annotations

import re


# ── Regex patterns ────────────────────────────────────────────────────────────
PRICE_RE = re.compile(r'[\$€£¥₹]\s?\d+[\d,\.]*|\d+[\d,\.]*\s?(?:USD|EUR|MXN|COP|usd|eur)', re.I)
EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE = re.compile(r'(\+?\d[\d\s\-\.\(\)]{7,}\d)')
HOURS_RE = re.compile(r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[\w\s,\-:]+\d{1,2}:\d{2}', re.I)

TEAM_KEYWORDS   = ["team", "staff", "doctor", "physician", "therapist", "coach",
                   "specialist", "expert", "founder", "ceo", "cto", "director"]
SERVICE_KEYWORDS = ["service", "treatment", "therapy", "program", "plan", "package",
                    "feature", "solution", "offering", "product"]
TESTIMONIAL_KEYWORDS = ["testimonial", "review", "quote", "patient", "client",
                         "customer", "said", "feedback", "opinion"]
FAQ_KEYWORDS    = ["faq", "question", "answer", "frequently", "how to", "what is",
                   "how does", "why", "when"]
PRICE_KEYWORDS  = ["price", "pricing", "plan", "cost", "fee", "rate", "subscription",
                   "per month", "per year", "annually"]


def _texts(el) -> str:
    return " ".join(t.strip() for t in el.css("*::text").get_all() if t.strip())


def _has_keyword(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(k in low for k in keywords)


def extract_business(page) -> dict:
    result = {}

    # ── Contact info ──────────────────────────────────────────────────
    full_text = " ".join(page.css("body *::text").get_all())
    result["contact"] = {
        "emails": list(set(EMAIL_RE.findall(full_text))),
        "phones": list(set(PHONE_RE.findall(full_text))),
        "hours":  list(set(HOURS_RE.findall(full_text))),
    }

    # ── Prices ────────────────────────────────────────────────────────
    prices = []
    for el in page.css("[class*='price'], [class*='plan'], [class*='pricing'], [id*='price'], [id*='plan']"):
        text = _texts(el)
        if text:
            found = PRICE_RE.findall(text)
            label_els = el.css("h1, h2, h3, h4, [class*='title'], [class*='name']")
            label = _texts(label_els[0]) if label_els else ""
            if found or _has_keyword(text, PRICE_KEYWORDS):
                prices.append({
                    "label": label[:100],
                    "prices_found": found,
                    "text": text[:300],
                })
    if not prices:
        for el in page.css("*"):
            attrib = getattr(el, "attrib", {}) or {}
            class_id = (attrib.get("class", "") + attrib.get("id", "")).lower()
            if _has_keyword(class_id, PRICE_KEYWORDS):
                text = _texts(el)
                found = PRICE_RE.findall(text)
                if found:
                    prices.append({"label": class_id[:50], "prices_found": found, "text": text[:200]})
    result["pricing"] = prices

    # ── Services / offerings ──────────────────────────────────────────
    services = []
    for el in page.css("[class*='service'], [class*='feature'], [class*='product'], [class*='offering'], [class*='treatment'], [class*='program']"):
        text = _texts(el)
        if len(text) > 20:
            heading_els = el.css("h1, h2, h3, h4")
            heading = _texts(heading_els[0]) if heading_els else ""
            desc_els = el.css("p")
            desc = _texts(desc_els[0]) if desc_els else ""
            services.append({"name": heading[:100], "description": desc[:300]})
    result["services"] = _dedupe(services, "name")

    # ── Team members ──────────────────────────────────────────────────
    team = []
    for el in page.css("[class*='team'], [class*='staff'], [class*='member'], [class*='doctor'], [class*='therapist'], [class*='coach']"):
        text = _texts(el)
        if len(text) < 10:
            continue
        name_els = el.css("h1, h2, h3, h4, [class*='name'], strong")
        name = _texts(name_els[0]) if name_els else ""
        role_els = el.css("[class*='role'], [class*='title'], [class*='position'], span")
        role = _texts(role_els[0]) if role_els else ""
        img_els = el.css("img")
        img_attrib = getattr(img_els[0], "attrib", {}) if img_els else {}
        photo = img_attrib.get("src", "") if img_attrib else ""
        bio_els = el.css("p")
        bio = _texts(bio_els[0]) if bio_els else ""
        if name or role:
            team.append({"name": name[:80], "role": role[:80], "bio": bio[:200], "photo": photo})
    result["team"] = _dedupe(team, "name")

    # ── Testimonials / reviews ────────────────────────────────────────
    testimonials = []
    for el in page.css("[class*='testimonial'], [class*='review'], [class*='quote'], [class*='feedback']"):
        text = _texts(el)
        if len(text) < 20:
            continue
        author_els = el.css("[class*='author'], [class*='name'], cite, strong")
        author = _texts(author_els[0]) if author_els else ""
        testimonials.append({"text": text[:400], "author": author[:80]})
    result["testimonials"] = testimonials

    # ── FAQs ──────────────────────────────────────────────────────────
    faqs = []
    for el in page.css("[class*='faq'], [class*='accordion'], details"):
        question_els = el.css("summary, [class*='question'], h3, h4, dt, strong")
        answer_els   = el.css("[class*='answer'], p, dd")
        q = _texts(question_els[0]) if question_els else ""
        a = _texts(answer_els[0])   if answer_els   else ""
        if q:
            faqs.append({"question": q[:200], "answer": a[:400]})
    result["faqs"] = faqs

    # ── Locations / addresses ─────────────────────────────────────────
    locations = []
    for el in page.css("[class*='location'], [class*='address'], [class*='office'], address"):
        text = _texts(el)
        if len(text) > 10:
            locations.append(text[:200])
    result["locations"] = list(set(locations))

    # ── Key stats / numbers ───────────────────────────────────────────
    stats = []
    for el in page.css("[class*='stat'], [class*='count'], [class*='metric'], [class*='number'], [class*='achievement']"):
        number_els = el.css("[class*='number'], [class*='count'], strong, span")
        label_els  = el.css("[class*='label'], [class*='title'], p, span")
        num   = _texts(number_els[0]) if number_els else ""
        label = _texts(label_els[0])  if label_els  else ""
        if num:
            stats.append({"number": num[:50], "label": label[:100]})
    result["stats"] = stats

    return result


def _dedupe(items: list[dict], key: str) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        val = item.get(key, "")
        if val and val not in seen:
            seen.add(val)
            out.append(item)
        elif not val:
            out.append(item)
    return out
