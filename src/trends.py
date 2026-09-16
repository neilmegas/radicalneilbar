"""Small, inspectable longitudinal summaries used by the static portal."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import timedelta


ACTION_TYPES = [
    "Policy proposal",
    "Parliamentary intervention",
    "Election or campaign",
    "Organisational change",
    "Mobilisation or protest",
    "Legal action",
    "Alliance or coordination",
    "Public statement",
    "Reported development",
]

DIRECT_SOURCE_TYPES = {
    "party_site", "site_feed", "site_scrape", "party_archive", "party_search",
    "telegram", "youtube", "leader", "parliament", "hansard",
    "parliamentary_record",
}
DIRECT_PROVENANCE = {"party_document", "leader_direct", "parliamentary_record"}


def is_direct(item: dict) -> bool:
    """Whether an item is controlled by the party or is an official record."""
    return (item.get("provenance") in DIRECT_PROVENANCE
            or item.get("source_type") in DIRECT_SOURCE_TYPES)


def _item_text(item: dict) -> str:
    analysis = item.get("analysis") or {}
    return " ".join([
        str(item.get("title") or ""),
        str(analysis.get("summary") or ""),
        str(item.get("body") or "")[:4000],
    ]).casefold()


def _clip(text: str, limit: int = 260) -> str:
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def action_type(item: dict) -> str:
    """Classify what happened, not what ideological subject it concerned.

    New analyses carry this field explicitly. Older records are classified by
    transparent keyword rules so the historical archive gains the same filter
    without a costly or irreproducible re-analysis pass.
    """
    analysis = item.get("analysis") or {}
    supplied = str(analysis.get("action_type") or "").strip()
    aliases = {
        "policy": "Policy proposal",
        "parliament": "Parliamentary intervention",
        "election": "Election or campaign",
        "campaign": "Election or campaign",
        "organisation": "Organisational change",
        "organization": "Organisational change",
        "mobilisation": "Mobilisation or protest",
        "mobilization": "Mobilisation or protest",
        "legal": "Legal action",
        "alliance": "Alliance or coordination",
        "statement": "Public statement",
        "reported": "Reported development",
    }
    if supplied in ACTION_TYPES:
        return supplied
    if supplied.casefold() in aliases:
        return aliases[supplied.casefold()]

    source_type = str(item.get("source_type") or "")
    if source_type in {"parliament", "hansard", "parliamentary_record"}:
        return "Parliamentary intervention"
    relations = analysis.get("relations") or []
    if any(r.get("kind") in {"joint_appearance", "endorsement", "alliance", "split"}
           for r in relations if isinstance(r, dict)):
        return "Alliance or coordination"

    text = _item_text(item)
    rules = [
        ("Legal action", r"\b(court|trial|lawsuit|sues?|sued|judge|prosecut|convict|"
                         r"indict|legal challenge|constitutional court|arrest|police investigation)\b"),
        ("Mobilisation or protest", r"\b(rally|demonstration|protest|march|strike|"
                                      r"street mobilisation|street mobilization)\b"),
        ("Alliance or coordination", r"\b(coalition|alliance|pact|joint statement|"
                                       r"joint appearance|endorse|delegation|cooperat|split|merger)\b"),
        ("Organisational change", r"\b(leadership|party leader|party congress|conference|"
                                  r"resign|expel|membership|candidate selection|founded|"
                                  r"launch(?:ed|es|ing)? the party)\b"),
        ("Election or campaign", r"\b(election|electoral|campaign|candidate|polling?|ballot|"
                                 r"constituency|seat projection)\b"),
        ("Parliamentary intervention", r"\b(parliament|knesset|bundestag|assembly|bill|motion|"
                                         r"amendment|committee|lawmaker|legislation|parliamentary vote)\b"),
        ("Policy proposal", r"\b(policy|proposal|programme|program|manifesto|plan|demands?|"
                            r"calls? for|pledges?|would abolish|would introduce)\b"),
    ]
    for label, pattern in rules:
        if re.search(pattern, text):
            return label
    return "Public statement" if is_direct(item) else "Reported development"


def week_in_one_minute(items: list[dict], highlights: list[dict] | None = None,
                       limit: int = 5) -> list[dict]:
    """A short evidence-linked account of the week's most important actions."""
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    by_id = {i["id"]: i for i in relevant}
    ordered = []
    for row in highlights or []:
        item = by_id.get(row.get("item_id")) if isinstance(row, dict) else None
        if item and item not in ordered:
            ordered.append(item)
    ordered += [i for i in sorted(
        relevant,
        key=lambda x: (is_direct(x), x.get("published") or ""),
        reverse=True,
    ) if i not in ordered]

    out, used_parties = [], set()
    for item in ordered:
        pid = item.get("party_id")
        if pid in used_parties and len(out) < min(limit, len({i.get('party_id') for i in ordered})):
            continue
        used_parties.add(pid)
        analysis = item.get("analysis") or {}
        text = analysis.get("summary") or item.get("title") or "Recorded activity"
        out.append({
            "item_id": item.get("id"),
            "party": item.get("party_name") or pid,
            "action": action_type(item),
            "text": _clip(text),
        })
        if len(out) >= limit:
            break
    return out


def week_changes(current: list[dict], previous: list[dict], previous_week: str = "",
                 limit: int = 8) -> list[dict]:
    """Describe changes in the retained record without inferring ideology."""
    current = [i for i in current if (i.get("analysis") or {}).get("relevant")]
    previous = [i for i in previous if (i.get("analysis") or {}).get("relevant")]
    current_by, previous_by = {}, {}
    for item in current:
        current_by.setdefault(item.get("party_id"), []).append(item)
    for item in previous:
        previous_by.setdefault(item.get("party_id"), []).append(item)

    rows = []
    for pid in sorted(set(current_by) | set(previous_by)):
        now, before = current_by.get(pid, []), previous_by.get(pid, [])
        party = ((now or before)[0].get("party_name") or pid)
        direct_now = sum(is_direct(i) for i in now)
        direct_before = sum(is_direct(i) for i in before)
        now_types = {action_type(i) for i in now}
        before_types = {action_type(i) for i in before}
        new_types = sorted(now_types - before_types)
        reference = next((i for i in now if is_direct(i)), now[0] if now else None)

        if now and not before:
            rows.append((0, {
                "party": party, "kind": "Newly active",
                "text": (f"Entered the retained weekly record after no retained item in "
                         f"{previous_week or 'the previous report'}; {len(now)} item(s), "
                         f"including {direct_now} direct record(s)."),
                "item_id": reference.get("id") if reference else "",
            }))
        elif now and new_types:
            rows.append((1, {
                "party": party, "kind": "New recorded action",
                "text": ("Action type not present in the previous report: "
                         + ", ".join(new_types) + "."),
                "item_id": reference.get("id") if reference else "",
            }))
        elif now and abs(direct_now - direct_before) >= 2:
            direction = "rose" if direct_now > direct_before else "fell"
            rows.append((2, {
                "party": party, "kind": "Direct-document volume",
                "text": f"Direct records {direction} from {direct_before} to {direct_now}.",
                "item_id": reference.get("id") if reference else "",
            }))
        elif before and not now:
            rows.append((3, {
                "party": party, "kind": "No retained activity",
                "text": (f"Had retained activity in {previous_week or 'the previous report'} "
                         "but none in this issue; consult collection coverage before reading this as silence."),
                "item_id": "",
            }))
    return [row for _, row in sorted(rows, key=lambda x: (x[0], x[1]["party"]))[:limit]]


def coverage_report(week: str, parties: list[dict], items: list[dict],
                    logs: list[dict]) -> dict:
    """Summarise what was checked and distinguish silence from failure."""
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    by_party, by_log = {}, {}
    for item in relevant:
        by_party.setdefault(item.get("party_id"), []).append(item)
    for row in logs:
        if row.get("week") == week:
            by_log.setdefault(row.get("party_id"), []).append(row)

    official_channels = {"site_feed", "site_scrape", "party_archive", "party_search"}
    fallback_channels = {"party_search", "web_search"}
    entries, counts = [], Counter()
    for party in parties:
        pid = party["id"]
        mine, attempts = by_party.get(pid, []), by_log.get(pid, [])
        direct = [i for i in mine if is_direct(i)]
        coverage = [i for i in mine if not is_direct(i)]
        official = [a for a in attempts if a.get("channel") in official_channels]
        fallback = any(a.get("channel") in fallback_channels for a in attempts)
        errors = [a.get("error") for a in official if not a.get("ok") and a.get("error")]

        if direct:
            status = "Direct material found"
        elif coverage:
            status = "Outside reporting only"
        elif not attempts:
            status = "No archived check"
        elif official and not any(a.get("ok") for a in official):
            status = "Official source inaccessible"
        else:
            status = "No dated activity retained"
        counts[status] += 1
        if fallback:
            counts["Search fallback used"] += 1
        entries.append({
            "party_id": pid,
            "party": party.get("short") or party.get("name") or pid,
            "country": party.get("country") or "",
            "status": status,
            "direct": len(direct),
            "coverage": len(coverage),
            "fallback": fallback,
            "error": (errors[0] if errors else "")[:140],
        })
    return {
        "checked": sum(1 for e in entries if e["status"] != "No archived check"),
        "total": len(parties),
        "counts": dict(counts),
        "entries": entries,
    }


def watch_next(items: list[dict], limit: int = 5) -> list[dict]:
    """Build evidence-linked follow-up questions for the next reporting week."""
    templates = {
        "Policy proposal": "Watch for a formal proposal, implementation step, or response from competitors.",
        "Parliamentary intervention": "Watch for the next committee, amendment, or vote connected to this intervention.",
        "Election or campaign": "Watch for candidate decisions, polling movement, or a repeated campaign line.",
        "Organisational change": "Watch for appointments, defections, disciplinary action, or formal confirmation.",
        "Mobilisation or protest": "Watch for turnout claims, follow-up demonstrations, or official responses.",
        "Legal action": "Watch for the next filing, hearing, judgment, appeal, or enforcement step.",
        "Alliance or coordination": "Watch for formal confirmation, a joint appearance, or further coordinated action.",
        "Public statement": "Watch whether this statement becomes a formal policy or is repeated by other party figures.",
        "Reported development": "Watch for confirmation in a direct party document or official record.",
    }
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    relevant.sort(key=lambda i: (is_direct(i), i.get("published") or ""), reverse=True)
    out, parties = [], set()
    for item in relevant:
        if item.get("party_id") in parties:
            continue
        parties.add(item.get("party_id"))
        action = action_type(item)
        explicit = (item.get("interpretation") or {}).get("watch")
        out.append({
            "item_id": item.get("id"),
            "party": item.get("party_name") or item.get("party_id"),
            "action": action,
            "text": explicit or templates[action],
        })
        if len(out) >= limit:
            break
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
                })
                rec["parties"].add((by_id.get(item.get("party_id")) or {}).get("short")
                                   or item.get("party_id"))
                if item["id"] not in rec["items"]:
                    rec["items"].append(item["id"])
                rec["quoted"] += quoted.get(name, 0)
    for rec in index.values():
        rec["parties"] = sorted(rec["parties"])
    return index
