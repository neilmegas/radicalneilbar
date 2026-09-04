"""LLM-assisted triage and extraction with an offline, deterministic fallback."""

from __future__ import annotations

import json
import os
import re
from collections import Counter

import requests


MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-5"
PROMPT_VERSION = "analyze/3"
API_URL = "https://api.anthropic.com/v1/messages"

THEME_TERMS = {
    "israel_palestine": [
        "israel", "israeli", "palestine", "palestinian", "gaza", "west bank",
        "zionis", "ισραήλ", "παλαιστ", "israël", "palästina", "פלסט", "ישראל",
    ],
    "jews_antisemitism": [
        "jew", "jews", "jewish", "antisemit", "anti-semit", "zionist conspiracy",
        "juif", "juive", "jüdisch", "antisemitismus", "εβραί", "αντισημι", "יהוד", "אנטישמ",
    ],
    "immigration": [
        "immigration", "immigrant", "migration", "migrant", "asylum", "refugee",
        "deport", "remigration", "border", "μετανάστ", "προσφυγ", "migration",
        "einwander", "abschieb", "immigrazione", "inmigración", "invandring",
    ],
}

SYSTEM = """You are a careful research assistant monitoring political-party output.
Return JSON only. Never decide whether a statement is racist, antisemitic, extremist,
true, or false. Preserve the boundary between source material and inference.

Schema:
{"relevant": true, "triaged_out": "", "topics": ["israel_palestine"],
 "confidence": "high", "actors": ["Full Name"],
 "summary": "one factual sentence",
 "quotes": [{"original":"verbatim source-language sentence",
             "translation":"faithful English translation", "speaker":"name or party"}],
 "relations": [{"source":"organisation", "target":"organisation",
                 "kind":"joint_appearance|endorsement|alliance|split|criticism",
                 "detail":"short evidence description"}]}

Use only these topic labels: israel_palestine, jews_antisemitism, immigration.
Relevant means the item contains a substantive position, action, speech, policy,
campaign intervention, organisational change, or parliamentary intervention by or
about the named party. Routine navigation, event listings, duplicates, and unrelated
mentions are not relevant. Quotes must be genuinely verbatim; never reconstruct one.
If there is no usable quote, return an empty list."""


def _call(payload: dict) -> dict:
    """Low-level Anthropic Messages API call used by other modules too."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = dict(payload)
    body["model"] = os.environ.get("ANTHROPIC_MODEL") or body.get("model") or MODEL
    response = requests.post(
        API_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def _response_text(data: dict) -> str:
    return "".join(
        part.get("text", "") for part in data.get("content", [])
        if part.get("type") == "text"
    )


def _parse_json(data: dict) -> dict:
    raw = _response_text(data).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model response did not contain a JSON object")
    return json.loads(raw[start:end + 1])


def _themes(text: str) -> list[str]:
    folded = (text or "").casefold()
    return [theme for theme, terms in THEME_TERMS.items() if any(t in folded for t in terms)]


def _fallback(item: dict, party: dict) -> dict:
    title = re.sub(r"\s+", " ", item.get("title") or "").strip()
    body = re.sub(r"\s+", " ", item.get("body") or "").strip()
    text = f"{title} {body}"
    if not text.strip():
        return {
            "relevant": False, "skipped": True, "topics": [], "confidence": "low",
            "actors": [], "summary": "", "quotes": [], "relations": [],
        }
    summary = title or body[:220]
    if body and title and body.casefold() != title.casefold():
        summary = f"{title}. {body[:260]}"
    return {
        "relevant": True,
        "topics": _themes(text),
        "confidence": "low",
        "actors": [],
        "summary": summary[:420],
        "quotes": [],
        "relations": [],
        "fallback": "No API key was available; this item needs human review.",
    }


def analyze_item(item: dict, party: dict) -> dict:
    """Analyse one collected item. API failure is explicit and fails open."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(item, party)
    source = (item.get("body") or item.get("title") or "")[:18000]
    prompt = (
        f"Party: {party.get('name')} ({party.get('country')})\n"
        f"Source type: {item.get('source_type')}\n"
        f"Date: {item.get('published')}\nTitle: {item.get('title')}\n"
        f"URL: {item.get('url')}\nLanguage hint: {item.get('lang') or party.get('lang')}\n\n"
        f"SOURCE TEXT\n{source}"
    )
    payload = {
        "model": MODEL,
        "max_tokens": 1800,
        "temperature": 0,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        out = _parse_json(_call(payload))
        out.setdefault("relevant", True)
        out["topics"] = [t for t in (out.get("topics") or []) if t in THEME_TERMS]
        out.setdefault("confidence", "medium")
        out.setdefault("actors", [])
        out.setdefault("summary", item.get("title") or "")
        out.setdefault("quotes", [])
        out.setdefault("relations", [])
        return out
    except Exception as exc:
        out = _fallback(item, party)
        out["error"] = f"analysis failed; fallback used: {type(exc).__name__}"
        return out


def weekly_overview(items: list[dict]) -> str:
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    if not relevant:
        return "Nothing substantive was collected this week."
    if os.environ.get("ANTHROPIC_API_KEY"):
        lines = [
            f"- {i.get('party_name', i.get('party_id'))}: "
            f"{(i.get('analysis') or {}).get('summary', '')}"
            for i in relevant[:80]
        ]
        payload = {
            "model": MODEL,
            "max_tokens": 500,
            "temperature": 0,
            "system": (
                "Write a neutral 2-4 sentence weekly overview from the supplied item summaries. "
                "Name the dominant themes and any cross-party contrast. Do not evaluate claims."
            ),
            "messages": [{"role": "user", "content": "\n".join(lines)}],
        }
        try:
            return _response_text(_call(payload)).strip()
        except Exception:
            pass
    counts = Counter(t for i in relevant for t in ((i.get("analysis") or {}).get("topics") or []))
    names = {
        "israel_palestine": "Israel and Palestine",
        "jews_antisemitism": "Jews and antisemitism",
        "immigration": "immigration",
    }
    lead = ", ".join(f"{names[k]} ({v})" for k, v in counts.most_common()) or "other issues"
    return f"{len(relevant)} substantive items were retained this week. The tagged agenda was {lead}."
