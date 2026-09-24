"""National news collection and country-context writing."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests

from analyze import MODEL, _call, _response_text
from collect import HEADERS, TIMEOUT, _clean_html, _date, _recent


def fetch_country_news(country: dict, since, days: int = 7) -> list[dict]:
    queries = country.get("news_queries") or [f"{country.get('name')} politics"]
    out, seen = [], set()
    for query in queries[:5]:
        try:
            feed = (
                "https://news.google.com/rss/search?q="
                + quote_plus(f"{query} when:{max(1, int(days))}d")
                + "&hl=en&gl=US&ceid=US:en"
            )
            response = requests.get(feed, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            for entry in feedparser.parse(response.content).entries[:30]:
                title = entry.get("title") or ""
                if not title or title.casefold() in seen:
                    continue
                seen.add(title.casefold())
                published = _date(entry.get("published") or entry.get("updated"))
                if not _recent(published, since):
                    continue
                source = entry.get("source", {})
                out.append({
                    "title": title,
                    "url": entry.get("link") or "",
                    "published": published,
                    "body": _clean_html(entry.get("summary") or ""),
                    "source": source.get("title", "Google News") if isinstance(source, dict)
                              else "Google News",
                })
        except Exception:
            continue
    return out[:80]


def _ask(system: str, prompt: str, max_tokens: int = 900) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ""
    try:
        return _response_text(_call({
            "model": MODEL,
            "max_tokens": max_tokens,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        })).strip()
    except Exception:
        return ""


def refresh_background(country: dict, parties: list[dict]) -> str:
    names = ", ".join(p.get("name", p.get("id", "")) for p in parties)
    prompt = (
        f"Country: {country.get('name')} ({country.get('code')})\n"
        f"Monitored parties: {names}\n\n"
        "Write a durable primer covering the system of government, current election "
        "calendar, monitored parties' parliamentary status, and live legal or institutional "
        "questions that affect them. Distinguish known facts from uncertainty. Do not invent "
        "current office-holders if the information supplied is insufficient."
    )
    answer = _ask(
        "You write a concise factual country primer for a political monitoring archive. "
        "Use plain paragraphs, no markdown heading, and no evaluative labels.",
        prompt,
        1000,
    )
    if answer:
        return answer
    return (
        f"Starter primer for {country.get('name')}. The monitored roster currently contains "
        f"{len(parties)} parties: {names or 'none'}. No API key was available when this primer "
        "was generated, so verify the government, election calendar, parliamentary status, "
        "and any pending legal proceedings before relying on it."
    )


def country_brief(country: dict, background: str | None, news: list[dict],
                  party_items: list[dict]) -> str:
    news_lines = "\n".join(f"- {n['title']} ({n.get('source','')})" for n in news[:25])
    party_lines = "\n".join(
        f"- {i.get('party_name', i.get('party_id'))}: "
        f"{(i.get('analysis') or {}).get('summary', i.get('title',''))}"
        for i in party_items[:40]
    )
    answer = _ask(
        "Write a neutral 100-180 word national political briefing. Use only the supplied "
        "material, relate the week's party activity to the durable background, and state "
        "when evidence is thin. Do not evaluate whether a statement is extreme or hateful.",
        f"COUNTRY: {country.get('name')}\n\nSTANDING BACKGROUND:\n{background or '(none)'}"
        f"\n\nNATIONAL HEADLINES:\n{news_lines or '(none)'}"
        f"\n\nMONITORED PARTY ITEMS:\n{party_lines or '(none)'}",
        700,
    )
    if answer:
        return answer
    if party_items:
        return (
            f"{len(party_items)} analysed item(s) from monitored parties were retained for "
            f"{country.get('name')} this week. This automatically generated fallback does not "
            "attempt a national-context interpretation; review the linked sources directly."
        )
    return f"No substantive monitored-party items were retained for {country.get('name')} this week."
