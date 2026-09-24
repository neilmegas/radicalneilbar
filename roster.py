"""Conservative monthly roster-gap suggestions."""

from __future__ import annotations

import json
import os
import re

import yaml

from analyze import MODEL, _call, _response_text


def check_country(country: dict, monitored: list[dict]) -> list[dict]:
    """Ask the configured model for proposals, never automatic additions.

    No API key means no proposals. This is safer than fabricating a current
    roster from stale code.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return []
    current = ", ".join(p.get("name", p["id"]) for p in monitored)
    prompt = f"""Country: {country.get('name')}
Already monitored: {current or '(none)'}

Suggest only clearly relevant political parties that may be missing. Do not
include movements that do not contest elections. If you cannot establish a
current candidate from your knowledge, return an empty list. Return JSON only:
{{"candidates":[{{"name":"", "camp":"left|right", "why":"", "origin":"",
"founded":"", "polling":"", "seats":"", "site":""}}]}}"""
    try:
        data = _call({
            "model": MODEL, "max_tokens": 900, "temperature": 0,
            "system": "Make conservative research suggestions. Never imply the list is verified current.",
            "messages": [{"role": "user", "content": prompt}],
        })
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", _response_text(data).strip(),
                     flags=re.I | re.S)
        parsed = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
        return [x for x in parsed.get("candidates", []) if x.get("name")]
    except Exception:
        return []


def to_yaml_stub(candidate: dict, country: dict) -> str:
    name = candidate.get("name") or "candidate"
    slug = re.sub(r"[^a-z0-9]+", "", name.casefold())[:24] or "candidate"
    row = {
        "id": slug,
        "name": name,
        "short": name,
        "country": country.get("code"),
        "camp": candidate.get("camp", "right"),
        "site": candidate.get("site") or None,
        "queries": [name],
    }
    return yaml.safe_dump([row], allow_unicode=True, sort_keys=False).strip()
