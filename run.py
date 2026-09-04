#!/usr/bin/env python3
"""Radical Party Watch — weekly monitoring portal.

  python run.py discover     probe party sites, fill in feeds
  python run.py probe        test the parliamentary adapters
  python run.py refresh      rebuild standing country primers (monthly)
  python run.py collect      gather the week
  python run.py analyze      triage, translate, extract quotes, classify evidence
  python run.py brief        write this week's national briefings
  python run.py interpret    write the analytical note on each carried item
  python run.py world        world briefing, highlights and the reading list
  python run.py archive      push sources to the Wayback Machine
  python run.py export       write coding rows for the week as CSV
  python run.py diff         re-fetch watched programme pages and diff them
  python run.py roster       check for radical parties missing from the roster
  python run.py code         local coding queue for the week (writes to the DB)
  python run.py site         rebuild the portal, corpus and report builder
  python run.py report       frozen report for a date range (see --from/--to)
  python run.py checklinks   re-check collected URLs for deletions and revisions
  python run.py backtrans    back-translation check on quotes you cannot verify
  python run.py reliability  blind coding round (--report <id> for agreement)
  python run.py weekly       the whole chain
  python run.py backfill     collect an exact historical range (see --from/--to)
  python run.py demo         offline sample portal, no keys needed
"""

import argparse
import copy
import json
import math
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import analyze as an          # noqa: E402
import archive as ar          # noqa: E402
import collect as co          # noqa: E402
import context as cx          # noqa: E402
import digest as dg           # noqa: E402
import diffs as df            # noqa: E402
import backtranslate as bt    # noqa: E402
import evidence as ev         # noqa: E402
import exports as ex          # noqa: E402
import hansard as hn          # noqa: E402
import health as hlth         # noqa: E402
import liveness as lv         # noqa: E402
import interpret as ip        # noqa: E402
import review as rv           # noqa: E402
import roster as ro           # noqa: E402
import portal as st_site      # noqa: E402
import reportbuilder as rb    # noqa: E402
import store as st            # noqa: E402
import trends as tr           # noqa: E402

CONFIG = os.environ.get("RW_CONFIG", "config/sources.yaml")
COUNTRIES = os.environ.get("RW_COUNTRIES", "config/countries.yaml")
SITE_DIR = os.environ.get("RW_SITE", "site")
DATA_DIR = os.environ.get("RW_EXPORTS", "exports")
BG_DIR = os.environ.get("RW_BACKGROUND", "background")
BG_MAX_AGE_DAYS = int(os.environ.get("RW_BG_MAX_AGE", "30"))
HISTORY_WEEKS = 12
OVERVIEW_SCOPE = "_overview"


def e_(t):
    import html as _h
    return _h.escape(str(t or ""))
DIFF_SCOPE = "_pagediffs"
WORLD_SCOPE = "_world"
RETRACT_SCOPE = "_retractions"
BACKTRANS_SCOPE = "_backtrans"
HIGHLIGHT_SCOPE = "_highlights"
READING_SCOPE = "_reading"
ROSTER_SCOPE = "_roster"


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_countries():
    try:
        with open(COUNTRIES, encoding="utf-8") as f:
            return yaml.safe_load(f)["countries"]
    except FileNotFoundError:
        return []


def country_names(countries):
    return {c["code"]: c["name"] for c in countries}


def current_week():
    y, w, _ = datetime.now(timezone.utc).isocalendar()
    return f"{y}-W{w:02d}"


def week_bounds(week):
    y, w = int(week[:4]), int(week.split("W")[1])
    monday = datetime.fromisocalendar(y, w, 1)
    return monday, monday + timedelta(days=6, hours=23, minutes=59)


def collection_bounds(args):
    """Return an exact historical window, or the ordinary rolling window.

    Historical ``until`` is exclusive internally so the user's ``--to`` day
    remains inclusive without time-of-day edge cases.
    """
    requested = bool(args.dfrom or args.dto)
    if requested and not (args.dfrom and args.dto):
        raise SystemExit("Historical collection needs both --from and --to (YYYY-MM-DD).")
    if not requested:
        return co.window_start(args.days), None, False
    try:
        since = datetime.strptime(args.dfrom, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        until = (datetime.strptime(args.dto, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                 + timedelta(days=1))
    except ValueError as exc:
        raise SystemExit("Dates must use YYYY-MM-DD, for example 2023-01-01.") from exc
    if until <= since:
        raise SystemExit("The To date must be the same as or later than the From date.")
    if until > datetime.now(timezone.utc) + timedelta(days=2):
        raise SystemExit("The historical collection date cannot be in the future.")
    return since, until, True


def selected_parties(cfg, args):
    """Resolve optional IDs/names and country codes used by a backfill run."""
    parties = list(cfg["parties"])
    countries = {str(x).strip().casefold() for x in (args.country or []) if str(x).strip()}
    if countries:
        parties = [p for p in parties if str(p.get("country", "")).casefold() in countries]
    selectors = [str(x).strip().casefold() for x in (args.party or []) if str(x).strip()]
    if selectors:
        def matched(p):
            names = {str(p.get(k, "")).strip().casefold() for k in ("id", "name", "short")}
            return any(s in names for s in selectors)
        parties = [p for p in parties if matched(p)]
    if (countries or selectors) and not parties:
        allowed = ", ".join(p["id"] for p in cfg["parties"])
        raise SystemExit(f"No parties matched. Valid party IDs are: {allowed}")
    return parties


def iso_week(value: str, fallback: str) -> str:
    dt = co._as_datetime(value)
    if not dt:
        return fallback
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _enrich(items, cfg, codes=None, extras=None):
    by_id = {p["id"]: p for p in cfg["parties"]}
    codes = codes or {}
    extras = extras or {}
    links = extras.get("links") or {}
    annos = extras.get("annotations") or {}
    btr = extras.get("backtrans") or {}
    metas = extras.get("meta") or {}
    for i in items:
        p = by_id.get(i["party_id"], {})
        i["party_name"] = p.get("short") or p.get("name") or i["party_id"]
        i["party_full"] = p.get("name", "")
        i["country"] = p.get("country", "")
        i["camp"] = p.get("camp", "right")
        i["rtl"] = bool(p.get("rtl"))
        c = codes.get((i["id"], 0))
        if c and c.get("category"):
            i["coded"] = c["category"]
        ls = links.get(i["id"])
        if ls:
            i["link_status"] = ls.get("status")
        if annos.get(i["id"]):
            i["annotation"] = annos[i["id"]]
        if btr.get(i["id"]):
            i["backtranslation"] = btr[i["id"]]
        m = metas.get(i["id"], {}).get("analyze")
        if m:
            i["meta_stamp"] = f"{m.get('model','')} · {m.get('prompt_ver','')}"
    return items


# ------------------------------------------------------------- commands

def cmd_discover(cfg, args):
    changed = 0
    for p in cfg["parties"]:
        res = co.discover_feeds(p.get("site"))
        print(f"[{'ok  ' if res['reachable'] else 'DOWN'}] {p['short']:<14} {p.get('site') or '-'}")
        print(f"         {', '.join(res['feeds']) or '(no feed found)'}")
        if res["error"]:
            print(f"         error: {res['error']}")
        if res["feeds"] and not p.get("feeds"):
            p["feeds"] = res["feeds"]
            changed += 1
    if changed and not args.dry_run:
        with open(CONFIG, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
        print(f"\nWrote {changed} feed set(s) back to {CONFIG}")


def cmd_probe(cfg, args):
    """The parliamentary adapters were written without network access. This is
    how you find out which of them work before relying on the output."""
    since = co.window_start(30)
    configured = 0
    for p in cfg["parties"]:
        spec = p.get("parliament")
        if not spec:
            continue
        configured += 1
        items, err = hn.collect(p, since)
        status = "ok  " if items else ("ERR " if err else "none")
        print(f"[{status}] {p['short']:<14} {spec.get('adapter','?'):<18} {len(items)} items / 30d")
        if err:
            print(f"         {err}")
        elif items:
            print(f"         e.g. {items[0]['title'][:80]}")
    if not configured:
        print("No parties have a `parliament:` block configured.")


def cmd_collect(cfg, args):
    conn = st.connect()
    removed_demo = st.remove_demo_data(conn)
    if removed_demo:
        print(f"Removed {removed_demo} demonstration items before live collection.")
        for path in ("exports/2026-W35.csv", "exports/2026-W36.csv"):
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
    since, until, historical = collection_bounds(args)
    week = args.week or (iso_week(since.isoformat(), current_week()) if historical
                         else current_week())
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    new = total = 0

    def run_channel(p, name, fn):
        """Every attempt is logged, successful or not. Success-only records
        cannot tell a party that went quiet from a feed that died."""
        try:
            got = fn() or []
            st.log_collection(conn, week, p["id"], name, True, len(got))
            return got
        except Exception as ex:
            st.log_collection(conn, week, p["id"], name, False, 0, str(ex))
            return []

    for p in selected_parties(cfg, args):
        items = []
        if p.get("feeds"):
            for feed in p["feeds"]:
                items += run_channel(
                    p, "site_feed",
                    lambda f=feed: co.from_feed(p, f, since, until),
                )
        if historical and p.get("site"):
            items += run_channel(
                p, "party_archive",
                lambda: co.from_sitemaps(p, since, until),
            )
        elif not p.get("feeds") and p.get("site"):
            items += run_channel(p, "site_scrape", lambda: co.from_site_scrape(p, since))
        items += run_channel(
            p, "press",
            lambda: co.from_google_news(p, since, days=args.days, until=until),
        )
        if p.get("telegram"):
            items += run_channel(
                p, "telegram", lambda: co.from_telegram(p, since, until),
            )
        if p.get("youtube_channel"):
            items += run_channel(
                p, "youtube", lambda: co.from_youtube(p, since, yt_key, until),
            )
        parl, perr = [], None
        if p.get("parliament"):
            try:
                parl, perr = hn.collect(p, since)
                st.log_collection(conn, week, p["id"], "parliament", not perr,
                                  len(parl), perr)
            except Exception as ex:
                st.log_collection(conn, week, p["id"], "parliament", False, 0, str(ex))
        items += parl

        fetched_here = len(items)
        unique = {}
        for item in items:
            key = st.item_id(p["id"], item.get("url"), item.get("title"))
            unique.setdefault(key, item)
        items = sorted(unique.values(), key=lambda item: item.get("published") or "",
                       reverse=True)
        if args.max_items_per_party and args.max_items_per_party > 0:
            items = items[:args.max_items_per_party]
        total += fetched_here

        kept = 0
        for it in items:
            if historical and not co._within(it.get("published"), since, until):
                continue
            iid = st.item_id(p["id"], it.get("url"), it.get("title"))
            if st.seen(conn, iid):
                continue
            item_week = iso_week(it.get("published"), week) if historical else week
            it["id"] = iid
            it["week"] = item_week
            it["snapshot_path"] = st.write_snapshot(item_week, iid, it.get("body"))
            st.save(conn, it)
            new += 1
            kept += 1
        flag = f"  [parl {len(parl)}]" if parl else ("  [parl err]" if perr else "")
        selected = f"; newest {len(items)} processed" if len(items) < fetched_here else ""
        print(f"{p['short']:<14} {kept:>3} new / {fetched_here:>3} fetched"
              f"{selected}{flag}")

    if historical:
        label = f"{args.dfrom} to {args.dto}"
    else:
        label = week
    print(f"\n{new} new items ({total} fetched) for {label}")


def _weeks_in_window(since, until):
    labels, seen = [], set()
    cursor = since
    while cursor < until:
        label = iso_week(cursor.isoformat(), current_week())
        if label not in seen:
            labels.append(label)
            seen.add(label)
        cursor += timedelta(days=7)
    last = iso_week((until - timedelta(seconds=1)).isoformat(), current_week())
    if last not in seen:
        labels.append(last)
    return labels


def cmd_backfill(cfg, args):
    """Collect an exact past range in bounded chunks, then rebuild the corpus."""
    since, until, historical = collection_bounds(args)
    if not historical:
        raise SystemExit("Backfill needs --from and --to.")
    parties = selected_parties(cfg, args)
    days = (until - since).days
    chunks = math.ceil(days / 31)
    work_units = len(parties) * chunks
    if work_units > 156:
        per_run = max(1, 156 // len(parties)) * 31
        raise SystemExit(
            f"This request is too large for one safe GitHub job ({len(parties)} parties × "
            f"{chunks} date chunks). Use at most about {per_run} days with this party "
            "selection, or select fewer party IDs. Existing data is preserved between runs."
        )

    print(f"Historical collection: {args.dfrom} to {args.dto}; "
          f"{len(parties)} parties; {chunks} chunk(s).")
    cursor = since
    while cursor < until:
        stop = min(cursor + timedelta(days=31), until)
        chunk_args = copy.copy(args)
        chunk_args.dfrom = cursor.date().isoformat()
        chunk_args.dto = (stop - timedelta(seconds=1)).date().isoformat()
        chunk_args.days = (stop - cursor).days
        chunk_args.week = None
        print(f"\n=== Collecting {chunk_args.dfrom} to {chunk_args.dto} ===")
        cmd_collect(cfg, chunk_args)
        cursor = stop

    conn = st.connect()
    for week in _weeks_in_window(since, until):
        if not st.week_items(conn, week):
            continue
        step_args = copy.copy(args)
        step_args.week = week
        print(f"\n=== Analysing {week} ===")
        cmd_analyze(cfg, step_args)
        if args.with_interpretation:
            cmd_interpret(cfg, step_args)
        cmd_export(cfg, step_args)
    cmd_site(cfg, args)
    print("\nHistorical collection complete. The database and report corpus are ready to publish.")


def cmd_analyze(cfg, args):
    conn = st.connect()
    week = args.week or current_week()
    by_id = {p["id"]: p for p in cfg["parties"]}
    pending = st.unanalyzed(conn, week)
    print(f"Analyzing {len(pending)} items...")
    for i, it in enumerate(pending, 1):
        party = by_id.get(it["party_id"])
        if not party:
            continue
        a = an.analyze_item(it, party)
        st.set_analysis(conn, it["id"], a)
        st.set_meta(conn, it["id"], "analyze", an.MODEL, an.PROMPT_VERSION)
        if a.get("relations"):
            st.set_relations(conn, it["id"], a["relations"])
        pc = ev.classify(it, a)
        st.set_evidence(conn, it["id"], pc, ev.rank(pc), None)
        if i % 25 == 0:
            print(f"  {i}/{len(pending)}")

    # Cluster wire copy after analysis, per party. A syndicated story is one
    # event, not six; counting it six times corrupts every frequency series.
    items = st.week_items(conn, week)
    by_party = {}
    for it in items:
        by_party.setdefault(it["party_id"], []).append(it)
    merged = 0
    for pid, group in by_party.items():
        assignment, clusters = ev.cluster(group)
        lookup = {x["id"]: x for x in group}
        for iid, ci in assignment.items():
            src = lookup[iid]
            st.set_evidence(conn, iid, src.get("provenance"),
                            src.get("provenance_rank"), f"{pid}-{ci}")
        merged += sum(1 for c in clusters if len(c) > 1)
    print(f"Done. {merged} duplicate cluster(s) collapsed.")


def cmd_brief(cfg, args):
    conn = st.connect()
    week = args.week or current_week()
    countries = load_countries()
    items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg)
    since = co.window_start(args.days)

    for c in countries:
        code = c["code"]
        if st.get_briefing(conn, week, code) and not args.force:
            print(f"{code}  briefing exists, skipping")
            continue
        background, _ = st.get_background(conn, code)
        if not background:
            fp = os.path.join(BG_DIR, f"{code}.md")
            if os.path.exists(fp):
                background = open(fp, encoding="utf-8").read()
        news = cx.fetch_country_news(c, since, days=args.days)
        here = [i for i in items if i["country"] == code]
        print(f"{code}  {len(news)} national items, {len(here)} party items")
        st.set_briefing(conn, week, code, cx.country_brief(c, background, news, here))

    overview = an.weekly_overview(items) if items else "Nothing collected this week."
    st.set_briefing(conn, week, OVERVIEW_SCOPE, overview)
    print("Briefings done.")


def cmd_interpret(cfg, args):
    """One analytical note per carried item. Runs after `brief`, because the
    national context is an input to it."""
    conn = st.connect()
    week = args.week or current_week()
    by_id = {p["id"]: p for p in cfg["parties"]}
    frameworks = ip.load_frameworks()
    briefs = st.all_briefings(conn, week)
    week_items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg)
    pending = [i for i in _enrich(st.uninterpreted(conn, week), cfg)]

    print(f"Interpreting {len(pending)} items against "
          f"{len(frameworks)} framework(s)...")
    counts = {}
    for n, it in enumerate(pending, 1):
        party = by_id.get(it["party_id"])
        if not party:
            continue
        note = ip.interpret_item(conn, it, party, week_items,
                                 briefs.get(it.get("country")), frameworks, st, tr)
        st.set_interpretation(conn, it["id"], note)
        st.set_meta(conn, it["id"], "interpret", an.MODEL, ip.PROMPT_VERSION)
        counts[note.get("significance", "routine")] = \
            counts.get(note.get("significance", "routine"), 0) + 1
        if n % 20 == 0:
            print(f"  {n}/{len(pending)}")
    print("Done. " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))


def cmd_world(cfg, args):
    """The layers that sit outside any single party: what happened globally,
    the highlight list, and what is worth reading. Runs after `interpret`
    because highlights use the significance grades."""
    conn = st.connect()
    week = args.week or current_week()
    start, end = week_bounds(week)
    rng = f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
    items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg)

    print("Writing the world briefing...")
    st.set_briefing(conn, week, WORLD_SCOPE, dg.world_briefing(rng, items))

    print("Selecting highlights...")
    hl = dg.highlights(items)
    st.set_briefing(conn, week, HIGHLIGHT_SCOPE, json.dumps(hl, ensure_ascii=False))
    print(f"  {len(hl)} highlight(s)")

    print("Gathering the reading list...")
    rcfg = dg.load_reading_config()
    since = co.window_start(args.days)
    cands = dg.fetch_reading_feeds(rcfg, since) + dg.search_reading(rcfg, days=args.days)
    print(f"  {len(cands)} candidates, curating...")
    reading = dg.curate(cands)
    st.set_briefing(conn, week, READING_SCOPE, json.dumps(reading, ensure_ascii=False))
    print(f"  {len(reading)} kept")


def cmd_archive(cfg, args):
    conn = st.connect()
    week = args.week or current_week()
    items = [i for i in st.week_items(conn, week, analyzed_only=True)
             if (i.get("analysis") or {}).get("relevant")
             and i.get("url") and not i.get("archive_url")]
    print(f"Archiving {len(items)} source URLs (slow by design)...")
    results = ar.archive_all([i["url"] for i in items])
    ok = 0
    for i in items:
        u = results.get(i["url"])
        if u:
            st.set_archive(conn, i["id"], u)
            ok += 1
    print(f"{ok}/{len(items)} archived.")


def _cluster_sizes(items):
    sizes = {}
    for it in items:
        cid = it.get("cluster_id")
        sizes[cid] = sizes.get(cid, 0) + 1
    return sizes


def cmd_export(cfg, args):
    conn = st.connect()
    week = args.week or current_week()
    items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg)
    path = ex.write_csv(ex.rows_for(items, _cluster_sizes(items)),
                        os.path.join(DATA_DIR, f"{week}.csv"))
    print(f"{len(ex.rows_for(items, _cluster_sizes(items)))} rows -> {path}")
    return path


def _absences(conn, cfg, countries, week):
    start, end = week_bounds(week)
    items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg)
    out = []
    for c in countries:
        parties = [p for p in cfg["parties"] if p.get("country") == c["code"]]
        here = [i for i in items if i["country"] == c["code"]]
        for rep in tr.absence_report(here, c, parties, start, end):
            out.append({**rep, "country": c["code"]})
    return out


GROUPERS = {
    "country": lambda i: [i.get("country") or "—"],
    "party":   lambda i: [i.get("party_name") or "—"],
    "actor":   lambda i: (i.get("analysis") or {}).get("actors") or ["(no named actor)"],
    "theme":   lambda i: (i.get("analysis") or {}).get("topics") or ["(no theme tagged)"],
    "camp":    lambda i: ["Radical left" if i.get("camp") == "left" else "Far right"],
    "source":  lambda i: [i.get("provenance") or "—"],
    "month":   lambda i: [(i.get("published") or "")[:7] or "—"],
    "none":    lambda i: ["All"],
}


def _snapshot_reader(path):
    try:
        return open(path, encoding="utf-8").read() if path else ""
    except Exception:
        return ""


def cmd_checklinks(cfg, args):
    """Re-fetch collected URLs. A statement that has been pulled is a political
    act, and the snapshot means you still have what it said."""
    conn = st.connect()
    codes = st.get_codes(conn)
    items = []
    for wk in st.all_weeks(conn):
        items += _enrich(st.week_items(conn, wk, analyzed_only=True), cfg, codes)
    items = [i for i in items
             if (i.get("analysis") or {}).get("relevant") and i.get("url")]
    items.sort(key=lambda x: x.get("published") or "", reverse=True)
    items = items[:args.limit]
    print(f"Re-checking {len(items)} source pages (slow by design)...")
    results, flagged = lv.sweep(conn, st, items, _snapshot_reader)
    st.set_briefing(conn, args.week or current_week(), RETRACT_SCOPE,
                    json.dumps(flagged, ensure_ascii=False))
    print("  " + ", ".join(f"{v} {k}" for k, v in results.items()))
    if flagged:
        print(f"\n{len(flagged)} page(s) gone or materially changed — see the issue.")


def cmd_backtrans(cfg, args):
    """Round-trip the quotes in languages you cannot check yourself."""
    conn = st.connect()
    week = args.week or current_week()
    skip = bt.load_config()
    items = [i for i in _enrich(st.week_items(conn, week, analyzed_only=True), cfg)
             if (i.get("analysis") or {}).get("quotes")]
    print(f"Checking quotes in {len(items)} item(s); skipping {sorted(skip)}...")
    out, flagged = {}, 0
    for it in items:
        res = bt.check_item(it, skip)
        if not res:
            continue
        out[it["id"]] = res
        flagged += sum(1 for r in res if r["flagged"])
        st.set_meta(conn, it["id"], "backtranslate", an.MODEL, bt.PROMPT_VERSION)
    st.set_briefing(conn, week, BACKTRANS_SCOPE, json.dumps(out, ensure_ascii=False))
    print(f"{sum(len(v) for v in out.values())} quote(s) checked, {flagged} flagged.")


def cmd_reliability(cfg, args):
    """Blind round, or the agreement report for a finished one."""
    conn = st.connect()
    if args.report_round:
        items = []
        for wk in st.all_weeks(conn):
            items += _enrich(st.week_items(conn, wk, analyzed_only=True), cfg)
        rep = hlth.round_report(conn, st, args.report_round, items)
        if not rep:
            print(f"No coding recorded for round {args.report_round}.")
            return
        print(f"Round {rep['round_id']} — {rep['n_items']} items, "
              f"coders: {', '.join(rep['coders'])}\n")
        for coder, res in rep["vs_model"].items():
            print(f"{coder} vs model:")
            for lab, v in res.items():
                k = "—" if v["kappa"] is None else f"{v['kappa']:.2f}"
                print(f"  {lab:<20} agreement {v['raw_agreement']:.0%}  kappa {k}"
                      f"  prevalence {v['prevalence']:.0%}  {v['note']}")
        if rep.get("inter_coder"):
            print("\nbetween coders:")
            for lab, v in rep["inter_coder"].items():
                k = "—" if v["kappa"] is None else f"{v['kappa']:.2f}"
                print(f"  {lab:<20} agreement {v['raw_agreement']:.0%}  kappa {k}")
        return

    round_id = args.round_id or datetime.now(timezone.utc).strftime("%Y-%m")
    items = []
    for wk in st.all_weeks(conn):
        items += _enrich(st.week_items(conn, wk, analyzed_only=True), cfg)
    sample = hlth.sample_for_round(items, n=args.n, seed=round_id)
    if not sample:
        print("Nothing to sample yet.")
        return
    coder = os.environ.get("RW_CODER", "NB")
    try:
        import yaml as _y
        coder = _y.safe_load(open("config/coding.yaml", encoding="utf-8")).get("coder", coder)
    except Exception:
        pass
    rv.serve_blind(conn, st, sample, round_id, coder, port=args.port + 1)


def cmd_report(cfg, args):
    """A frozen report for a date range, written to disk.

    The browser builder regenerates on every visit, which is what you want
    while working. This is for the other case: a report you cite, circulate or
    keep, which has to still say the same thing when someone opens it later.
    """
    if not (args.dfrom and args.dto):
        print("Need --from and --to, e.g. --from 2026-06-01 --to 2026-08-31")
        return
    conn = st.connect()
    codes = st.get_codes(conn)
    items = []
    for wk in st.all_weeks(conn):
        items += _enrich(st.week_items(conn, wk, analyzed_only=True), cfg, codes)

    def keep(i):
        a = i.get("analysis") or {}
        d = (i.get("published") or "")[:10]
        if not a.get("relevant") or not d or d < args.dfrom or d > args.dto:
            return False
        if args.country and i.get("country") not in args.country:
            return False
        if args.party and not ({i.get("party_id"), i.get("party_name")} & set(args.party)):
            return False
        if args.actor and not (set(a.get("actors") or []) & set(args.actor)):
            return False
        if args.theme and not (set(a.get("topics") or []) & set(args.theme)):
            return False
        if args.camp and i.get("camp") != args.camp:
            return False
        return True

    rows = sorted((i for i in items if keep(i)), key=lambda x: x.get("published") or "")
    if not rows:
        print("No items match. Widen the range or drop a filter.")
        return

    groups = {}
    for i in rows:
        for k in GROUPERS[args.groupby](i):
            groups.setdefault(k, []).append(i)
    order = sorted(groups, key=lambda k: (-len(groups[k]), k))

    filters = [f"{k}: {', '.join(v)}" for k, v in
               [("countries", args.country), ("parties", args.party),
                ("actors", args.actor), ("themes", args.theme),
                ("camp", [args.camp] if args.camp else [])] if v]
    top = max(len(g) for g in groups.values())
    body = [f'<h1>Report</h1>',
            f'<p class="meta">{e_(args.dfrom)} to {e_(args.dto)} · grouped by '
            f'{e_(args.groupby)} · generated '
            f'{datetime.now(timezone.utc).date().isoformat()}'
            + (f' · {e_("; ".join(filters))}' if filters else '') + '</p>',
            '<div class="statline">'
            f'<div class="stat"><div class="v">{len(rows)}</div><div class="k">items</div></div>'
            f'<div class="stat"><div class="v">{len({i["party_id"] for i in rows})}</div>'
            f'<div class="k">parties</div></div>'
            f'<div class="stat"><div class="v">{len({i["country"] for i in rows})}</div>'
            f'<div class="k">countries</div></div>'
            f'<div class="stat"><div class="v">'
            f'{sum(1 for i in rows if (i.get("analysis") or {}).get("quotes"))}</div>'
            f'<div class="k">with a quote</div></div></div>',
            '<div class="box"><h4>Distribution</h4>']
    for k in order:
        n = len(groups[k])
        body.append(f'<div class="distrow"><span>{e_(k)}</span>'
                    f'<span class="track"><i style="width:{100*n/top:.1f}%"></i></span>'
                    f'<span class="n">{n}</span></div>')
    body.append('</div>')
    for k in order:
        body.append(f'<h3>{e_(k)} <span class="meta">{len(groups[k])} items</span></h3>')
        for i in groups[k]:
            body.append(st_site.item_html(i))

    os.makedirs("reports", exist_ok=True)
    stem = f"reports/report_{args.dfrom}_{args.dto}_{args.groupby}"
    with open(stem + ".html", "w", encoding="utf-8") as f:
        f.write(st_site.layout("Report", "".join(body), subtitle="frozen report")
                .replace('href="assets/style.css"',
                         'href="../site/assets/style.css"'))
    ex.write_csv(ex.rows_for(rows, _cluster_sizes(rows)), stem + ".csv")
    print(f"{len(rows)} items across {len(groups)} group(s)")
    print(f"  {stem}.html\n  {stem}.csv")


def cmd_site(cfg, args):
    conn = st.connect()
    countries = load_countries()
    names = country_names(countries)
    # These directories are generated views of the database.  Recreate them
    # so removed demo records (or corrected records) cannot leave stale pages.
    for generated in ("issues", "data", "corpus", "speakers", "parties"):
        shutil.rmtree(os.path.join(SITE_DIR, generated), ignore_errors=True)
    st_site.write_assets(SITE_DIR)

    weeks = st.all_weeks(conn)
    codes = st.get_codes(conn)
    baselines = {}
    reference = None
    try:
        with open("config/baselines.yaml", encoding="utf-8") as f:
            b = yaml.safe_load(f)
            baselines, reference = b.get("baselines") or {}, b.get("reference")
    except Exception:
        pass
    all_ids = [r[0] for r in conn.execute("SELECT DISTINCT item_id FROM analysis_meta")]
    extras = {"links": st.latest_link_status(conn),
              "annotations": st.get_annotations(conn),
              "meta": {iid: st.meta_for(conn, iid) for iid in all_ids}}
    index = []
    for week in weeks:
        wk_extras = dict(extras)
        try:
            wk_extras["backtrans"] = json.loads(
                st.get_briefing(conn, week, BACKTRANS_SCOPE) or "{}")
        except Exception:
            wk_extras["backtrans"] = {}
        items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg, codes, wk_extras)
        if not items:
            continue
        briefs = st.all_briefings(conn, week)
        overview = briefs.pop(OVERVIEW_SCOPE, "")
        world = briefs.pop(WORLD_SCOPE, "")
        briefs.pop(BACKTRANS_SCOPE, None)
        try:
            retractions = json.loads(briefs.pop(RETRACT_SCOPE, "[]"))
        except Exception:
            retractions = []
        try:
            page_changes = json.loads(briefs.pop(DIFF_SCOPE, "[]"))
        except Exception:
            page_changes = []
        try:
            hl = json.loads(briefs.pop(HIGHLIGHT_SCOPE, "[]"))
        except Exception:
            hl = []
        try:
            reading = json.loads(briefs.pop(READING_SCOPE, "[]"))
        except Exception:
            reading = []
        conv = tr.convergence(conn, cfg["parties"], week, st)
        sizes = _cluster_sizes(items)

        shifts_by_party = {}
        hist = tr.iso_weeks_back(week, HISTORY_WEEKS)
        for p in cfg["parties"]:
            s = tr.shifts(tr.theme_series(conn, p["id"], hist))
            if s:
                shifts_by_party[p.get("short") or p["id"]] = s

        csv_path = os.path.join(DATA_DIR, f"{week}.csv")
        if not os.path.exists(csv_path):
            ex.write_csv(ex.rows_for(items, sizes), csv_path)
        st_site.copy_export(csv_path, week, SITE_DIR)

        st_site.issue_page(week, items, overview, briefs, names, cfg["parties"],
                           _absences(conn, cfg, countries, week),
                           shifts_by_party, sizes, SITE_DIR,
                           all_items=_enrich(st.week_items(conn, week), cfg),
                           convergence=conv, page_changes=page_changes,
                           editors_cut=ip.editors_cut(items),
                           world=world, highlights=hl, reading=reading,
                           week_range=f"{week_bounds(week)[0].strftime('%d %b')} – "
                                      f"{week_bounds(week)[1].strftime('%d %b %Y')}",
                           retractions=retractions, baselines=baselines,
                           reference=reference)

        relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
        start, end = week_bounds(week)
        index.append({
            "week": week,
            "range": f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}",
            "headline": (overview or "").split(". ")[0][:180],
            "items": len(relevant),
            "parties": len({i["party_id"] for i in relevant}),
        })
        print(f"issue {week}: {len(relevant)} items")

    newest = weeks[0] if weeks else current_week()
    totals = {}
    for p in cfg["parties"]:
        pitems = _enrich(st.party_items(conn, p["id"]), cfg)
        rel = [i for i in pitems if (i.get("analysis") or {}).get("relevant")]
        totals[p["id"]] = len(rel)
        series = tr.theme_series(conn, p["id"], tr.iso_weeks_back(newest, HISTORY_WEEKS))
        st_site.party_page(p, series, rel, SITE_DIR)

    # Speakers: disaggregate what the party pages aggregate.
    spk = tr.speaker_index(conn, cfg["parties"], st)
    all_by_id = {}
    for wk in weeks:
        for it in _enrich(st.week_items(conn, wk, analyzed_only=True), cfg):
            all_by_id[it["id"]] = it
    for key, rec in spk.items():
        st_site.speaker_page(key, rec,
                             [all_by_id[i] for i in rec["items"] if i in all_by_id],
                             SITE_DIR)
    st_site.speakers_page(spk, SITE_DIR)

    try:
        cand = json.loads(st.get_background(conn, ROSTER_SCOPE)[0] or "[]")
    except Exception:
        cand = []
    st_site.roster_page(cand, SITE_DIR)

    # Corpus for the in-browser report builder.
    all_relevant = []
    for wk in weeks:
        all_relevant += _enrich(st.week_items(conn, wk, analyzed_only=True), cfg, codes)
    yrs = st_site.corpus_json(all_relevant, SITE_DIR)
    rb.report_page(SITE_DIR, len(cfg["parties"]),
                   len({p.get("country") for p in cfg["parties"]}))
    print(f"corpus: {sum(1 for i in all_relevant if (i.get('analysis') or {}).get('relevant'))} "
          f"items across {len(yrs)} year shard(s)")

    # Health, network and reliability: what the system knows about itself.
    history = st.collection_history(conn, weeks=16)
    hrows, hweeks = hlth.health_table(history, cfg["parties"])
    silent = hlth.silent_parties(history, cfg["parties"])
    link_status = st.latest_link_status(conn)
    link_summary = {}
    for v in link_status.values():
        link_summary[v["status"]] = link_summary.get(v["status"], 0) + 1
    st_site.health_page(hrows, hweeks, silent, st.prompt_versions(conn),
                        link_summary, SITE_DIR)
    st_site.network_page(st.all_relations(conn), cfg["parties"], SITE_DIR)

    all_items_flat = []
    for wk in weeks:
        all_items_flat += _enrich(st.week_items(conn, wk, analyzed_only=True), cfg, codes)
    reports = [r for r in (hlth.round_report(conn, st, rid, all_items_flat)
                           for rid in st.blind_rounds(conn)) if r]
    st_site.reliability_page(reports, SITE_DIR)

    st_site.archive_page(index, SITE_DIR)
    st_site.parties_page(cfg["parties"], totals, SITE_DIR)
    st_site.home_page(index[0] if index else None, index, SITE_DIR)
    st_site.write_index_json(index, SITE_DIR)
    print(f"\nPortal built: {len(index)} issue(s), {len(cfg['parties'])} party pages -> {SITE_DIR}/")


def cmd_diff(cfg, args):
    conn = st.connect()
    week = args.week or current_week()
    print("Checking watched programme pages...")
    changes = df.check(conn, cfg["parties"], st)
    st.set_briefing(conn, week, DIFF_SCOPE, json.dumps(changes, ensure_ascii=False))
    print(f"{len(changes)} page(s) changed.")


def cmd_roster(cfg, args):
    """Monthly. Proposes, never writes -- adding a party changes any dataset
    built on the roster."""
    conn = st.connect()
    countries = load_countries()
    found = []
    for c in countries:
        monitored = [p for p in cfg["parties"] if p.get("country") == c["code"]]
        print(f"{c['code']}  checking against {len(monitored)} monitored...")
        for cand in ro.check_country(c, monitored):
            cand["country"] = c["code"]
            found.append(cand)
            print(f"    + {cand.get('name')}  {cand.get('polling','')}")
    st.set_background(conn, ROSTER_SCOPE, json.dumps(found, ensure_ascii=False))
    if found:
        os.makedirs("roster", exist_ok=True)
        with open("roster/candidates.yaml", "w", encoding="utf-8") as f:
            f.write("# Proposed additions. Review, then paste into "
                    "config/sources.yaml if you accept them.\n\n")
            for cand in found:
                c = next(x for x in countries if x["code"] == cand["country"])
                f.write(ro.to_yaml_stub(cand, c) + "\n")
        print(f"\n{len(found)} candidate(s) -> roster/candidates.yaml")
    else:
        print("\nRoster is current.")


def cmd_code(cfg, args):
    conn = st.connect()
    week = args.week or current_week()
    items = _enrich(st.week_items(conn, week, analyzed_only=True), cfg)
    cats = rv.load_categories()
    coder = os.environ.get("RW_CODER", "coder")
    try:
        import yaml as _y
        coder = _y.safe_load(open("config/coding.yaml", encoding="utf-8")).get("coder", coder)
    except Exception:
        pass
    rv.serve(conn, st, items, cats, week, coder, port=args.port)


def cmd_refresh(cfg, args):
    conn = st.connect()
    countries = load_countries()
    os.makedirs(BG_DIR, exist_ok=True)
    for c in countries:
        scope = c["code"]
        age = st.background_age_days(conn, scope)
        if age is not None and age < BG_MAX_AGE_DAYS and not args.force:
            print(f"{scope}  fresh ({age}d old), skipping")
            continue
        parties = [p for p in cfg["parties"] if p.get("country") == scope]
        print(f"{scope}  refreshing background ({len(parties)} parties)...")
        text = cx.refresh_background(c, parties)
        st.set_background(conn, scope, text)
        with open(os.path.join(BG_DIR, f"{scope}.md"), "w", encoding="utf-8") as f:
            f.write(f"# {c['name']} — standing background\n\n"
                    f"*Refreshed {datetime.now(timezone.utc).date().isoformat()}.*\n\n{text}\n")


def cmd_demo(cfg, args):
    """Builds a portal from fixtures so the shape is visible without keys.

    Quotes here are attributed to placeholder speakers, not real politicians.
    Fixtures get committed and published like anything else, and an invented
    sentence in a named person's mouth is the one thing this system exists to
    make impossible."""
    conn = st.connect()
    fixtures = [
        ("d1", "afd", "party_site", "https://example.org/afd", "Landtag programme", "2026-09-01",
         {"relevant": True, "topics": ["immigration"], "confidence": "high", "actors": [],
          "summary": "The party published its state election programme.", "quotes": []}),
        ("d2", "wpb", "press", "https://example.org/wpb", "Broadcast interview", "2026-09-02",
         {"relevant": True, "topics": ["israel_palestine"], "confidence": "medium",
          "actors": ["George Galloway"], "quotes": [],
          "summary": "Galloway restated the party's call for a full arms embargo."}),
        ("d3", "rn", "parliament", "https://example.org/rn", "Séance publique", "2026-08-31",
         {"relevant": True, "topics": ["immigration"], "confidence": "high",
          "actors": ["Demo Speaker A"],
          "summary": "Floor speech arguing that le regroupement familial should be suspended.",
          "quotes": [{"original": "Le regroupement familial doit être suspendu.",
                      "translation": "Family reunification must be suspended.",
                      "speaker": "Demo Speaker A"}]}),
        ("d5", "lfi", "parliament", "https://example.org/lfi", "Séance publique", "2026-09-01",
         {"relevant": True, "topics": ["immigration"], "confidence": "high",
          "actors": ["Demo Speaker B"],
          "summary": "Floor speech opposing the suspension of le regroupement familial.",
          "quotes": [{"original": "Le regroupement familial n'est pas négociable.",
                      "translation": "Family reunification is not negotiable.",
                      "speaker": "Demo Speaker B"}]}),
        ("d6", "otzma", "party_site", "https://example.org/otzma", "הודעת מפלגה", "2026-09-01",
         {"relevant": True, "topics": ["jews_antisemitism"], "confidence": "high",
          "actors": ["Demo Speaker C"],
          "summary": "Party statement on the annual Kahane memorial and its legal status.",
          "quotes": [{"original": "הציבור לא ישכח.", "translation": "The public will not forget.",
                      "speaker": "Demo Speaker C"}]}),
        ("d7", "hadash", "parliament", "https://example.org/hadash", "ישיבת מליאה", "2026-09-02",
         {"relevant": True, "topics": [], "confidence": "high", "actors": ["Demo Speaker D"],
          "summary": "Floor speech opposing a bill on party registration criteria.",
          "quotes": []}),
        ("d4", "fonilogikis", "press", "https://example.org/fl", "Grammos and Vitsi commemoration", "2026-08-30",
         {"relevant": True, "topics": [], "confidence": "high", "actors": ["Αφροδίτη Λατινοπούλου"],
          "summary": "The only party to issue a formal announcement on the Grammos and Vitsi commemorations.",
          "quotes": []}),
    ]
    for iid, pid, stype, url, title, pub, a in fixtures:
        # Week is derived from the date so the occasions calendar lines up:
        # the Greek commemoration lands in W35, the rest in W36.
        y, w, _ = datetime.fromisoformat(pub).isocalendar()
        week = f"{y}-W{w:02d}"
        body = title + " " + a["summary"]
        it = {"id": iid, "party_id": pid, "source_type": stype, "url": url,
              "title": title, "published": pub, "week": week, "body": body,
              "snapshot_path": f"snapshots/{week}/{iid}.txt", "analysis": a,
              "outlet": "example.org", "cluster_id": f"{pid}-0"}
        pc = ev.classify(it, a)
        it["provenance"], it["provenance_rank"] = pc, ev.rank(pc)
        st.save(conn, it)
    DEMO_INTERP = {
        "d1": {"significance": "notable", "confidence": "medium",
               "reading": "A governing prospectus rather than a manifesto: published four days before a vote the party expects to win outright, it is written for the electorate that will produce a minister-president, not for a federal audience. The choice to lead on immigration and family policy rather than economics tells you which coalition of voters it thinks is decisive.",
               "why_now": "Four days before the Saxony-Anhalt vote, and three weeks before Berlin and Mecklenburg-Vorpommern. Publishing now sets the terms for all three.",
               "continuity": "escalation",
               "continuity_note": "The themes are the party's standing repertoire; what is new is stating them as an implementation programme rather than an opposition platform.",
               "comparison": "No other monitored party this week is writing as a prospective governing party.",
               "watch": "Whether the federal party adopts or distances itself from the state programme after Sunday.",
               "frameworks": ["Militant democracy pressure"],
               "caveat": "Read from a magazine's account, not the party's own document. Pull afd.de before citing any specific measure."},
        "d3": {"significance": "routine", "confidence": "high",
               "reading": "Standard restatement of a long-held position, made on the floor rather than in a broadcast, which puts it in the permanent record.",
               "why_now": "No particular trigger; the debate was scheduled.",
               "continuity": "consistent",
               "continuity_note": "Matches the party's line across the whole archive window.",
               "comparison": "The same formulation appears this week from the opposite camp arguing the reverse.",
               "watch": "Whether the phrasing migrates into coalition-negotiation language.",
               "frameworks": ["Horseshoe convergence"], "caveat": ""},
        "d5": {"significance": "notable", "confidence": "medium",
               "reading": "Contests the same ground in the same words as the far right, from the opposing side. The shared vocabulary is the point: both parties have accepted that this is the terrain the argument happens on.",
               "why_now": "Same sitting as the opposing speech; the two are in direct exchange.",
               "continuity": "consistent", "continuity_note": "Consistent with the party's standing position.",
               "comparison": "Direct mirror of the far-right intervention the same day.",
               "watch": "Whether the phrase appears in the party's own campaign material rather than only in rebuttal.",
               "frameworks": ["Horseshoe convergence"],
               "caveat": "Shared vocabulary is not shared position. The convergence here is in framing, not in substance."},
        "d2": {"significance": "routine", "confidence": "low",
               "reading": "Restatement of an established position in a broadcast setting.",
               "why_now": "No identifiable trigger.", "continuity": "consistent",
               "continuity_note": "Insufficient record on file to judge properly.",
               "comparison": "", "watch": "Whether it is repeated in a party document.",
               "frameworks": [], "caveat": "Reported at second hand; no verbatim quote captured."},
        "d4": {"significance": "unusual", "confidence": "high",
               "reading": "The party placed itself alone on commemorative ground that three direct competitors left vacant. Attending and issuing a formal announcement, when rivals on the same flank did neither, is a claim to be the authentic custodian of that memory.",
               "why_now": "The commemoration is fixed to the date; the choice was whether to show up.",
               "continuity": "consistent",
               "continuity_note": "Consistent in direction, but the exclusivity is new — in prior years this ground was contested.",
               "comparison": "Greek Solution, Niki and Spartiates issued nothing. The absence is the comparison.",
               "watch": "Whether rivals respond after the fact, which would indicate they judged the absence a mistake.",
               "frameworks": ["National-memory competition"],
               "caveat": "Absence of a formal announcement is not absence of activity; local-level attendance may not be captured."},
    }
    DEMO_INTERP["d6"] = {
        "significance": "notable", "confidence": "medium",
        "explanation": "The reference is to the annual memorial for Meir Kahane, assassinated in New York in November 1990. Kach, the party he founded, was barred from Knesset elections in 1988 under the anti-racism amendment to the Basic Law and outlawed in 1994. Otzma Yehudit's leadership emerged from that milieu, and the memorial's legal standing has been contested repeatedly since.",
        "reading": "Marking the anniversary keeps a lineage visible that the party's electoral position depends on obscuring. The statement is addressed inward, to a base for whom the continuity is the point, rather than outward.",
        "why_now": "Ahead of the November anniversary rather than on it, which allows the party to set terms before the annual argument about the event's legality begins.",
        "continuity": "consistent",
        "continuity_note": "Consistent with the party's standing handling of this anniversary.",
        "comparison": "No other monitored party in Israel engaged the anniversary this week.",
        "watch": "Whether the Attorney General's office responds, and whether coalition partners distance themselves.",
        "frameworks": ["National-memory competition", "Militant democracy pressure"],
        "caveat": "Demo fixture. Placeholder speaker, illustrative text."}
    DEMO_INTERP["d7"] = {
        "significance": "notable", "confidence": "medium",
        "explanation": "Party registration and disqualification in Israel run through the Central Elections Committee with Supreme Court review, under Basic Law: The Knesset, section 7A. The provision has been applied to both Kahanist lists and Arab parties, which is why proposals to change its criteria draw opposition from parties that would not otherwise align.",
        "reading": "Opposition here is a defence of the party's own eligibility as much as a position on the bill. The instrument being amended is one that has been pointed at this party before.",
        "why_now": "The bill's first reading.",
        "continuity": "consistent", "continuity_note": "Long-standing position.",
        "comparison": "The far-right parties monitored here have historically been on the other side of the same instrument.",
        "watch": "Whether Balad takes the same position, and whether any coalition party breaks ranks.",
        "frameworks": ["Militant democracy pressure"],
        "caveat": "Demo fixture."}
    for iid, note in DEMO_INTERP.items():
        st.set_interpretation(conn, iid, note)
    st.set_briefing(conn, "2026-W36", WORLD_SCOPE,
        "Demo fixture. In a real issue this is 150-350 words on the international "
        "developments of the week that bear on these parties — Israel and Palestine, "
        "migration events at European borders, EU-level rulings and funding fights, US "
        "policy where it reverberates in European party politics, and transnational "
        "organising on either flank. It is written with search and then narrowed against "
        "what the monitored parties actually did, so it explains the week these parties "
        "had rather than the week in general.")
    st.set_briefing(conn, "2026-W36", HIGHLIGHT_SCOPE, json.dumps([
        {"item_id": "d1", "line": "State election programme published four days before the vote.", "tag": "election week"},
        {"item_id": "d3", "line": "Floor speech restating the party's position on family reunification.", "tag": "parliamentary"},
        {"item_id": "d5", "line": "Opposing floor speech in the same sitting, using the same terms.", "tag": "direct exchange"},
        {"item_id": "d6", "line": "Statement on the Kahane memorial and its contested legal standing.", "tag": "commemoration"},
        {"item_id": "d7", "line": "Floor speech against a bill amending party registration criteria.", "tag": "eligibility law"},
        {"item_id": "d2", "line": "Arms embargo position restated in a broadcast interview.", "tag": "broadcast"},
    ], ensure_ascii=False))
    st.set_briefing(conn, "2026-W36", READING_SCOPE, json.dumps([
        {"title": "(Demo fixture — the real list is built from config/reading.yaml)",
         "url": "https://example.org", "source": "—", "kind": "analysis",
         "why": "Feeds from monitoring bodies, journals and think tanks, plus a search pass, curated down by relevance. Typically 20-40 entries."},
    ], ensure_ascii=False))
    st.set_briefing(conn, "2026-W36", "IL",
        "Demo fixture. In a real issue this is the Israeli national context for the week.")
    st.set_briefing(conn, "2026-W36", "FR",
                    "Demo fixture data — quotes are attributed to placeholder speakers.")
    st.set_code(conn, "d3", 0, "Israel-related, not antisemitic on its face (JDA 11–15)", "NB")
    st.set_briefing(conn, "2026-W36", DIFF_SCOPE, json.dumps([{
        "party_id": "sd", "party": "SD", "url": "https://www.sd.se/valplattform/",
        "since": "2026-08-24", "added_total": 2, "removed_total": 1, "similarity": 0.96,
        "added": ["Naturaliserade medborgare ska kunna förlora sitt svenska medborgarskap på grund av brottslighet."],
        "removed": ["Frivillig återvandring ska fortsatt uppmuntras."],
    }], ensure_ascii=False))
    st.set_briefing(conn, "2026-W36", OVERVIEW_SCOPE,
                    "A quiet week. Immigration dominated on the right while Israel-related "
                    "output was confined to the radical left.")
    st.set_briefing(conn, "2026-W36", "DE",
                    "The Bundestag was in recess and the Saxony-Anhalt campaign dominated.")
    st.set_briefing(conn, "2026-W35", OVERVIEW_SCOPE,
                    "One item of substance, in Greece, on commemorative rather than "
                    "electoral ground.")
    st.set_briefing(conn, "2026-W35", "GR",
                    "The week's one event with political weight was the 30 August "
                    "commemoration at Grammos and Vitsi, marking the closing battles of "
                    "the civil war.")
    # Seed the self-monitoring layers so they are visible offline.
    import random as _r
    _r.seed(7)
    for wk in ["2026-W33", "2026-W34", "2026-W35", "2026-W36"]:
        for p in cfg["parties"]:
            for ch in ["press", "site_feed"]:
                if p["id"] in ("dritteweg", "heimat", "nmr", "casapound") and ch == "site_feed":
                    ok, n = False, 0
                elif p["id"] == "vlaamsbelang" and ch == "site_feed" and wk >= "2026-W34":
                    ok, n = False, 0          # regressed: worked, then stopped
                else:
                    ok, n = True, _r.choice([0, 0, 1, 2, 3])
                st.log_collection(conn, wk, p["id"], ch, ok, n,
                                  "" if ok else "connection refused")
    st.set_relations(conn, "d1", [
        {"source": "AfD", "target": "FPÖ", "kind": "joint_appearance",
         "detail": "shared platform at a campaign event"},
        {"source": "AfD", "target": "Rassemblement National", "kind": "alliance",
         "detail": "European parliamentary group"}])
    st.set_relations(conn, "d5", [
        {"source": "La France Insoumise", "target": "Parti Communiste Français",
         "kind": "criticism", "detail": "public disagreement over coalition strategy"}])
    st.set_link_check(conn, "d2", "gone", 404, None, "page returns not found")
    st.set_briefing(conn, "2026-W36", RETRACT_SCOPE, json.dumps([
        {"id": "d2", "party": "WPB", "country": "GB", "date": "2026-09-02",
         "status": "gone", "url": "https://example.org/wpb",
         "archive_url": "https://web.archive.org/web/2026/https://example.org/wpb",
         "snapshot_path": "snapshots/2026-W36/d2.txt",
         "summary": "Galloway restated the party's call for a full arms embargo."},
        {"id": "d1", "party": "AfD", "country": "DE", "date": "2026-09-01",
         "status": "changed", "url": "https://example.org/afd", "similarity": 0.41,
         "archive_url": None, "snapshot_path": "snapshots/2026-W36/d1.txt",
         "summary": "The party published its state election programme."},
    ], ensure_ascii=False))
    st.set_link_check(conn, "d1", "changed", 200, 0.41, "content materially differs")
    st.set_annotation(conn, "d4",
                      "Check whether the 2024 and 2025 editions drew announcements "
                      "from Greek Solution — if so the exclusivity is genuinely new.")
    st.set_briefing(conn, "2026-W36", BACKTRANS_SCOPE, json.dumps({
        "d3": [{"quote_index": 0, "similarity": 0.18, "severity": "minor",
                "flagged": True,
                "round_trip": "Le regroupement familial devrait être suspendu.",
                "note": "The round trip weakens the modal from 'doit' (must) to "
                        "'devrait' (should), which softens an obligation into a "
                        "recommendation."}]}, ensure_ascii=False))
    for stage, ver in [("analyze", an.PROMPT_VERSION), ("interpret", ip.PROMPT_VERSION)]:
        for iid in ["d1", "d2", "d3", "d4", "d5", "d6", "d7"]:
            st.set_meta(conn, iid, stage, an.MODEL, ver)
    st.set_meta(conn, "d1", "analyze", an.MODEL, "analyze/2")
    for iid, themes in [("d1", ["immigration"]), ("d2", []), ("d3", ["immigration"]),
                        ("d4", []), ("d5", ["immigration"]), ("d6", ["jews_antisemitism"]),
                        ("d7", ["immigration"])]:
        st.set_blind_code(conn, iid, "2026-09", "NB", themes)

    cmd_site(cfg, args)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=[
        "discover", "probe", "collect", "analyze", "refresh", "brief",
        "archive", "export", "site", "diff", "roster", "code", "interpret",
        "world", "report", "checklinks", "backtrans", "reliability",
        "weekly", "backfill", "demo"])
    ap.add_argument("--round", dest="round_id")
    ap.add_argument("--report", dest="report_round")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--limit", type=int, default=250)
    ap.add_argument("--from", dest="dfrom", help="YYYY-MM-DD")
    ap.add_argument("--to", dest="dto", help="YYYY-MM-DD")
    ap.add_argument("--country", action="append", default=[])
    ap.add_argument("--party", action="append", default=[])
    ap.add_argument("--actor", action="append", default=[])
    ap.add_argument("--theme", action="append", default=[])
    ap.add_argument("--camp", choices=["left", "right"])
    ap.add_argument("--group-by", dest="groupby", default="country",
                    choices=["country", "party", "actor", "theme", "camp",
                             "source", "month", "none"])
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--week")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fast", action="store_true",
                    help="weekly core collection and analysis without slow enrichment/archiving")
    ap.add_argument("--max-items-per-party", type=int, default=0,
                    help="process at most this many newest fetched items per party (0 = unlimited)")
    ap.add_argument("--with-interpretation", action="store_true",
                    help="also create model interpretations during a historical backfill")
    args = ap.parse_args()
    cfg = load_config()

    if args.command == "weekly":
        cmd_collect(cfg, args)
        cmd_analyze(cfg, args)
        if not args.fast:
            cmd_diff(cfg, args)
            cmd_brief(cfg, args)
            cmd_interpret(cfg, args)
            cmd_world(cfg, args)
            cmd_archive(cfg, args)
        cmd_export(cfg, args)
        cmd_site(cfg, args)
    elif args.command == "backfill":
        cmd_backfill(cfg, args)
    else:
        {"discover": cmd_discover, "probe": cmd_probe, "collect": cmd_collect,
         "analyze": cmd_analyze, "refresh": cmd_refresh, "brief": cmd_brief,
         "archive": cmd_archive, "export": cmd_export, "site": cmd_site,
         "diff": cmd_diff, "roster": cmd_roster, "code": cmd_code,
         "interpret": cmd_interpret, "world": cmd_world, "report": cmd_report,
         "checklinks": cmd_checklinks, "backtrans": cmd_backtrans,
         "reliability": cmd_reliability,
         "demo": cmd_demo}[args.command](cfg, args)


if __name__ == "__main__":
    main()
