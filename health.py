"""Two things the system needs to know about itself.

SOURCE HEALTH — whether collection is still working, per party and per
channel, across weeks. This is the failure mode most likely to hurt and least
likely to announce itself: a feed that dies quietly in November looks exactly
like a party that went quiet, and without a trend you would not know which for
months. The per-issue "unreachable" line is a snapshot; this is the series.

RELIABILITY — agreement between your coding and the model's tagging, computed
from blind rounds rather than impressions. The same machinery gives you
inter-coder reliability if a second person codes, which is what you would need
for a methods appendix anyway.
"""

import json
from collections import defaultdict

THEMES = ["israel_palestine", "jews_antisemitism", "immigration"]


# ------------------------------------------------------------- health

def health_table(history, parties, min_weeks=3):
    """Per party and channel: success rate over the observed weeks, and
    whether it is currently failing after having previously worked."""
    by_key = defaultdict(list)
    weeks = sorted({h["week"] for h in history}, reverse=True)
    for h in history:
        by_key[(h["party_id"], h["channel"])].append(h)

    by_id = {p["id"]: p for p in parties}
    rows = []
    for (pid, channel), entries in by_key.items():
        entries.sort(key=lambda x: x["week"], reverse=True)
        ok = sum(1 for e in entries if e["ok"])
        n = len(entries)
        recent = entries[:min_weeks]
        recent_ok = sum(1 for e in recent if e["ok"])
        older = entries[min_weeks:]
        older_ok = sum(1 for e in older if e["ok"])

        # The state worth flagging is not "broken" but "used to work".
        # A source that never worked is a configuration error you already know
        # about; one that stopped is new information.
        if recent_ok == 0 and older_ok > 0:
            state = "regressed"
        elif recent_ok == 0 and n >= min_weeks:
            state = "never worked"
        elif recent_ok < len(recent):
            state = "intermittent"
        else:
            state = "healthy"

        rows.append({
            "party_id": pid,
            "party": (by_id.get(pid) or {}).get("short") or pid,
            "country": (by_id.get(pid) or {}).get("country", ""),
            "channel": channel, "weeks": n, "ok": ok,
            "rate": round(ok / n, 2) if n else 0.0,
            "items": sum(e["n"] for e in entries),
            "state": state,
            "last_error": next((e["error"] for e in entries if e["error"]), ""),
            "series": [1 if e["ok"] else 0 for e in reversed(entries)][-12:],
        })

    order = {"regressed": 0, "never worked": 1, "intermittent": 2, "healthy": 3}
    rows.sort(key=lambda r: (order[r["state"]], -r["weeks"], r["party"]))
    return rows, weeks


def silent_parties(history, parties, weeks_back=4):
    """Parties producing nothing for several consecutive weeks despite their
    channels reporting success. That combination is the interesting one: the
    collection works and the party genuinely has no output, or the selector is
    matching an empty page and reporting success."""
    weeks = sorted({h["week"] for h in history}, reverse=True)[:weeks_back]
    if len(weeks) < weeks_back:
        return []
    by_id = {p["id"]: p for p in parties}
    out = []
    for p in parties:
        rel = [h for h in history if h["party_id"] == p["id"] and h["week"] in weeks]
        if not rel:
            continue
        if all(h["n"] == 0 for h in rel) and any(h["ok"] for h in rel):
            out.append({"party": p.get("short") or p["id"],
                        "country": p.get("country", ""), "weeks": len(weeks)})
    return out


# -------------------------------------------------------- reliability

def sample_for_round(items, n=20, seed=None):
    """A reproducible sample. Seeded on the round id so the same round always
    draws the same items — otherwise the sample is not re-examinable."""
    import random
    pool = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool[:n]


def agreement(model_tags, human_tags, labels=None):
    """Per-label agreement and Cohen's kappa.

    Themes are multi-label, so this treats each label as its own binary
    decision rather than forcing a single-label comparison. Raw agreement is
    reported alongside kappa because kappa is unstable when a label is rare —
    which `jews_antisemitism` will be, and reporting kappa alone on a rare
    label invites over-reading a wild number.
    """
    labels = labels or THEMES
    out = {}
    for lab in labels:
        a = b = c = d = 0
        for iid in set(model_tags) & set(human_tags):
            m = lab in model_tags[iid]
            h = lab in human_tags[iid]
            if m and h:
                a += 1
            elif m and not h:
                b += 1
            elif h and not m:
                c += 1
            else:
                d += 1
        n = a + b + c + d
        if not n:
            continue
        po = (a + d) / n
        pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
        kappa = (po - pe) / (1 - pe) if pe < 1 else None
        out[lab] = {
            "n": n, "both": a, "model_only": b, "human_only": c, "neither": d,
            "raw_agreement": round(po, 3),
            "kappa": (round(kappa, 3) if kappa is not None else None),
            "prevalence": round((a + c) / n, 3),
            "note": ("too rare for a stable kappa" if (a + c) < 5 else ""),
        }
    return out


def round_report(conn, store, round_id, items):
    """Compare one blind round against the model's tags."""
    rows = store.blind_round(conn, round_id)
    if not rows:
        return None
    by_item = {i["id"]: i for i in items}
    coders = sorted({r["coder"] for r in rows})

    human = defaultdict(dict)
    for r in rows:
        human[r["coder"]][r["item_id"]] = set(r["themes"])

    model = {iid: set((by_item[iid].get("analysis") or {}).get("topics") or [])
             for iid in {r["item_id"] for r in rows} if iid in by_item}

    out = {"round_id": round_id, "coders": coders, "n_items": len(model),
           "vs_model": {}, "inter_coder": None}
    for coder in coders:
        out["vs_model"][coder] = agreement(model, human[coder])
    if len(coders) >= 2:
        out["inter_coder"] = agreement(human[coders[0]], human[coders[1]])
    return out
