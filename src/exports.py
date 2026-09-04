"""CSV export for coding and audit."""

from __future__ import annotations

import csv
import os


FIELDS = [
    "item_id", "week", "date", "country", "party_id", "party", "camp",
    "source_type", "provenance", "outlet", "title", "source_url", "archive_url",
    "summary", "themes", "actors", "quote_index", "speaker", "original_quote",
    "translation", "cluster_id", "cluster_size", "confidence", "jda_category",
    "coder", "coded_date", "notes",
]


def rows_for(items: list[dict], cluster_sizes: dict | None = None) -> list[dict]:
    cluster_sizes = cluster_sizes or {}
    rows = []
    for item in items:
        analysis = item.get("analysis") or {}
        if not analysis.get("relevant"):
            continue
        quotes = analysis.get("quotes") or [{}]
        for index, quote in enumerate(quotes):
            code = item.get("coded") or ""
            rows.append({
                "item_id": item.get("id", ""),
                "week": item.get("week", ""),
                "date": (item.get("published") or "")[:10],
                "country": item.get("country", ""),
                "party_id": item.get("party_id", ""),
                "party": item.get("party_name", item.get("party_id", "")),
                "camp": item.get("camp", ""),
                "source_type": item.get("source_type", ""),
                "provenance": item.get("provenance", ""),
                "outlet": item.get("outlet", ""),
                "title": item.get("title", ""),
                "source_url": item.get("url", ""),
                "archive_url": item.get("archive_url", ""),
                "summary": analysis.get("summary", ""),
                "themes": "; ".join(analysis.get("topics") or []),
                "actors": "; ".join(analysis.get("actors") or []),
                "quote_index": index if quote else "",
                "speaker": quote.get("speaker", ""),
                "original_quote": quote.get("original", ""),
                "translation": quote.get("translation", ""),
                "cluster_id": item.get("cluster_id", ""),
                "cluster_size": cluster_sizes.get(item.get("cluster_id"), 1),
                "confidence": analysis.get("confidence", ""),
                "jda_category": code,
                "coder": "",
                "coded_date": "",
                "notes": "",
            })
    return rows


def write_csv(rows: list[dict], path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path
