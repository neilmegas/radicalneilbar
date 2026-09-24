"""Local review queue for coding.

The export is a CSV you open somewhere else, code, and then have to keep in
sync with a database that keeps moving. This closes that loop: a local page
listing the week's theme-tagged quotes with your categories as buttons,
writing straight back into the `codes` table beside the items.

Local only, by design. It binds to loopback, it is the one part of the system
that writes rather than reads, and coding is desk work. Nothing here is
published to the portal.

Categories come from config/coding.yaml. The defaults are a placeholder
scaffold, not your instrument — replace them.
"""

import html
import json
import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_CATEGORIES = [
    "not applicable",
    "general (JDA 1–5)",
    "Israel-related, antisemitic on its face (JDA 6–10)",
    "Israel-related, not antisemitic on its face (JDA 11–15)",
    "unclear — flag for discussion",
]

PAGE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500&display=swap&subset=latin,latin-ext,greek');
:root{--ground:#E6E7E1;--paper:#F4F5F0;--ink:#1B1D19;--muted:#6A6E64;--rule:#C9CBC1;
  --left:#93202F;--right:#26374F;--mark:#8A6A1F}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:'Source Serif 4',Georgia,serif;font-size:17px;line-height:1.55}
.wrap{max-width:880px;margin:0 auto;padding:1.5rem 1.25rem 5rem}
.meta{font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:12.5px;color:var(--muted)}
h1{font-size:1.9rem;font-weight:600;margin:0 0 .2rem;letter-spacing:-.02em}
.card{background:var(--paper);border:1px solid var(--rule);border-left:3px solid var(--right);
  padding:1rem 1.1rem;margin:1.1rem 0}
.card.left{border-left-color:var(--left)}
.card.done{opacity:.55}
.card h3{margin:0 0 .3rem;font-size:1.03rem}
.q{border-left:2px solid var(--mark);padding-left:.8rem;margin:.6rem 0}
.q .orig{font-size:1.02rem}
.q .tr{color:var(--muted);font-style:italic;margin-top:.15rem}
.cats{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.7rem}
button.cat{font-family:'IBM Plex Sans',sans-serif;font-size:12.5px;padding:.32rem .7rem;
  border:1px solid var(--rule);background:transparent;cursor:pointer;color:var(--ink)}
button.cat:hover{border-color:var(--muted)}
button.cat[data-on="1"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
input.note{font-family:'IBM Plex Sans',sans-serif;font-size:13px;width:100%;margin-top:.5rem;
  padding:.4rem .5rem;border:1px solid var(--rule);background:#fff;color:var(--ink)}
.saved{color:var(--mark);font-family:'IBM Plex Sans',sans-serif;font-size:12px;margin-left:.5rem}
.bar{position:sticky;top:0;background:var(--ground);border-bottom:2px solid var(--ink);
  padding:.7rem 0;margin-bottom:1rem;z-index:2}
a{color:var(--ink)}
"""


def build_page(items, categories, codes, week, coder):
    cards = []
    for it, qi, q in items:
        key = (it["id"], qi)
        existing = codes.get(key, {})
        a = it.get("analysis") or {}
        cards.append(f"""
<div class="card {html.escape(it.get('camp','right'))} {'done' if existing.get('category') else ''}"
     id="c-{html.escape(it['id'])}-{qi}">
  <h3>{html.escape(it.get('party_name',''))}
    <span class="meta">{html.escape((it.get('published') or '')[:10])} ·
    {html.escape(it.get('provenance') or '')} ·
    {html.escape(", ".join(a.get('topics') or []))}</span></h3>
  <p>{html.escape(a.get('summary',''))}</p>
  {"".join(f'''<div class="q"><div class="orig">{html.escape(q['original'])}</div>
     <div class="tr">{html.escape(q.get('translation',''))}</div>
     <div class="meta">{html.escape(q.get('speaker') or '')}</div></div>''' if q else '')}
  <div class="meta"><a href="{html.escape(it.get('url') or '#')}" target="_blank">source</a>
    {f' · <a href="{html.escape(it["archive_url"])}" target="_blank">archived</a>' if it.get('archive_url') else ''}
    · {html.escape(it.get('snapshot_path') or '')}</div>
  <div class="cats">
    {"".join(f'''<button class="cat" data-item="{html.escape(it['id'])}" data-qi="{qi}"
       data-cat="{html.escape(c)}" data-on="{1 if existing.get('category')==c else 0}"
       >{html.escape(c)}</button>''' for c in categories)}
  </div>
  <input class="note" data-item="{html.escape(it['id'])}" data-qi="{qi}"
     placeholder="Notes" value="{html.escape(existing.get('notes') or '')}">
  <span class="saved" id="s-{html.escape(it['id'])}-{qi}">
    {('coded ' + html.escape(existing.get('coded_date') or '')) if existing.get('category') else ''}</span>
</div>""")

    done = sum(1 for it, qi, _ in items if codes.get((it["id"], qi), {}).get("category"))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coding — {html.escape(week)}</title><style>{PAGE_CSS}</style></head><body><div class="wrap">
<div class="bar"><h1>Coding queue</h1>
<div class="meta">Week {html.escape(week)} · {len(items)} rows · <span id="done">{done}</span> coded ·
coder: {html.escape(coder)} · writes to data/items.db</div></div>
{''.join(cards)}
<p class="meta">Close the tab and stop the server when finished. Codes are in the
database and flow into the next CSV export.</p>
<script>
async function save(item, qi, cat, note){{
  const r = await fetch('/save', {{method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{item_id:item, quote_index:qi, category:cat, notes:note}})}});
  const el = document.getElementById('s-'+item+'-'+qi);
  if(r.ok){{ const d = await r.json(); el.textContent = 'coded ' + d.coded_date;
    document.getElementById('c-'+item+'-'+qi).classList.add('done');
    document.getElementById('done').textContent = d.total; }}
  else {{ el.textContent = 'save failed'; }}
}}
document.querySelectorAll('button.cat').forEach(b => b.addEventListener('click', () => {{
  const item=b.dataset.item, qi=b.dataset.qi;
  document.querySelectorAll(`button.cat[data-item="${{item}}"][data-qi="${{qi}}"]`)
    .forEach(x => x.dataset.on = '0');
  b.dataset.on = '1';
  const note = document.querySelector(`input.note[data-item="${{item}}"][data-qi="${{qi}}"]`);
  save(item, qi, b.dataset.cat, note ? note.value : '');
}}));
document.querySelectorAll('input.note').forEach(n => n.addEventListener('change', () => {{
  const on = document.querySelector(
    `button.cat[data-item="${{n.dataset.item}}"][data-qi="${{n.dataset.qi}}"][data-on="1"]`);
  if(on) save(n.dataset.item, n.dataset.qi, on.dataset.cat, n.value);
}}));
</script></div></body></html>"""


def queue_items(items, themes_only=True):
    """One row per quote; items without quotes still get a row so a coding
    decision can be recorded against the summary."""
    rows = []
    for it in items:
        a = it.get("analysis") or {}
        if not a.get("relevant"):
            continue
        if themes_only and not (a.get("topics") or []):
            continue
        quotes = a.get("quotes") or []
        if not quotes:
            rows.append((it, 0, None))
        else:
            for i, q in enumerate(quotes):
                if q.get("original"):
                    rows.append((it, i, q))
    return rows


def serve(conn, store, items, categories, week, coder, port=8765, open_browser=True):
    rows = queue_items(items)
    if not rows:
        print("Nothing to code this week — no theme-tagged items.")
        return

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            codes = store.get_codes(conn, [r[0]["id"] for r in rows])
            page = build_page(rows, categories, codes, week, coder).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/save":
                self.send_error(404)
                return
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                store.set_code(conn, d["item_id"], int(d.get("quote_index", 0)),
                               d.get("category"), coder, d.get("notes", ""))
                codes = store.get_codes(conn, [r[0]["id"] for r in rows])
                total = sum(1 for it, qi, _ in rows
                            if codes.get((it["id"], qi), {}).get("category"))
                import datetime
                body = json.dumps({
                    "ok": True, "total": total,
                    "coded_date": datetime.datetime.now(
                        datetime.timezone.utc).date().isoformat(),
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_error(500, str(e))

    srv = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Coding queue for {week}: {len(rows)} rows at {url}")
    print("Ctrl-C when finished.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Codes saved to the database.")


def load_categories(path="config/coding.yaml"):
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)["categories"]
    except Exception:
        return DEFAULT_CATEGORIES


# --------------------------------------------------- blind coding rounds

BLIND_CSS = PAGE_CSS + """
.tchip{display:inline-block;font-size:12.5px;padding:.3rem .7rem;border:1px solid var(--rule);
  cursor:pointer;margin-right:.4rem;background:transparent;color:var(--ink);
  font-family:'IBM Plex Sans',sans-serif}
.tchip[data-on="1"]{background:var(--ink);color:#fff;border-color:var(--ink)}
"""

BLIND_THEMES = [
    ("israel_palestine", "Israel and Palestine"),
    ("jews_antisemitism", "Jews and antisemitism"),
    ("immigration", "Immigration"),
]


def build_blind_page(rows, round_id, coder, done):
    """The model's tags are absent from this page. That is the whole point:
    seeing them first makes agreement meaningless."""
    cards = []
    for it in rows:
        a = it.get("analysis") or {}
        quotes = "".join(
            f'<div class="q"><div class="orig">{html.escape(q.get("original",""))}</div>'
            f'<div class="tr">{html.escape(q.get("translation",""))}</div></div>'
            for q in (a.get("quotes") or []) if q.get("original"))
        chips = "".join(
            f'<button class="tchip" data-item="{html.escape(it["id"])}" '
            f'data-theme="{t}" data-on="0">{html.escape(label)}</button>'
            for t, label in BLIND_THEMES)
        cards.append(f"""
<div class="card {html.escape(it.get('camp','right'))}" id="b-{html.escape(it['id'])}">
  <h3>{html.escape(it.get('party_name',''))}
    <span class="meta">{html.escape((it.get('published') or '')[:10])}</span></h3>
  <p>{html.escape(a.get('summary',''))}</p>
  {quotes}
  <div class="meta"><a href="{html.escape(it.get('url') or '#')}" target="_blank">source</a></div>
  <div class="cats">{chips}</div>
  <span class="saved" id="s-{html.escape(it['id'])}"></span>
</div>""")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blind round {html.escape(round_id)}</title><style>{BLIND_CSS}</style></head>
<body><div class="wrap"><div class="bar"><h1>Blind coding</h1>
<div class="meta">Round {html.escape(round_id)} · {len(rows)} items · coder
{html.escape(coder)} · <span id="done">{done}</span> coded</div></div>
<p class="meta">Tag each item with whichever themes apply, or none. The model's
tags are deliberately not shown — agreement computed after seeing them would
measure nothing. Run <code>python run.py reliability --report {html.escape(round_id)}</code>
when finished.</p>
{''.join(cards)}
<script>
const state = {{}};
async function save(item){{
  const r = await fetch('/blind', {{method:'POST',headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{item_id:item, themes:[...(state[item]||[])]}})}});
  const el = document.getElementById('s-'+item);
  if(r.ok){{ const d = await r.json(); el.textContent='saved';
    document.getElementById('done').textContent = d.total; }}
}}
document.querySelectorAll('button.tchip').forEach(b => b.addEventListener('click', () => {{
  const i=b.dataset.item, t=b.dataset.theme;
  state[i] = state[i] || new Set();
  if(state[i].has(t)){{ state[i].delete(t); b.dataset.on='0'; }}
  else {{ state[i].add(t); b.dataset.on='1'; }}
  save(i);
}}));
</script></div></body></html>"""


def serve_blind(conn, store, rows, round_id, coder, port=8766, open_browser=True):
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            done = len({r["item_id"] for r in store.blind_round(conn, round_id)
                        if r["coder"] == coder})
            page = build_blind_page(rows, round_id, coder, done).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/blind":
                self.send_error(404)
                return
            n = int(self.headers.get("Content-Length", 0))
            try:
                d = _json.loads(self.rfile.read(n) or b"{}")
                store.set_blind_code(conn, d["item_id"], round_id, coder,
                                     d.get("themes") or [])
                total = len({r["item_id"] for r in store.blind_round(conn, round_id)
                             if r["coder"] == coder})
                body = _json.dumps({"ok": True, "total": total}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as ex:
                self.send_error(500, str(ex))

    srv = HTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Blind round {round_id}: {len(rows)} items at {url}")
    print("Ctrl-C when finished.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Run `python run.py reliability --report "
              f"{round_id}` for agreement.")
