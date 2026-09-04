"""World briefing, highlights, and secondary-reading curation."""

from __future__ import annotations

import json
import os
from urllib.parse import quote_plus

import feedparser
import requests
import yaml

from analyze import MODEL, _call, _response_text
from collect import HEADERS, TIMEOUT, _clean_html, _date


def load_reading_config(path: str = "config/reading.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {"feeds": [], "queries": [], "limit": 30}


def fetch_reading_feeds(config: dict, since) -> list[dict]:
    out = []
    for url in (config.get("feeds") or [])[:20]:
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:30]:
                out.append({
                    "title": entry.get("title") or "Untitled",
                    "url": entry.get("link") or url,
                    "source": feed.feed.get("title") or "Feed",
                    "kind": "analysis",
                    "published": _date(entry.get("published") or entry.get("updated")),
                    "text": _clean_html(entry.get("summary") or ""),
                })
        except Exception:
            continue
    return out


def search_reading(config: dict, days: int = 7) -> list[dict]:
    out, seen = [], set()
    for query in (config.get("queries") or [])[:10]:
        url = (
            "https://news.google.com/rss/search?q="
            + quote_plus(f"{query} when:{max(1, int(days))}d")
            + "&hl=en&gl=US&ceid=US:en"
        )
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            for entry in feedparser.parse(response.content).entries[:20]:
                title = entry.get("title") or ""
                if not title or title.casefold() in seen:
                    continue
                seen.add(title.casefold())
                src = entry.get("source", {})
                out.append({
                    "title": title,
                    "url": entry.get("link") or "",
                    "source": src.get("title", "Google News") if isinstance(src, dict)
                              else "Google News",
                    "kind": "reporting",
                    "published": _date(entry.get("published") or entry.get("updated")),
                    "text": _clean_html(entry.get("summary") or ""),
                })
        except Exception:
            continue
    return out


def curate(candidates: list[dict], limit: int = 30) -> list[dict]:
    """Deduplicate and retain a bounded list. The model adds only a short rationale."""
    unique = {}
    for row in candidates:
        key = (row.get("url") or row.get("title") or "").casefold()
        if key and key not in unique:
            unique[key] = row
    rows = sorted(unique.values(), key=lambda x: x.get("published") or "", reverse=True)[:limit]
    for row in rows:
        row.setdefault("why", "Potentially relevant secondary reading; verify before citing.")
    return rows


def highlights(items: list[dict], limit: int = 12) -> list[dict]:
    weights = {"unusual": 3, "notable": 2, "routine": 1}
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    relevant.sort(key=lambda i: (
        -weights.get((i.get("interpretation") or {}).get("significance", "routine"), 1),
        i.get("provenance_rank") or 9,
        i.get("published") or "",
    ))
    out = []
    for item in relevant[:limit]:
        analysis = item.get("analysis") or {}
        topics = analysis.get("topics") or []
        out.append({
            "item_id": item["id"],
            "line": analysis.get("summary") or item.get("title") or "Item",
            "tag": ", ".join(topics).replace("_", " ") or item.get("source_type", "item"),
        })
    return out


def world_briefing(week_range: str, items: list[dict]) -> str:
    summaries = "\n".join(
        f"- {i.get('country')} / {i.get('party_name', i.get('party_id'))}: "
        f"{(i.get('analysis') or {}).get('summary','')}"
        for i in items if (i.get("analysis") or {}).get("relevant")
    )[:18000]
    if os.environ.get("ANTHROPIC_API_KEY") and summaries:
        try:
            return _response_text(_call({
                "model": MODEL,
                "max_tokens": 650,
                "temperature": 0,
                "system": (
                    "Write a neutral 150-250 word transnational briefing that connects only "
                    "the supplied monitored-party items. Do not invent external events or make "
                    "evaluative classifications. State when the record is too thin."
                ),
                "messages": [{"role": "user", "content":
                              f"Date range: {week_range}\n\nITEMS:\n{summaries}"}],
            })).strip()
        except Exception:
            pass
    n = sum(1 for i in items if (i.get("analysis") or {}).get("relevant"))
    return (
        f"The archive retained {n} substantive monitored-party item(s) for {week_range}. "
        "This fallback briefing was generated without model assistance; use the country "
        "sections and original sources for interpretation."
    )
