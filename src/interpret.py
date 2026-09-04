"""Per-item interpretation kept visibly separate from source evidence."""

from __future__ import annotations

import json
import os
import re

import yaml

from analyze import MODEL, _call, _response_text


PROMPT_VERSION = "interpret/2"


def load_frameworks(path: str = "config/frameworks.yaml") -> list[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return data.get("frameworks") or []
    except FileNotFoundError:
        return []


def _parse_json(data: dict) -> dict:
    raw = _response_text(data).strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
    return json.loads(raw[raw.find("{"):raw.rfind("}") + 1])


def _fallback(item: dict) -> dict:
    return {
        "significance": "routine",
        "confidence": "low",
        "explanation": "",
        "reading": "No model-assisted interpretation was produced; read the source and factual summary directly.",
        "why_now": "Timing was not assessed.",
        "continuity": "unclear",
        "continuity_note": "The record was not assessed for continuity.",
        "comparison": "",
        "watch": "Look for repetition, implementation, or a response from other parties.",
        "frameworks": [],
        "caveat": "Fallback text generated because no API key was available or the request failed.",
    }


def interpret_item(conn, item: dict, party: dict, week_items: list[dict],
                   country_brief: str | None, frameworks: list[dict], store, trends) -> dict:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback(item)
    history = store.party_items(conn, party["id"])[:60]
    previous = "\n".join(
        f"- {(h.get('published') or '')[:10]}: {(h.get('analysis') or {}).get('summary','')}"
        for h in history if h.get("id") != item.get("id")
    )[:9000]
    peers = "\n".join(
        f"- {i.get('party_name', i.get('party_id'))}: {(i.get('analysis') or {}).get('summary','')}"
        for i in week_items if i.get("id") != item.get("id")
    )[:7000]
    fw = "\n".join(f"- {f.get('name')}: {f.get('description')}" for f in frameworks)
    prompt = f"""PARTY: {party.get('name')} ({party.get('country')})
ITEM: {json.dumps(item.get('analysis') or {}, ensure_ascii=False)}
TITLE/DATE: {item.get('title')} / {item.get('published')}
COUNTRY BRIEF: {country_brief or '(none)'}

PREVIOUS PARTY RECORD:
{previous or '(thin record)'}

OTHER PARTIES THIS WEEK:
{peers or '(none)'}

OPTIONAL FRAMEWORKS:
{fw or '(none)'}

Return JSON only with:
{{"significance":"routine|notable|unusual", "confidence":"low|medium|high",
"explanation":"factual context only", "reading":"political interpretation",
"why_now":"timing", "continuity":"consistent|escalation|break|unclear",
"continuity_note":"comparison to own record", "comparison":"comparison to peers",
"watch":"one observable confirmation or disconfirmation",
"frameworks":["exact framework names, candidates only"], "caveat":"key uncertainty"}}"""
    try:
        out = _parse_json(_call({
            "model": MODEL,
            "max_tokens": 1200,
            "temperature": 0,
            "system": (
                "You write disciplined political interpretation. Facts and inference must stay "
                "separate. Never decide whether speech is antisemitic, racist, extremist, true, "
                "or justified. Do not invent motives. Use uncertainty plainly."
            ),
            "messages": [{"role": "user", "content": prompt}],
        }))
        base = _fallback(item)
        base.update(out)
        allowed = {f.get("name") for f in frameworks}
        base["frameworks"] = [x for x in (base.get("frameworks") or []) if x in allowed]
        return base
    except Exception:
        return _fallback(item)


def editors_cut(items: list[dict], limit: int = 8) -> list[dict]:
    weight = {"unusual": 3, "notable": 2, "routine": 1}
    rows = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    rows.sort(key=lambda i: (
        -weight.get((i.get("interpretation") or {}).get("significance", "routine"), 1),
        i.get("provenance_rank") or 9,
    ))
    return rows[:limit]
