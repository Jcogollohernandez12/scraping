"""
Exporter: saves extracted data to JSON, JSONL, or CSV.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rich.console import Console

console = Console()


def _slug(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "").replace(".", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{host}_{ts}"


class Exporter:
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: Any, url: str, fmt: str = "json") -> list[Path]:
        """Save data in specified format(s). fmt can be 'json','jsonl','csv','all'."""
        slug = _slug(url)
        saved = []

        formats = ["json", "jsonl", "csv"] if fmt == "all" else [fmt]

        for f in formats:
            path = self.output_dir / f"{slug}.{f}"
            if f == "json":
                self._to_json(data, path)
            elif f == "jsonl":
                self._to_jsonl(data, path)
            elif f == "csv":
                self._to_csv(data, path)
            saved.append(path)
            console.print(f"  [green]Saved[/green] → [link={path}]{path}[/link]")

        return saved

    def _to_json(self, data: Any, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _to_jsonl(self, data: Any, path: Path):
        records = data if isinstance(data, list) else [data]
        with open(path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _to_csv(self, data: Any, path: Path):
        records = data if isinstance(data, list) else [data]
        if not records:
            return
        flat = []
        for r in records:
            flat.append({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
        keys = list(flat[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(flat)
