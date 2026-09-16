"""LLM-assisted triage and extraction with an offline, deterministic fallback."""

from __future__ import annotations

import json
import os
import re
import requests


MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-5"
PROMPT_VERSION = "analyze/5"
API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM = """You are a careful research assistant monitoring political-party output.
Return JSON only. Never decide whether a statement is racist, antisemitic, extremist,
true, or false. Preserve the boundary between source material and inference.

Schema:
{"relevant": true, "triaged_out": "", "confidence": "high",
 "action_type": "Policy proposal|Parliamentary intervention|Election or campaign|Organisational change|Mobilisation or protest|Legal action|Alliance or coordination|Public statement|Reported development",
 "actors": ["Full Name"],
 "summary": "one factual sentence",
 "quotes": [{"original":"verbatim source-language sentence",
             "translation":"faithful English translation", "speaker":"name or party"}],
 "relations": [{"source":"organisation", "target":"organisation",
                 "kind":"joint_appearance|endorsement|alliance|split|criticism",
                 "detail":"short evidence description"}]}

Relevant means the item contains a substantive position, action, speech, policy,
campaign intervention, organisational change, or parliamentary intervention by or
about the named party. Routine navigation, event listings, duplicates, and unrelated
mentions are not relevant. Quotes must be genuinely verbatim; never reconstruct one.
If there is no usable quote, return an empty list. Action type describes the observable
form of activity, never its ideological subject."""


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


def _fallback(item: dict, party: dict) -> dict:
    title = re.sub(r"\s+", " ", item.get("title") or "").strip()
    body = re.sub(r"\s+", " ", item.get("body") or "").strip()
    text = f"{title} {body}"
    if not text.strip():
        return {
            "relevant": False, "skipped": True, "confidence": "low",
            "action_type": "Reported development", "actors": [], "summary": "",
            "quotes": [], "relations": [],
        }
    summary = title or body[:220]
    if body and title and body.casefold() != title.casefold():
        summary = f"{title}. {body[:260]}"
    return {
        "relevant": True,
        "confidence": "low",
        "action_type": ("Public statement" if item.get("source_type") in {
            "party_site", "site_feed", "site_scrape", "party_archive", "party_search",
            "telegram", "youtube", "leader", "parliament", "hansard",
            "parliamentary_record",
        } else "Reported development"),
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
        # Old model aliases can still emit the retired topic field. Do not
        # retain it: reports are organised by party activity, not topic tags.
        out.pop("topics", None)
        out.setdefault("confidence", "medium")
        out.setdefault("action_type", "Reported development")
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
                "Name the most consequential party actions and any cross-party contrast. "
                "Do not evaluate claims."
            ),
            "messages": [{"role": "user", "content": "\n".join(lines)}],
        }
        try:
            return _response_text(_call(payload)).strip()
        except Exception:
            pass
    parties = {i.get("party_name") or i.get("party_id") for i in relevant}
    return (f"{len(relevant)} substantive party actions or statements were retained "
            f"this week across {len(parties)} monitored parties.")
