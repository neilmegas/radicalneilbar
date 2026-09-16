"""Build the three short, linked panels at the top of every weekly issue.

The panels are deliberately deterministic. They do not depend on an AI call,
so a fast scheduled run still produces highlights, world context, and a
reading list. Party activity comes from the research database; the two wider
panels come from configured feeds and dated Google News searches.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import requests
import yaml

from collect import HEADERS, TIMEOUT, _as_datetime, _clean_html, _date, _within


DEFAULT_CONFIG = {
    "feeds": [],
    "highlights_queries": [
        "European radical parties politics",
        "Israel political parties Knesset",
    ],
    "world_queries": [
        "global politics elections diplomacy",
        "international politics governments conflict",
    ],
    "queries": [
        "European radical right parties analysis",
        "European radical left parties analysis",
    ],
    "limit_per_panel": 6,
    "minimum_per_panel": 2,
}


def load_reading_config(path: str = "config/reading.yaml") -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return {**DEFAULT_CONFIG, **(yaml.safe_load(fh) or {})}
    except FileNotFoundError:
        return dict(DEFAULT_CONFIG)


def _trim(text: str, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", text or "").strip(" -·|\n\t")
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip(" ,;:") + "…"


def _description(title: str, text: str, source: str, kind: str) -> str:
    """Return a useful one-line description even when an RSS feed has no dek."""
    title_clean = re.sub(r"\s+-\s+[^-]{2,80}$", "", title or "").strip()
    cleaned = _clean_html(text or "")
    for noise in (title or "", title_clean, source or ""):
        if noise:
            cleaned = re.sub(re.escape(noise), " ", cleaned, flags=re.I)
    cleaned = _trim(cleaned)
    if len(cleaned) >= 45:
        return cleaned
    subject = _trim(title_clean or title or "the linked development", 190)
    prefix = "Analysis" if kind == "analysis" else "Reporting"
    return f"{prefix} from {source or 'the linked publication'} on {subject}."


def _row(entry, source: str, kind: str, fallback_url: str = "") -> dict:
    title = _clean_html(entry.get("title") or "Untitled")
    text = entry.get("summary") or entry.get("description") or ""
    return {
        "title": title,
        "url": entry.get("link") or fallback_url,
        "source": source or "Publication",
        "kind": kind,
        "published": _date(entry.get("published") or entry.get("updated")),
        "description": _description(title, text, source, kind),
    }


def fetch_reading_feeds(config: dict, since, until=None) -> list[dict]:
    urls = list(config.get("feeds") or [])[:12]

    def fetch(url):
        rows = []
        try:
            response = requests.get(url, headers=HEADERS, timeout=min(TIMEOUT, 8))
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            source = feed.feed.get("title") or "Feed"
            for entry in feed.entries[:40]:
                row = _row(entry, source, "analysis", url)
                if _within(row["published"], since, until):
                    rows.append(row)
        except Exception:
            pass
        return rows

    out = []
    with ThreadPoolExecutor(max_workers=min(6, len(urls) or 1)) as pool:
        for rows in pool.map(fetch, urls):
            out.extend(rows)
    return out


def search_news(queries: list[str], since, until=None, kind: str = "reporting",
                per_query: int = 16) -> list[dict]:
    """Dated news search used when direct sites or specialist feeds are thin."""
    since = _as_datetime(since) or datetime.now(timezone.utc) - timedelta(days=7)
    until = _as_datetime(until) if until else datetime.now(timezone.utc) + timedelta(days=1)
    # Never ask a feed for future material when building the current partial week.
    until = min(until, datetime.now(timezone.utc) + timedelta(days=1))
    selected_queries = list(queries or [])[:8]

    def fetch(query):
        rows = []
        after = (since.date() - timedelta(days=1)).isoformat()
        before = until.date().isoformat()
        search = f"{query} after:{after} before:{before}"
        url = (
            "https://news.google.com/rss/search?q=" + quote_plus(search)
            + "&hl=en&gl=GB&ceid=GB:en"
        )
        try:
            response = requests.get(url, headers=HEADERS, timeout=min(TIMEOUT, 8))
            response.raise_for_status()
            for entry in feedparser.parse(response.content).entries[:per_query]:
                title = _clean_html(entry.get("title") or "")
                if not title:
                    continue
                published = _date(entry.get("published") or entry.get("updated"))
                if not _within(published, since, until):
                    continue
                src = entry.get("source", {})
                source = (src.get("title") if isinstance(src, dict) else "") or "Google News"
                row = _row(entry, source, kind)
                row["published"] = published
                rows.append(row)
        except Exception:
            pass
        return rows

    out, seen = [], set()
    with ThreadPoolExecutor(max_workers=min(6, len(selected_queries) or 1)) as pool:
        for rows in pool.map(fetch, selected_queries):
            for row in rows:
                key = (row.get("title") or "").casefold()
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(row)
    return out


def search_reading(config: dict, days: int = 7, since=None, until=None) -> list[dict]:
    since = _as_datetime(since) or datetime.now(timezone.utc) - timedelta(days=days)
    return search_news(config.get("queries") or [], since, until, "analysis")


def curate(candidates: list[dict], limit: int = 6, minimum: int = 2) -> list[dict]:
    """Deduplicate, favour source diversity, and keep a short linked list."""
    unique = {}
    for raw in candidates:
        row = dict(raw)
        key = (row.get("url") or row.get("title") or "").casefold()
        if not key or key in unique:
            continue
        row["description"] = row.get("description") or row.get("why") or _description(
            row.get("title", ""), row.get("text", ""), row.get("source", ""),
            row.get("kind", "reporting"),
        )
        row["why"] = row["description"]  # backward-compatible with older pages
        unique[key] = row
    trusted = (
        "reuters", "associated press", "ap news", "bbc", "financial times",
        "the guardian", "le monde", "politico", "france 24", "al jazeera",
        "deutsche welle", "dw.com", "pbs", "npr", "the times of israel",
        "haaretz", "euronews", "european parliament", "osce", "united nations",
    )

    def quality(row):
        source = (row.get("source") or "").casefold()
        return 1 if any(name in source for name in trusted) else 0

    ordered = sorted(unique.values(), key=lambda x: x.get("published") or "", reverse=True)
    ordered.sort(key=quality, reverse=True)
    chosen, used_sources = [], set()
    for row in ordered:
        source = (row.get("source") or "").casefold()
        if source and source in used_sources:
            continue
        chosen.append(row)
        used_sources.add(source)
        if len(chosen) >= limit:
            return chosen
    for row in ordered:
        if row not in chosen:
            chosen.append(row)
        if len(chosen) >= limit:
            break
    # ``minimum`` is an assertion target, not permission to invent a story.
    # The caller records an explicit coverage warning if searches return fewer.
    return chosen[:max(minimum, limit)]


def highlights(items: list[dict], context: list[dict] | None = None,
               limit: int = 6, minimum: int = 2) -> list[dict]:
    """Select the clearest direct record of what monitored parties did."""
    weights = {"unusual": 3, "notable": 2, "routine": 1}
    importance_terms = {
        "election", "vote", "campaign", "coalition", "resign", "launch", "policy",
        "bill", "court", "government", "minister", "parliament", "ban", "protest",
        "donation", "funding", "candidate", "leader", "agreement", "pact", "strike",
    }
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]

    def importance(item):
        analysis = item.get("analysis") or {}
        text = f"{item.get('title', '')} {analysis.get('summary', '')}".casefold()
        keywords = sum(1 for term in importance_terms if term in text)
        significance = weights.get(
            (item.get("interpretation") or {}).get("significance", "routine"), 1)
        direct = 2 if (item.get("provenance_rank") or 9) <= 3 else 0
        return significance * 20 + min(keywords, 4) * 5 + direct

    relevant.sort(key=lambda i: i.get("published") or "", reverse=True)
    relevant.sort(key=importance, reverse=True)
    out, seen = [], set()
    used_parties = set()

    def add(item):
        analysis = item.get("analysis") or {}
        key = str(item.get("cluster_id") or item.get("title") or item.get("id") or "").casefold()
        if key in seen:
            return False
        seen.add(key)
        summary = analysis.get("summary") or item.get("title") or "Party activity"
        out.append({
            "item_id": item["id"],
            "title": item.get("title") or summary,
            "url": item.get("url") or "",
            "source": item.get("party_name") or item.get("party_id") or "Party source",
            "published": item.get("published") or "",
            "description": _trim(summary),
            "line": _trim(summary),  # backward-compatible field
            "kind": "party activity",
        })
        used_parties.add(item.get("party_id"))
        return True

    # First pass: one consequential item per party. This prevents a prolific
    # site from occupying the entire weekly summary.
    for item in relevant:
        if item.get("party_id") in used_parties:
            continue
        add(item)
        if len(out) >= limit:
            break
    if len(out) < limit:
        for item in relevant:
            add(item)
            if len(out) >= limit:
                break
    if len(out) < minimum:
        for row in curate(context or [], limit=limit, minimum=minimum):
            key = (row.get("url") or row.get("title") or "").casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
            if len(out) >= minimum:
                break
    return out[:limit]


def build_panels(config: dict, items: list[dict], since, until) -> tuple[list, list, list]:
    """Return highlights, world politics, and worth-reading rows."""
    limit = max(2, int(config.get("limit_per_panel") or 6))
    minimum = max(2, int(config.get("minimum_per_panel") or 2))

    def retry(fn):
        rows = []
        for _ in range(2):
            rows = fn()
            if rows:
                break
        return rows

    # The four source groups are independent. Fetching them together keeps a
    # slow feed from serially delaying the scheduled workflow.
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_europe = pool.submit(
            retry, lambda: search_news(config.get("highlights_queries") or [], since, until))
        future_world = pool.submit(
            retry, lambda: search_news(config.get("world_queries") or [], since, until))
        future_feeds = pool.submit(
            retry, lambda: fetch_reading_feeds(config, since, until))
        future_reading = pool.submit(
            retry, lambda: search_reading(config, since=since, until=until))
        europe_israel = future_europe.result()
        world_candidates = future_world.result()
        reading_candidates = future_feeds.result() + future_reading.result()

    world = curate(world_candidates, limit=limit, minimum=minimum)
    reading = curate(reading_candidates, limit=limit, minimum=minimum)
    highlight_rows = highlights(items, europe_israel, limit=limit, minimum=minimum)
    return highlight_rows, world, reading


def world_briefing(week_range: str, items: list[dict]) -> str:
    """Legacy text fallback retained for old callers and old databases."""
    n = sum(1 for i in items if (i.get("analysis") or {}).get("relevant"))
    return f"{n} substantive monitored-party item(s) were retained for {week_range}."
