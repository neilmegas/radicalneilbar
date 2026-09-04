"""Evidence classes, similarity helpers, and duplicate clustering."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse


PROVENANCE = {
    "parliamentary_record": (
        "parliamentary record", 1,
        "An official parliamentary transcript, question, vote, or proceeding.",
    ),
    "party_document": (
        "party document", 2,
        "Material published by the party on an official party-controlled site.",
    ),
    "leader_direct": (
        "leader direct", 3,
        "A statement published directly by a named party figure.",
    ),
    "press_reported_speech": (
        "press reporting speech", 4,
        "Reporting that contains words attributed directly to a party or figure.",
    ),
    "press_characterisation": (
        "press characterisation", 5,
        "A news outlet characterises a position without a captured verbatim statement.",
    ),
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", (text or "").casefold(), flags=re.UNICODE)


def shingles(text: str, n: int = 5) -> set[str]:
    """Return word shingles. Short text falls back to its complete token string."""
    words = _tokens(text)
    if not words:
        return set()
    if len(words) < n:
        return {" ".join(words)}
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def classify(item: dict, analysis: dict | None = None) -> str:
    """Assign an evidence class without turning it into a truth score."""
    kind = (item.get("source_type") or "").casefold()
    if kind in {"parliament", "hansard", "parliamentary_record"}:
        return "parliamentary_record"
    if kind in {"party_site", "site_feed", "site_scrape", "telegram"}:
        return "party_document"
    if kind in {"youtube", "leader", "leader_direct"}:
        return "leader_direct"
    if (analysis or {}).get("quotes"):
        return "press_reported_speech"
    return "press_characterisation"


def rank(provenance: str) -> int:
    return int(PROVENANCE.get(provenance, ("unknown", 9, ""))[1])


def _fingerprint(item: dict) -> set[str]:
    analysis = item.get("analysis") or {}
    text = " ".join([
        item.get("title") or "",
        analysis.get("summary") or "",
        item.get("body") or "",
    ])[:12000]
    return shingles(text, 5)


def cluster(items: list[dict], threshold: float = 0.62):
    """Greedy near-duplicate clustering.

    Returns ``(assignment, clusters)`` where assignment maps item ids to a
    stable integer and clusters is a list of lists of item ids.
    """
    clusters: list[list[str]] = []
    representatives: list[set[str]] = []
    assignment: dict[str, int] = {}

    ordered = sorted(items, key=lambda x: (x.get("published") or "", x.get("id") or ""))
    for item in ordered:
        iid = item.get("id") or hashlib.sha1(repr(item).encode()).hexdigest()[:12]
        fp = _fingerprint(item)
        chosen = None
        best = 0.0
        for idx, rep in enumerate(representatives):
            score = jaccard(fp, rep)
            if score > best:
                best, chosen = score, idx
        if chosen is None or best < threshold:
            chosen = len(clusters)
            clusters.append([])
            representatives.append(fp)
        clusters[chosen].append(iid)
        assignment[iid] = chosen
    return assignment, clusters
