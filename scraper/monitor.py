"""
D) Change monitor:
Takes a snapshot of a page and compares it with previous snapshots.
Detects added/removed text, price changes, link changes, and new sections.
Snapshots are stored in ./snapshots/ as JSON files.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table

console = Console()

SNAPSHOTS_DIR = Path("./snapshots")


def _url_slug(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "").replace(".", "_")
    path = urlparse(url).path.strip("/").replace("/", "_") or "home"
    return f"{host}__{path}"


def _snapshot_path(url: str, ts: str) -> Path:
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    return SNAPSHOTS_DIR / f"{_url_slug(url)}__{ts}.json"


def _latest_snapshot(url: str) -> dict | None:
    slug = _url_slug(url)
    files = sorted(SNAPSHOTS_DIR.glob(f"{slug}__*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text())


def _text_hash(data: dict) -> str:
    text = data.get("full_text", "") or json.dumps(data, sort_keys=True)
    return hashlib.md5(text.encode()).hexdigest()


def take_snapshot(url: str, page_data: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _snapshot_path(url, ts)
    page_data["_snapshot_ts"] = ts
    page_data["_url"] = url
    page_data["_hash"] = _text_hash(page_data)
    path.write_text(json.dumps(page_data, ensure_ascii=False, indent=2))
    console.print(f"  [green]Snapshot saved:[/green] {path.name}")
    return path


def compare_snapshots(url: str, new_data: dict) -> dict:
    old = _latest_snapshot(url)
    if not old:
        return {"status": "first_snapshot", "changes": []}

    changes = []

    # ── Hash change ───────────────────────────────────────────────────
    new_hash = _text_hash(new_data)
    if old.get("_hash") == new_hash:
        return {"status": "no_change", "changes": [], "last_snapshot": old.get("_snapshot_ts")}

    # ── Title ─────────────────────────────────────────────────────────
    if old.get("title") != new_data.get("title"):
        changes.append({"type": "title_changed", "old": old.get("title"), "new": new_data.get("title")})

    # ── Headings ──────────────────────────────────────────────────────
    old_headings = set(h["text"] for h in old.get("headings", []))
    new_headings = set(h["text"] for h in new_data.get("headings", []))
    for h in new_headings - old_headings:
        changes.append({"type": "heading_added", "text": h})
    for h in old_headings - new_headings:
        changes.append({"type": "heading_removed", "text": h})

    # ── Links ─────────────────────────────────────────────────────────
    old_hrefs = set(l["href"] for l in old.get("links", []))
    new_hrefs = set(l["href"] for l in new_data.get("links", []))
    for href in new_hrefs - old_hrefs:
        changes.append({"type": "link_added", "href": href})
    for href in old_hrefs - new_hrefs:
        changes.append({"type": "link_removed", "href": href})

    # ── Images ────────────────────────────────────────────────────────
    old_imgs = set(i["src"] for i in old.get("images", []))
    new_imgs = set(i["src"] for i in new_data.get("images", []))
    for src in new_imgs - old_imgs:
        changes.append({"type": "image_added", "src": src})
    for src in old_imgs - new_imgs:
        changes.append({"type": "image_removed", "src": src})

    # ── Prices (if business data present) ────────────────────────────
    old_prices = set(p for item in old.get("pricing", []) for p in item.get("prices_found", []))
    new_prices = set(p for item in new_data.get("pricing", []) for p in item.get("prices_found", []))
    for p in new_prices - old_prices:
        changes.append({"type": "price_added", "value": p})
    for p in old_prices - new_prices:
        changes.append({"type": "price_removed", "value": p})

    # ── Text diff (word count) ────────────────────────────────────────
    old_words = len((old.get("full_text", "") or "").split())
    new_words = len((new_data.get("full_text", "") or "").split())
    diff = new_words - old_words
    if abs(diff) > 50:
        changes.append({"type": "content_changed", "word_diff": diff,
                        "old_words": old_words, "new_words": new_words})

    return {
        "status": "changed" if changes else "minor_change",
        "last_snapshot": old.get("_snapshot_ts"),
        "changes": changes,
        "total_changes": len(changes),
    }


def list_snapshots(url: str | None = None) -> list[dict]:
    SNAPSHOTS_DIR.mkdir(exist_ok=True)
    pattern = f"{_url_slug(url)}__*.json" if url else "*.json"
    files = sorted(SNAPSHOTS_DIR.glob(pattern), reverse=True)
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            result.append({
                "file": f.name,
                "url": data.get("_url", ""),
                "timestamp": data.get("_snapshot_ts", ""),
                "hash": data.get("_hash", "")[:8],
            })
        except Exception:
            pass
    return result


def print_diff_report(diff: dict):
    if diff["status"] == "no_change":
        console.print("[green]No changes detected[/green] since last snapshot.")
        return
    if diff["status"] == "first_snapshot":
        console.print("[cyan]First snapshot taken[/cyan] — nothing to compare yet.")
        return

    table = Table(title=f"Changes detected ({diff['total_changes']})", show_lines=True)
    table.add_column("Type", style="yellow", no_wrap=True)
    table.add_column("Detail", style="white", overflow="fold")

    for change in diff["changes"]:
        ctype = change["type"]
        detail = " | ".join(f"{k}: {v}" for k, v in change.items() if k != "type")
        table.add_row(ctype, detail[:200])

    console.print(table)
