"""Item store: SQLite for dedup and state, plain files for source snapshots."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("RW_DB", "data/items.db")
SNAPSHOT_DIR = os.environ.get("RW_SNAPSHOTS", "snapshots")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id            TEXT PRIMARY KEY,
    party_id      TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    url           TEXT,
    title         TEXT,
    published     TEXT,
    collected_at  TEXT NOT NULL,
    lang          TEXT,
    body          TEXT,
    snapshot_path TEXT,
    archive_url   TEXT,
    analysis      TEXT,
    week          TEXT,
    provenance    TEXT,
    provenance_rank INTEGER,
    cluster_id    TEXT,
    outlet        TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_week  ON items(week);
CREATE INDEX IF NOT EXISTS idx_items_party ON items(party_id);

CREATE TABLE IF NOT EXISTS background (
    scope      TEXT PRIMARY KEY,
    text       TEXT,
    updated_at TEXT
);

-- Coding decisions live beside the items, not in a spreadsheet that drifts
-- out of sync with them.
-- What produced each analysis. Prompts change; items analysed before and
-- after a change are not comparable, and without this there is no way to tell
-- them apart afterwards. Impossible to reconstruct later, so it is recorded
-- at write time.
CREATE TABLE IF NOT EXISTS analysis_meta (
    item_id     TEXT NOT NULL,
    stage       TEXT NOT NULL,          -- triage | analyze | interpret | backtranslate
    model       TEXT,
    prompt_ver  TEXT,
    run_at      TEXT,
    PRIMARY KEY (item_id, stage)
);

-- Every collection attempt, successful or not. Success-only records cannot
-- distinguish a party that went quiet from a feed that died.
CREATE TABLE IF NOT EXISTS collection_log (
    week        TEXT NOT NULL,
    party_id    TEXT NOT NULL,
    channel     TEXT NOT NULL,
    ok          INTEGER NOT NULL,
    n_items     INTEGER DEFAULT 0,
    error       TEXT,
    run_at      TEXT,
    PRIMARY KEY (week, party_id, channel)
);

-- Re-checks of already-collected URLs. A statement that disappears is a
-- political act, and often a more informative one than the statement.
CREATE TABLE IF NOT EXISTS link_checks (
    item_id     TEXT NOT NULL,
    checked_at  TEXT NOT NULL,
    status      TEXT,                   -- ok | gone | changed | error
    http        INTEGER,
    similarity  REAL,
    detail      TEXT,
    PRIMARY KEY (item_id, checked_at)
);

-- Your own notes, stored beside the items rather than in a separate document
-- that drifts out of sync with them.
CREATE TABLE IF NOT EXISTS annotations (
    item_id     TEXT PRIMARY KEY,
    note        TEXT,
    updated_at  TEXT
);

-- Ties between parties named in items: joint appearances, endorsements,
-- delegations, shared platforms. Network data the system otherwise discards.
CREATE TABLE IF NOT EXISTS relations (
    item_id     TEXT NOT NULL,
    source      TEXT NOT NULL,
    target      TEXT NOT NULL,
    kind        TEXT,
    detail      TEXT,
    PRIMARY KEY (item_id, source, target, kind)
);

-- Blind double-coding for reliability. The model's tag is hidden while you
-- code; agreement is computed afterwards.
CREATE TABLE IF NOT EXISTS blind_codes (
    item_id     TEXT NOT NULL,
    round_id    TEXT NOT NULL,
    coder       TEXT NOT NULL,
    themes      TEXT,
    coded_at    TEXT,
    PRIMARY KEY (item_id, round_id, coder)
);

CREATE TABLE IF NOT EXISTS codes (
    item_id      TEXT NOT NULL,
    quote_index  INTEGER NOT NULL DEFAULT 0,
    category     TEXT,
    coder        TEXT,
    coded_date   TEXT,
    notes        TEXT,
    PRIMARY KEY (item_id, quote_index)
);

-- Successive captures of the same URL. Programme pages keep their address
-- while their content changes, so item-level dedup would never see the edit.
CREATE TABLE IF NOT EXISTS page_versions (
    party_id   TEXT NOT NULL,
    url        TEXT NOT NULL,
    captured   TEXT NOT NULL,
    sha        TEXT NOT NULL,
    text       TEXT,
    PRIMARY KEY (url, sha)
);
CREATE INDEX IF NOT EXISTS idx_pv_url ON page_versions(url, captured);

CREATE TABLE IF NOT EXISTS briefings (
    week    TEXT NOT NULL,
    scope   TEXT NOT NULL,
    text    TEXT,
    PRIMARY KEY (week, scope)
);
"""


def item_id(party_id, url, title):
    """Stable id. URL is the primary key when present; title is the fallback
    for sources (Telegram, some feeds) that don't expose a canonical link."""
    basis = (url or "").strip().lower() or f"{party_id}:{(title or '').strip().lower()}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


# Columns added after the first release; SQLite has no ADD COLUMN IF NOT
# EXISTS, so existing databases are migrated on connect.
LATE_COLUMNS = [
    ("provenance", "TEXT"), ("provenance_rank", "INTEGER"),
    ("cluster_id", "TEXT"), ("outlet", "TEXT"),
    # Model inference, kept in its own column so it can never be mistaken for
    # source material and never leaks into the coding export.
    ("interpretation", "TEXT"),
]


def connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(items)").fetchall()}
    for name, decl in LATE_COLUMNS:
        if name not in have:
            conn.execute(f"ALTER TABLE items ADD COLUMN {name} {decl}")
    conn.commit()
    return conn


def seen(conn, iid):
    return conn.execute("SELECT 1 FROM items WHERE id=?", (iid,)).fetchone() is not None


def remove_demo_data(conn):
    """Remove the bundled demonstration fixtures before the first live run.

    The exact IDs are intentionally fixed in ``run.py``.  Cleanup only happens
    while those fixtures still exist, so later real collection logs for the
    same calendar weeks are not repeatedly removed.
    """
    demo_ids = tuple(f"d{i}" for i in range(1, 8))
    placeholders = ",".join("?" for _ in demo_ids)
    found = conn.execute(
        f"SELECT COUNT(*) FROM items WHERE id IN ({placeholders})", demo_ids
    ).fetchone()[0]
    if not found:
        return 0
    for table, column in [
        ("analysis_meta", "item_id"), ("link_checks", "item_id"),
        ("annotations", "item_id"), ("relations", "item_id"),
        ("blind_codes", "item_id"), ("codes", "item_id"),
    ]:
        conn.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", demo_ids)
    conn.execute(f"DELETE FROM items WHERE id IN ({placeholders})", demo_ids)
    conn.execute("DELETE FROM briefings WHERE week IN ('2026-W35','2026-W36')")
    conn.execute("DELETE FROM collection_log WHERE week IN "
                 "('2026-W33','2026-W34','2026-W35','2026-W36')")
    conn.commit()
    return found


def write_snapshot(week, iid, body):
    """Keep the source text on disk. Party sites edit and delete; a quote in
    the newsletter is worthless six months on if nothing preserved it."""
    d = os.path.join(SNAPSHOT_DIR, week)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{iid}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body or "")
    return path


def save(conn, item):
    conn.execute(
        """INSERT OR REPLACE INTO items
           (id, party_id, source_type, url, title, published, collected_at,
            lang, body, snapshot_path, archive_url, analysis, week,
            provenance, provenance_rank, cluster_id, outlet)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            item["id"], item["party_id"], item["source_type"], item.get("url"),
            item.get("title"), item.get("published"),
            item.get("collected_at") or datetime.now(timezone.utc).isoformat(),
            item.get("lang"), item.get("body"), item.get("snapshot_path"),
            item.get("archive_url"),
            json.dumps(item["analysis"], ensure_ascii=False) if item.get("analysis") else None,
            item.get("week"), item.get("provenance"), item.get("provenance_rank"),
            item.get("cluster_id"), item.get("outlet"),
        ),
    )
    conn.commit()


def set_analysis(conn, iid, analysis):
    conn.execute(
        "UPDATE items SET analysis=? WHERE id=?",
        (json.dumps(analysis, ensure_ascii=False), iid),
    )
    conn.commit()


def set_evidence(conn, iid, provenance, rank, cluster_id):
    conn.execute(
        "UPDATE items SET provenance=?, provenance_rank=?, cluster_id=? WHERE id=?",
        (provenance, rank, cluster_id, iid),
    )
    conn.commit()


def party_bodies(conn, party_id, weeks):
    """Raw text for a party across given weeks — used for novel-term work."""
    if not weeks:
        return []
    qs = ",".join("?" * len(weeks))
    return [r[0] or "" for r in conn.execute(
        f"SELECT body FROM items WHERE party_id=? AND week IN ({qs})",
        (party_id, *weeks)).fetchall()]


def all_weeks(conn):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT week FROM items WHERE week IS NOT NULL ORDER BY week DESC"
    ).fetchall()]


def set_archive(conn, iid, archive_url):
    conn.execute("UPDATE items SET archive_url=? WHERE id=?", (archive_url, iid))
    conn.commit()


def week_items(conn, week, analyzed_only=False):
    q = "SELECT * FROM items WHERE week=?"
    if analyzed_only:
        q += " AND analysis IS NOT NULL"
    conn.row_factory = sqlite3.Row
    rows = conn.execute(q, (week,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["analysis"] = json.loads(d["analysis"]) if d["analysis"] else None
        d["interpretation"] = (json.loads(d["interpretation"])
                               if d.get("interpretation") else None)
        out.append(d)
    return out


def unanalyzed(conn, week):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM items WHERE week=? AND analysis IS NULL", (week,)
    ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------- background and briefings

def get_background(conn, scope):
    row = conn.execute(
        "SELECT text, updated_at FROM background WHERE scope=?", (scope,)
    ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def set_background(conn, scope, text):
    conn.execute(
        "INSERT OR REPLACE INTO background (scope, text, updated_at) VALUES (?,?,?)",
        (scope, text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def background_age_days(conn, scope):
    _, updated = get_background(conn, scope)
    if not updated:
        return None
    try:
        then = datetime.fromisoformat(updated)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - then).days


def get_briefing(conn, week, scope):
    row = conn.execute(
        "SELECT text FROM briefings WHERE week=? AND scope=?", (week, scope)
    ).fetchone()
    return row[0] if row else None


def set_briefing(conn, week, scope, text):
    conn.execute(
        "INSERT OR REPLACE INTO briefings (week, scope, text) VALUES (?,?,?)",
        (week, scope, text),
    )
    conn.commit()


def all_briefings(conn, week):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT scope, text FROM briefings WHERE week=?", (week,)).fetchall()}


def party_items(conn, party_id):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM items WHERE party_id=? AND analysis IS NOT NULL "
        "ORDER BY published DESC", (party_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["analysis"] = json.loads(d["analysis"]) if d["analysis"] else None
        d["interpretation"] = (json.loads(d["interpretation"])
                               if d.get("interpretation") else None)
        out.append(d)
    return out


# ------------------------------------------------------------------ codes

def set_code(conn, item_id, quote_index, category, coder, notes=""):
    conn.execute(
        "INSERT OR REPLACE INTO codes "
        "(item_id, quote_index, category, coder, coded_date, notes) VALUES (?,?,?,?,?,?)",
        (item_id, quote_index, category, coder,
         datetime.now(timezone.utc).date().isoformat(), notes),
    )
    conn.commit()


def get_codes(conn, item_ids=None):
    if item_ids:
        qs = ",".join("?" * len(item_ids))
        rows = conn.execute(
            f"SELECT item_id, quote_index, category, coder, coded_date, notes "
            f"FROM codes WHERE item_id IN ({qs})", tuple(item_ids)).fetchall()
    else:
        rows = conn.execute(
            "SELECT item_id, quote_index, category, coder, coded_date, notes "
            "FROM codes").fetchall()
    return {(r[0], r[1]): {"category": r[2], "coder": r[3],
                           "coded_date": r[4], "notes": r[5]} for r in rows}


# --------------------------------------------------------- page versions

def save_page_version(conn, party_id, url, text):
    """Returns (is_new, sha). Identical captures are not stored twice."""
    sha = hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]
    exists = conn.execute(
        "SELECT 1 FROM page_versions WHERE url=? AND sha=?", (url, sha)).fetchone()
    if exists:
        return False, sha
    conn.execute(
        "INSERT INTO page_versions (party_id, url, captured, sha, text) VALUES (?,?,?,?,?)",
        (party_id, url, datetime.now(timezone.utc).isoformat(), sha, text),
    )
    conn.commit()
    return True, sha


def page_history(conn, url, limit=2):
    rows = conn.execute(
        "SELECT captured, sha, text FROM page_versions WHERE url=? "
        "ORDER BY captured DESC LIMIT ?", (url, limit)).fetchall()
    return [{"captured": r[0], "sha": r[1], "text": r[2]} for r in rows]


def watched_urls(conn):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT url FROM page_versions").fetchall()]


# ---------------------------------------------------------- interpretation

def set_interpretation(conn, iid, data):
    conn.execute("UPDATE items SET interpretation=? WHERE id=?",
                 (json.dumps(data, ensure_ascii=False), iid))
    conn.commit()


def uninterpreted(conn, week):
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM items WHERE week=? AND analysis IS NOT NULL "
        "AND interpretation IS NULL", (week,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["analysis"] = json.loads(d["analysis"]) if d["analysis"] else None
        out.append(d)
    return [d for d in out if (d.get("analysis") or {}).get("relevant")]


# ------------------------------------------------------- analysis meta

def set_meta(conn, iid, stage, model, prompt_ver):
    conn.execute(
        "INSERT OR REPLACE INTO analysis_meta "
        "(item_id, stage, model, prompt_ver, run_at) VALUES (?,?,?,?,?)",
        (iid, stage, model, prompt_ver, datetime.now(timezone.utc).isoformat()))
    conn.commit()


def meta_for(conn, iid):
    return {r[0]: {"model": r[1], "prompt_ver": r[2], "run_at": r[3]}
            for r in conn.execute(
                "SELECT stage, model, prompt_ver, run_at FROM analysis_meta "
                "WHERE item_id=?", (iid,)).fetchall()}


def prompt_versions(conn):
    """Which prompt versions are represented in the corpus, and how much of it.
    A mixed corpus is not a fault; not knowing it is mixed is."""
    return [{"stage": r[0], "model": r[1], "prompt_ver": r[2], "n": r[3],
             "first": r[4], "last": r[5]}
            for r in conn.execute(
                "SELECT stage, model, prompt_ver, COUNT(*), MIN(run_at), MAX(run_at) "
                "FROM analysis_meta GROUP BY stage, model, prompt_ver "
                "ORDER BY stage, prompt_ver").fetchall()]


# ------------------------------------------------------ collection log

def log_collection(conn, week, party_id, channel, ok, n_items=0, error=None):
    conn.execute(
        "INSERT OR REPLACE INTO collection_log "
        "(week, party_id, channel, ok, n_items, error, run_at) VALUES (?,?,?,?,?,?,?)",
        (week, party_id, channel, 1 if ok else 0, n_items, (error or "")[:200],
         datetime.now(timezone.utc).isoformat()))
    conn.commit()


def collection_history(conn, weeks=12):
    return [{"week": r[0], "party_id": r[1], "channel": r[2], "ok": r[3],
             "n": r[4], "error": r[5]}
            for r in conn.execute(
                "SELECT week, party_id, channel, ok, n_items, error FROM collection_log "
                "WHERE week IN (SELECT DISTINCT week FROM collection_log "
                "ORDER BY week DESC LIMIT ?) ORDER BY week DESC", (weeks,)).fetchall()]


# --------------------------------------------------------- link checks

def set_link_check(conn, iid, status, http=None, similarity=None, detail=""):
    conn.execute(
        "INSERT OR REPLACE INTO link_checks "
        "(item_id, checked_at, status, http, similarity, detail) VALUES (?,?,?,?,?,?)",
        (iid, datetime.now(timezone.utc).isoformat(), status, http, similarity,
         (detail or "")[:300]))
    conn.commit()


def latest_link_status(conn):
    return {r[0]: {"status": r[1], "checked_at": r[2], "similarity": r[3],
                   "detail": r[4]}
            for r in conn.execute(
                "SELECT item_id, status, checked_at, similarity, detail FROM link_checks lc "
                "WHERE checked_at = (SELECT MAX(checked_at) FROM link_checks "
                "WHERE item_id = lc.item_id)").fetchall()}


# --------------------------------------------------------- annotations

def set_annotation(conn, iid, note):
    conn.execute(
        "INSERT OR REPLACE INTO annotations (item_id, note, updated_at) VALUES (?,?,?)",
        (iid, note, datetime.now(timezone.utc).isoformat()))
    conn.commit()


def get_annotations(conn):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT item_id, note FROM annotations WHERE note IS NOT NULL AND note != ''"
    ).fetchall()}


# ----------------------------------------------------------- relations

def set_relations(conn, iid, rels):
    conn.execute("DELETE FROM relations WHERE item_id=?", (iid,))
    for r in rels:
        conn.execute(
            "INSERT OR REPLACE INTO relations (item_id, source, target, kind, detail) "
            "VALUES (?,?,?,?,?)",
            (iid, r.get("source", ""), r.get("target", ""), r.get("kind", ""),
             (r.get("detail") or "")[:400]))
    conn.commit()


def all_relations(conn):
    return [{"item_id": r[0], "source": r[1], "target": r[2], "kind": r[3],
             "detail": r[4]}
            for r in conn.execute(
                "SELECT item_id, source, target, kind, detail FROM relations").fetchall()]


# --------------------------------------------------------- blind codes

def set_blind_code(conn, iid, round_id, coder, themes):
    conn.execute(
        "INSERT OR REPLACE INTO blind_codes (item_id, round_id, coder, themes, coded_at) "
        "VALUES (?,?,?,?,?)",
        (iid, round_id, coder, json.dumps(sorted(themes), ensure_ascii=False),
         datetime.now(timezone.utc).isoformat()))
    conn.commit()


def blind_round(conn, round_id):
    return [{"item_id": r[0], "coder": r[1], "themes": json.loads(r[2] or "[]")}
            for r in conn.execute(
                "SELECT item_id, coder, themes FROM blind_codes WHERE round_id=?",
                (round_id,)).fetchall()]


def blind_rounds(conn):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT round_id FROM blind_codes ORDER BY round_id DESC").fetchall()]
