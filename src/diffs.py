"""Track sentence-level changes on configured programme pages."""

from __future__ import annotations

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from collect import HEADERS, TIMEOUT
from evidence import jaccard, shingles


def _text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "form", "aside"]):
        node.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text or "") if len(x.strip()) >= 35]


def check(conn, parties: list[dict], store, similarity_floor: float = 0.985) -> list[dict]:
    changes = []
    for party in parties:
        for url in party.get("watch_pages") or []:
            try:
                now = _text(url)
                previous = store.page_history(conn, url, limit=1)
                is_new, _ = store.save_page_version(conn, party["id"], url, now)
                if not previous or not is_new:
                    continue
                before = previous[0].get("text") or ""
                similarity = jaccard(shingles(before), shingles(now))
                if similarity >= similarity_floor:
                    continue
                old_s, new_s = set(_sentences(before)), set(_sentences(now))
                added, removed = sorted(new_s - old_s), sorted(old_s - new_s)
                changes.append({
                    "party_id": party["id"],
                    "party": party.get("short") or party.get("name") or party["id"],
                    "url": url,
                    "since": (previous[0].get("captured") or "")[:10],
                    "added_total": len(added),
                    "removed_total": len(removed),
                    "similarity": round(similarity, 3),
                    "added": added[:12],
                    "removed": removed[:12],
                })
            except Exception:
                continue
    return changes
