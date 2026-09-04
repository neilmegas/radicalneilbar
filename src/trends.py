"""Small, inspectable longitudinal summaries used by the static portal."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta


THEMES = ["israel_palestine", "jews_antisemitism", "immigration"]


def iso_weeks_back(week: str, count: int) -> list[str]:
    year, number = int(week[:4]), int(week.split("W")[1])
    current = datetime.fromisocalendar(year, number, 1)
    return [
        f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
        for d in (current - timedelta(weeks=n) for n in reversed(range(count)))
    ]


def theme_series(conn, party_id: str, weeks: list[str]) -> list[dict]:
    if not weeks:
        return []
    placeholders = ",".join("?" for _ in weeks)
    rows = conn.execute(
        f"SELECT week, analysis, cluster_id FROM items WHERE party_id=? "
        f"AND analysis IS NOT NULL AND week IN ({placeholders})",
        (party_id, *weeks),
    ).fetchall()
    import json
    counts = {week: Counter() for week in weeks}
    seen_clusters = set()
    for week, raw, cluster_id in rows:
        analysis = json.loads(raw) if raw else {}
        if not analysis.get("relevant"):
            continue
        key = (week, cluster_id) if cluster_id else None
        if key and key in seen_clusters:
            continue
        if key:
            seen_clusters.add(key)
        counts.setdefault(week, Counter()).update(t for t in analysis.get("topics", []) if t in THEMES)
    return [{"week": week, **{theme: counts[week][theme] for theme in THEMES}} for week in weeks]


def shifts(series: list[dict]) -> list[dict]:
    if len(series) < 2:
        return []
    current, previous = series[-1], series[:-1]
    out = []
    for theme in THEMES:
        earlier = [row.get(theme, 0) for row in previous]
        if current.get(theme, 0) > 0 and not any(earlier):
            out.append({"theme": theme, "kind": "new",
                        "detail": f"first engagement in {len(previous)} prior weeks"})
        elif current.get(theme, 0) == 0 and sum(v > 0 for v in earlier[-4:]) >= 3:
            out.append({"theme": theme, "kind": "dropped",
                        "detail": "present in at least three of the previous four weeks"})
    return out


def absence_report(items: list[dict], country: dict, parties: list[dict], start, end) -> list[dict]:
    out = []
    for occasion in country.get("occasions") or []:
        month = int(occasion.get("month", 0))
        first = int(occasion.get("start_day", occasion.get("day", 1)))
        last = int(occasion.get("end_day", first))
        dates = []
        day = start.date()
        while day <= end.date():
            if day.month == month and first <= day.day <= last:
                dates.append(day)
            day += timedelta(days=1)
        if not dates:
            continue
        terms = [str(x).casefold() for x in occasion.get("keywords") or []]
        engaged = set()
        for item in items:
            analysis = item.get("analysis") or {}
            haystack = " ".join([
                item.get("title") or "", item.get("body") or "", analysis.get("summary") or "",
            ]).casefold()
            if any(term in haystack for term in terms):
                engaged.add(item.get("party_id"))
        by_id = {p["id"]: p for p in parties}
        spoke = [by_id[x].get("short", x) for x in sorted(engaged) if x in by_id]
        silent = [p.get("short", p["id"]) for p in parties if p["id"] not in engaged]
        out.append({
            "occasion": occasion.get("name", "Occasion"),
            "date": f"{dates[0].isoformat()}–{dates[-1].isoformat()}" if len(dates) > 1
                    else dates[0].isoformat(),
            "spoke": spoke,
            "silent_names": silent,
        })
    return out


def _words(text: str) -> set[str]:
    stop = {"that", "this", "with", "from", "have", "will", "their", "about", "which",
            "eine", "einer", "und", "oder", "pour", "dans", "avec", "mais", "sono", "della"}
    return {w for w in re.findall(r"[^\W_]{5,}", (text or "").casefold(), flags=re.UNICODE)
            if w not in stop}


def convergence(conn, parties: list[dict], week: str, store) -> list[dict]:
    by_id = {p["id"]: p for p in parties}
    usage = defaultdict(lambda: {"left": set(), "right": set()})
    for item in store.week_items(conn, week, analyzed_only=True):
        party = by_id.get(item.get("party_id"), {})
        camp, lang = party.get("camp"), item.get("lang") or party.get("lang") or "?"
        if camp not in {"left", "right"}:
            continue
        quotes = (item.get("analysis") or {}).get("quotes") or []
        for quote in quotes:
            for word in _words(quote.get("original") or ""):
                usage[(lang, word)][camp].add(party.get("short") or item.get("party_id"))
    out = []
    for (lang, word), camps in usage.items():
        if camps["left"] and camps["right"]:
            out.append({"term": word, "lang": lang,
                        "left": sorted(camps["left"]), "right": sorted(camps["right"])})
    return sorted(out, key=lambda x: (-(len(x["left"]) + len(x["right"])), x["term"]))[:30]


def _speaker_key(name: str) -> str:
    norm = unicodedata.normalize("NFKC", name or "").casefold()
    return re.sub(r"\s+", " ", norm).strip()


def speaker_index(conn, parties: list[dict], store) -> dict[str, dict]:
    by_id = {p["id"]: p for p in parties}
    index = {}
    for week in store.all_weeks(conn):
        for item in store.week_items(conn, week, analyzed_only=True):
            analysis = item.get("analysis") or {}
            if not analysis.get("relevant"):
                continue
            quoted = Counter(q.get("speaker") for q in analysis.get("quotes") or [] if q.get("speaker"))
            names = list(dict.fromkeys((analysis.get("actors") or []) + list(quoted)))
            for name in names:
                key = _speaker_key(name)
                if not key:
                    continue
                rec = index.setdefault(key, {
                    "display": name, "parties": set(), "items": [], "quoted": 0,
                    "themes": Counter(),
                })
                rec["parties"].add((by_id.get(item.get("party_id")) or {}).get("short")
                                   or item.get("party_id"))
                if item["id"] not in rec["items"]:
                    rec["items"].append(item["id"])
                    rec["themes"].update(analysis.get("topics") or [])
                rec["quoted"] += quoted.get(name, 0)
    for rec in index.values():
        rec["parties"] = sorted(rec["parties"])
        rec["themes"] = dict(rec["themes"])
    return index
