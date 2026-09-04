"""Static site generator.

Produces a self-contained portal: latest issue, a permanent archive of every
issue ever built, and a page per party showing that party's whole run rather
than one week of it. No server, no build step, no framework — plain files that
any static host will serve.

Camp colour follows the parties' own vernacular: deep red for the radical
left, navy for the far right. It encodes a real dimension of the data, so
scanning a page tells you the composition of a week before you read a word.
"""

import html
import json
import os
import shutil

from evidence import PROVENANCE
from trends import THEMES

THEME_LABEL = {
    "israel_palestine": "Israel and Palestine",
    "jews_antisemitism": "Jews and antisemitism",
    "immigration": "Immigration",
}

CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap&subset=latin,latin-ext,greek,hebrew');

:root{
  --paper:#FFFFFF; --surface:#F6F8F9; --ink:#0A1B2E; --muted:#5C6670;
  --accent:#00A3C8; --accent-dk:#0B7E9B; --grey:#8E8E8E;
  --track:#E9E9E9; --rule:#A8D9E6; --hair:#DCE3E6;
  /* Camps take navy and cyan from the palette. */
  --right:#0A1B2E; --left:#00A3C8;
}
*,*::before,*::after{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:'IBM Plex Sans',ui-sans-serif,system-ui,sans-serif;
  font-size:16.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:880px;margin:0 auto;padding:0 1.25rem 5rem}
.meta{font-size:12.5px;line-height:1.45;color:var(--muted)}
.num{font-family:'Source Serif 4',Georgia,serif;font-variant-numeric:tabular-nums}
a{color:var(--accent-dk)} a:hover{color:var(--ink)}
a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
[dir="rtl"]{text-align:right}

nav.top{border-bottom:3px solid var(--ink);padding:1.4rem 0 .7rem;margin-bottom:1.6rem;
  display:flex;flex-wrap:wrap;gap:.5rem 1.3rem;align-items:baseline}
nav.top .brand{font-weight:700;font-size:1.2rem;letter-spacing:-.02em;
  text-decoration:none;color:var(--ink)}
nav.top a:not(.brand){font-size:13px;color:var(--muted);text-decoration:none}
nav.top a:not(.brand):hover{color:var(--accent-dk)}
nav.top .spacer{flex:1}

h1{font-size:clamp(2rem,5.4vw,2.9rem);font-weight:700;letter-spacing:-.03em;
  line-height:1.02;margin:0 0 .35rem}
h2{font-size:1.32rem;font-weight:700;letter-spacing:-.015em;margin:2.4rem 0 .2rem;
  padding-bottom:.4rem;border-bottom:2px solid var(--ink)}
h3{font-size:1.1rem;font-weight:600;margin:1.9rem 0 .3rem;color:var(--ink)}
h3 .cc{color:var(--accent);font-weight:700}
p{margin:.65rem 0}
.lede{font-size:1.06rem;line-height:1.62}
.brief{color:#2B3947}
hr.thin{border:0;border-top:1px solid var(--rule);margin:1.6rem 0}

/* items */
.item{display:grid;grid-template-columns:66px 1fr;gap:0 1rem;padding:1.15rem 0;
  border-bottom:1px solid var(--hair)}
.rail{border-left:4px solid var(--right);padding-left:.6rem}
.rail.left{border-left-color:var(--left)}
.rail span{display:block;font-size:11px;color:var(--muted)}
.rail .cc{font-weight:700;color:var(--ink)}
.rail .anchor{display:block;margin-top:.35rem;font-size:12px;color:var(--track);
  text-decoration:none}
.rail .anchor:hover,.item:target .anchor{color:var(--accent)}
.item:target{background:var(--surface);outline:2px solid var(--accent);outline-offset:6px}
.pname{font-weight:600}
.pname .full{font-weight:400;color:var(--muted);font-size:.87em;margin-left:.4rem}

.ptag{display:inline-block;font-size:10.5px;padding:.1rem .45rem;
  border:1px solid var(--hair);color:var(--muted);margin-left:.4rem;vertical-align:.12em;
  cursor:help;border-radius:2px}
.ptag.p1,.ptag.p2{border-color:var(--accent);color:var(--accent-dk);font-weight:500}
.ptag.p5{border-style:dashed}
.themes{margin:.2rem 0 .1rem}
.themes .tt{display:inline-block;font-size:11.5px;color:var(--accent-dk);
  border-bottom:2px solid var(--accent);margin-right:.6rem}

blockquote{margin:.7rem 0 0;padding-left:.9rem;border-left:3px solid var(--accent)}
blockquote[dir="rtl"]{padding:0 .9rem 0 0;border-left:0;border-right:3px solid var(--accent)}
blockquote .orig{font-family:'Source Serif 4',Georgia,serif;font-size:1.05rem}
blockquote .tr{color:var(--muted);font-style:italic;margin-top:.2rem;font-size:.95rem}

.prov{margin-top:.55rem;display:flex;flex-wrap:wrap;gap:.3rem .8rem}
.coded{color:var(--accent-dk);font-weight:500}
.retract{margin:.6rem 0 0;padding:.5rem .8rem;background:#FDF3F0;
  border-left:4px solid var(--grey);font-size:.93rem}
.anno{margin:.6rem 0 0;padding:.5rem .8rem;background:#FFFCF0;
  border-left:4px solid var(--accent-dk);font-size:.95rem}
.anno .ih,.bt .ih{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:.2rem}
.bt{margin:.6rem 0 0;padding:.5rem .8rem;background:var(--surface);
  border-left:4px solid var(--grey);font-size:.92rem}
.bt .lb{font-weight:600;margin-right:.4rem;text-transform:uppercase;font-size:10.5px;
  color:var(--grey)}
.hstate{display:inline-block;font-size:10.5px;padding:.05rem .4rem;border:1px solid;
  text-transform:uppercase;letter-spacing:.05em}
.hstate.regressed{border-color:var(--grey);color:#B4462F;background:#FDF3F0}
.hstate.intermittent{border-color:var(--grey);color:var(--muted)}
.hstate.healthy{border-color:var(--rule);color:var(--accent-dk)}
.hstate.never{border-color:var(--hair);color:var(--muted)}
.spark12{display:inline-flex;gap:2px;align-items:center;vertical-align:middle}
.spark12 i{width:7px;height:13px;background:var(--track);display:block}
.spark12 i.ok{background:var(--accent)}
.baseline{display:flex;flex-wrap:wrap;gap:1.4rem;margin:.5rem 0 1rem;
  padding:.7rem .9rem;background:var(--surface);border-left:4px solid var(--accent)}
.baseline .b{min-width:130px}
.baseline .bv{font-family:'Source Serif 4',Georgia,serif;font-size:1.7rem;
  line-height:1;color:var(--accent)}
.baseline .bk{font-size:11.5px;color:var(--muted);margin-top:.2rem}
.edge{display:grid;grid-template-columns:1fr auto;gap:.5rem;padding:.3rem 0;
  border-bottom:1px solid var(--hair);font-size:.93rem}
.kap{font-variant-numeric:tabular-nums}
.dup{color:var(--grey)}
.note{margin-top:.5rem;font-size:.87rem;color:var(--muted);
  border-top:1px solid var(--hair);padding-top:.4rem}

/* the two model-written blocks, deliberately unlike each other */
.ctx{margin:.7rem 0 0;padding:.55rem .85rem;background:var(--surface);
  border-left:4px solid var(--grey);font-size:.95rem}
.ctx .ih{font-size:11px;color:var(--muted);margin-bottom:.25rem;
  text-transform:uppercase;letter-spacing:.06em}
.interp{margin:.55rem 0 .2rem;padding:.6rem .85rem;background:var(--paper);
  border:1px solid var(--rule);border-left:4px solid var(--accent);font-size:.95rem}
.interp.sig-unusual{border-left-width:6px;background:#F2FAFC}
.interp .ih{display:flex;flex-wrap:wrap;gap:.5rem;align-items:baseline;
  margin-bottom:.35rem;font-size:11px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.06em}
.interp .ih .sig{border:1px solid var(--accent);color:var(--accent-dk);
  padding:0 .35rem;letter-spacing:.02em}
.interp.sig-routine .ih .sig{border-color:var(--hair);color:var(--muted)}
.interp p{margin:.3rem 0}
.interp .rd{font-size:1rem}
.interp .lb{font-size:11px;color:var(--muted);margin-right:.35rem;font-weight:500}
.interp .fw{border-bottom:1px dotted var(--accent);color:var(--accent-dk)}
.interp .cav{color:var(--muted);font-style:italic}

details.cite{margin-top:.4rem}
details.cite summary{cursor:pointer;font-size:12.5px;color:var(--muted)}
pre.bib{background:var(--surface);border:1px solid var(--hair);padding:.5rem .6rem;
  font-size:11.5px;overflow-x:auto;white-space:pre-wrap;margin:.4rem 0 0}

/* blocks */
.box{background:var(--surface);border:1px solid var(--hair);padding:.95rem 1.05rem;margin:1rem 0}
.box.dashed{border-style:dashed;background:var(--paper)}
.box.flag{border-left:4px solid var(--accent);background:var(--paper)}
.box h4{margin:0 0 .4rem;font-size:1rem;font-weight:600}
.box p{margin:.3rem 0}
.box .rm{margin:.15rem 0;color:var(--grey);font-size:.92rem}
.box .ad{margin:.15rem 0;color:var(--accent-dk);font-size:.92rem}

.cut{border:2px solid var(--ink);padding:1rem 1.1rem;margin:1.3rem 0}
.cut h4{margin:0 0 .4rem;font-size:1.05rem;font-weight:700}
.cut ol{margin:.4rem 0 0;padding-left:1.2rem}
.cut li{margin:.5rem 0}

/* highlights */
.partyblock{margin-top:1.7rem}
.partyblock .ph{font-weight:600;font-size:1.03rem;border-bottom:1px solid var(--hair);
  padding-bottom:.25rem}
.partyblock .ph .camp{display:inline-block;width:9px;height:9px;margin-right:.5rem;
  background:var(--right)}
.partyblock .ph .camp.left{background:var(--left)}
.partyblock .ph .full{font-weight:400;color:var(--muted);font-size:.87em}
ul.hl{list-style:none;padding:0;margin:.6rem 0 0}
ul.hl li{padding:.5rem 0 .5rem .9rem;border-bottom:1px solid var(--hair);
  border-left:4px solid var(--track)}
ul.hl li.right{border-left-color:var(--right)}
ul.hl li.left{border-left-color:var(--left)}
ul.hl .tagline{font-size:11.5px;color:var(--muted);display:block;margin-top:.15rem}

/* reading list */
.read{padding:.6rem 0;border-bottom:1px solid var(--hair)}
.read .kind{display:inline-block;font-size:10.5px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--accent-dk);border:1px solid var(--rule);
  padding:0 .4rem;margin-right:.5rem}
.read .src{font-size:12px;color:var(--muted)}

/* tables and lists */
table.idx,table.rev{width:100%;border-collapse:collapse;margin-top:1rem}
table.idx th,table.rev th{text-align:left;font-size:11.5px;color:var(--muted);
  font-weight:500;text-transform:uppercase;letter-spacing:.05em;
  border-bottom:2px solid var(--ink);padding:.4rem .5rem .4rem 0}
table.idx td,table.rev td{padding:.5rem .5rem .5rem 0;border-bottom:1px solid var(--hair);
  vertical-align:top}
table.rev{font-size:.9rem}
table.idx td.n,table.rev td.n{font-size:13px;color:var(--muted);white-space:nowrap;
  font-variant-numeric:tabular-nums}
table.rev tr.filtered td{color:var(--muted)}

.grid{display:grid;gap:.1rem 1.2rem}
@media(min-width:600px){.grid{grid-template-columns:1fr 1fr}}
.grow{display:flex;justify-content:space-between;gap:.5rem;padding:.26rem 0;
  border-bottom:1px solid var(--hair);font-size:.93rem}
.bad{color:var(--grey)}
.glance div{padding:.3rem 0;border-bottom:1px solid var(--hair)}
.glance .th{font-weight:600}
.spk{display:grid;grid-template-columns:1fr auto;gap:.4rem;padding:.32rem 0;
  border-bottom:1px solid var(--hair)}

/* bars, in the style of the source chart */
.bars{display:flex;align-items:flex-end;gap:3px;height:36px;margin:.3rem 0 .9rem}
.bars i{width:26px;background:var(--track);display:block}
.bars i.on{background:var(--right)}
.bars.left i.on{background:var(--left)}
.statline{display:flex;flex-wrap:wrap;gap:1.5rem;margin:.8rem 0 0}
.stat .v{font-family:'Source Serif 4',Georgia,serif;font-size:2rem;line-height:1;
  color:var(--accent);font-variant-numeric:tabular-nums}
.stat .k{font-size:12px;color:var(--muted);margin-top:.2rem}

input.q{font-size:14px;padding:.5rem .6rem;border:1px solid var(--hair);
  background:var(--surface);width:100%;max-width:340px;color:var(--ink);
  font-family:inherit}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--rule)}
"""

from reportbuilder import REPORT_CSS  # noqa: E402
CSS = CSS + REPORT_CSS



def e(s):
    return html.escape(str(s or ""))


def layout(title, body, depth=0, subtitle=""):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{e(title)}</title>
<link rel="stylesheet" href="{up}assets/style.css">
</head><body><div class="wrap">
<nav class="top">
  <a class="brand" href="{up}index.html">Radical Party Watch</a>
  <a href="{up}archive.html">Archive</a>
  <a href="{up}parties.html">Parties</a>
  <a href="{up}speakers.html">Speakers</a>
  <a href="{up}report.html">Report</a>
  <a href="{up}network.html">Network</a>
  <a href="{up}health.html">Health</a>
  <span class="spacer"></span>
  <span class="meta">{e(subtitle)}</span>
</nav>
{body}
<footer class="meta">
Research monitoring archive. Every item links to its source and, where the
capture succeeded, to an archived copy; source text is snapshotted at
collection time and committed alongside each issue.
</footer>
</div></body></html>"""


def cite_string(it):
    """A citation you can paste into a footnote, with the archived copy and
    the date it was captured — which is the part that makes a claim about a
    party website checkable a year later."""
    party = it.get("party_full") or it.get("party_name") or it["party_id"]
    date = (it.get("published") or "")[:10]
    bits = [party]
    if it.get("title"):
        bits.append(f'"{it["title"][:120]}"')
    if it.get("outlet"):
        bits.append(it["outlet"])
    if date:
        bits.append(date)
    if it.get("url"):
        bits.append(it["url"])
    if it.get("archive_url"):
        bits.append(f'archived at {it["archive_url"]}')
    if it.get("collected_at"):
        bits.append(f'collected {it["collected_at"][:10]}')
    return ", ".join(bits) + "."


def bibtex(it):
    key = f'{it["party_id"]}{(it.get("published") or "")[:10].replace("-", "")}'
    fields = [
        ("author", it.get("party_full") or it.get("party_name") or ""),
        ("title", (it.get("title") or "")[:160]),
        ("howpublished", it.get("outlet") or it.get("source_type") or ""),
        ("year", (it.get("published") or "")[:4]),
        ("url", it.get("archive_url") or it.get("url") or ""),
        ("urldate", (it.get("collected_at") or "")[:10]),
        ("note", f'source class: {it.get("provenance","")}; '
                 f'snapshot: {it.get("snapshot_path","")}'),
    ]
    body = "\n".join(f'  {k} = {{{v}}},' for k, v in fields if v)
    return "@misc{" + key + ",\n" + body + "\n}"


def prov_tag(item):
    p = item.get("provenance")
    if not p:
        return ""
    label, rank, _ = PROVENANCE.get(p, (p, 9, ""))
    return f'<span class="prov-tag p{rank}" title="{e(PROVENANCE.get(p,("","",""))[2])}">{e(label)}</span>'


def item_html(it, show_party=True, cluster_sizes=None):
    a = it.get("analysis") or {}
    cluster_sizes = cluster_sizes or {}
    parts = [f'<article class="item" id="item-{e(it["id"])}">'
             f'<div class="rail {e(it.get("camp","right"))}">'
             f'<span class="cc">{e(it.get("country",""))}</span>'
             f'<span>{e((it.get("published") or "")[:10])}</span>'
             f'<a class="anchor" href="#item-{e(it["id"])}" '
             f'title="Permanent link to this item">#</a></div><div>']
    if show_party:
        parts.append(f'<div class="pname">{e(it.get("party_name",""))}'
                     f'<span class="full">{e(it.get("party_full",""))}</span>'
                     f'{prov_tag(it)}</div>')
    else:
        parts.append(f'<div class="meta">{prov_tag(it)}</div>')
    topics = [THEME_LABEL[t] for t in (a.get("topics") or []) if t in THEME_LABEL]
    if topics:
        parts.append('<div class="themes meta">'
                     + "".join(f'<span class="tt">{e(t)}</span>' for t in topics)
                     + '</div>')
    parts.append(f'<p>{e(a.get("summary",""))}</p>')

    for q in (a.get("quotes") or [])[:2]:
        if not q.get("original"):
            continue
        rtl = ' dir="rtl"' if it.get("rtl") else ''
        parts.append(f'<blockquote{rtl}>')
        parts.append(f'<div class="orig">{e(q["original"])}</div>')
        if q.get("translation") and q["translation"] != q["original"]:
            parts.append(f'<div class="tr">{e(q["translation"])}</div>')
        if q.get("speaker"):
            parts.append(f'<div class="meta">{e(q["speaker"])}</div>')
        parts.append('</blockquote>')

    links = []
    if it.get("url"):
        links.append(f'<a href="{e(it["url"])}" rel="noreferrer">{e(it.get("outlet") or "source")}</a>')
    else:
        links.append('<span>no source link captured</span>')
    if it.get("archive_url"):
        links.append(f'<a href="{e(it["archive_url"])}" rel="noreferrer">archived</a>')
    if it.get("snapshot_path"):
        links.append(f'<span>{e(it["snapshot_path"])}</span>')
    if a.get("confidence") and a["confidence"] != "high":
        links.append(f'<span>confidence: {e(a["confidence"])}</span>')
    ip = it.get("interpretation") or {}
    if ip.get("explanation"):
        parts.append(f'<div class="ctx"><div class="ih">What is going on</div>'
                     f'<p>{e(ip["explanation"])}</p></div>')
    if ip.get("reading"):
        sig = ip.get("significance", "routine")
        rows = []
        rows.append(f'<p class="rd">{e(ip["reading"])}</p>')
        if ip.get("why_now"):
            rows.append(f'<p><span class="lb">Timing</span> {e(ip["why_now"])}</p>')
        cont = ip.get("continuity")
        if cont and cont != "unclear":
            rows.append(f'<p><span class="lb">Against the record</span> '
                        f'<strong>{e(cont)}</strong> — {e(ip.get("continuity_note",""))}</p>')
        elif ip.get("continuity_note"):
            rows.append(f'<p><span class="lb">Against the record</span> '
                        f'{e(ip["continuity_note"])}</p>')
        if ip.get("comparison"):
            rows.append(f'<p><span class="lb">Beside others</span> {e(ip["comparison"])}</p>')
        if ip.get("watch"):
            rows.append(f'<p><span class="lb">Watch for</span> {e(ip["watch"])}</p>')
        if ip.get("frameworks"):
            rows.append('<p><span class="lb">Candidate for</span> '
                        + ", ".join(f'<span class="fw">{e(f)}</span>'
                                    for f in ip["frameworks"]) + '</p>')
        if ip.get("caveat"):
            rows.append(f'<p class="cav"><span class="lb">Assuming</span> {e(ip["caveat"])}</p>')
        parts.append(
            f'<div class="interp sig-{e(sig)}">'
            f'<div class="ih meta">Interpretation — model inference, not evidence'
            f'<span class="sig">{e(sig)}</span>'
            f'<span class="cf">confidence: {e(ip.get("confidence","?"))}</span></div>'
            + "".join(rows) + '</div>')

    ls = it.get("link_status")
    if ls in ("gone", "changed"):
        word = ("source page has since been removed" if ls == "gone"
                else "source page has materially changed since capture")
        parts.append(f'<div class="retract"><strong>{e(word)}</strong> — the '
                     f'snapshot taken at collection is the record. '
                     f'<span class="meta">{e(it.get("snapshot_path") or "")}</span></div>')
    if it.get("annotation"):
        parts.append(f'<div class="anno"><div class="ih">Your note</div>'
                     f'<p>{e(it["annotation"])}</p></div>')
    bt = it.get("backtranslation") or []
    flagged = [b for b in bt if b.get("flagged")]
    if flagged:
        parts.append('<div class="bt"><div class="ih">Translation check</div>')
        for b in flagged:
            parts.append(f'<p><span class="lb">{e(b.get("severity",""))}</span>'
                         f'{e(b.get("note",""))}</p>'
                         f'<p class="meta">round trip: {e(b.get("round_trip",""))}</p>')
        parts.append('</div>')

    if it.get("meta_stamp"):
        links.append(f'<span title="which model and prompt version produced this '
                     f'analysis">{e(it["meta_stamp"])}</span>')
    if it.get("coded"):
        links.append(f'<span class="coded">coded: {e(it["coded"])}</span>')
    n = cluster_sizes.get(it.get("cluster_id"), 1)
    if n > 1:
        links.append(f'<span class="dup">also carried by {n - 1} other outlet(s)</span>')
    parts.append(f'<div class="prov meta">{"".join(links)}</div>')
    parts.append(
        f'<details class="cite"><summary class="meta">Citation</summary>'
        f'<p class="meta">{e(cite_string(it))}</p>'
        f'<pre class="bib">{e(bibtex(it))}</pre></details>')
    parts.append('</div></article>')
    return "".join(parts)


def bars(series, theme, camp):
    vals = [w[theme] for w in series]
    top = max(vals + [1])
    cells = "".join(
        f'<i class="{"on" if v else ""}" style="height:{max(2, int(34*v/top))}px"></i>'
        for v in vals
    )
    return f'<div class="bars {camp}">{cells}</div>'


# ------------------------------------------------------------- pages

def issue_page(week, items, overview, briefings, country_names, parties,
               absences, shifts_by_party, cluster_sizes, out_dir,
               all_items=None, convergence=None, page_changes=None,
               editors_cut=None, world=None, highlights=None, reading=None,
               week_range="", retractions=None, baselines=None, reference=None):
    """Order follows how the issue is read: the world, then the headlines,
    then country by country and party by party, then what to read."""
    relevant = [i for i in items if (i.get("analysis") or {}).get("relevant")]
    all_items = all_items if all_items is not None else items
    by_id = {p["id"]: p for p in parties}
    flagged = sum(1 for i in relevant
                  if (i.get("interpretation") or {}).get("significance") in ("notable", "unusual"))

    body = [f'<h1>Week {e(week)}</h1>',
            f'<p class="meta">{e(week_range)} · {len(relevant)} items · '
            f'{len({i["party_id"] for i in relevant})} of {len(parties)} parties · '
            f'{flagged} flagged · {len(all_items)} reviewed · '
            f'<a href="../data/{e(week)}.csv">coding rows (CSV)</a></p>']

    # 1 — the world
    body.append('<h2>This week in the world</h2>')
    body.append(f'<p class="lede">{e(world or overview or "")}</p>')
    if world and overview:
        body.append(f'<p class="brief">{e(overview)}</p>')

    # 2 — highlights
    body.append('<h2>Highlights</h2>')
    if highlights:
        item_by_id = {i["id"]: i for i in relevant}
        body.append('<ul class="hl">')
        for h in highlights:
            it = item_by_id.get(h.get("item_id"))
            if not it:
                continue
            sig = (it.get("interpretation") or {}).get("significance", "")
            body.append(
                f'<li class="{e(it.get("camp","right"))}">'
                f'<strong>{e(it.get("party_name"))}</strong> '
                f'<span class="meta">{e(it.get("country",""))} · '
                f'{e((it.get("published") or "")[:10])}</span> — {e(h.get("line",""))} '
                f'<a href="#item-{e(it["id"])}">in issue</a>'
                + (f' · <a href="{e(it["url"])}" rel="noreferrer">source</a>' if it.get("url") else "")
                + (f' · <a href="{e(it["archive_url"])}" rel="noreferrer">archived</a>' if it.get("archive_url") else "")
                + f'<span class="tagline">{e(h.get("tag",""))}'
                + (f' · {e(sig)}' if sig and sig != "routine" else "")
                + f' · {e(PROVENANCE.get(it.get("provenance"),("",0,""))[0])}</span></li>')
        body.append('</ul>')
    else:
        body.append('<div class="box dashed"><p>No highlights this week.</p></div>')

    body.append('<div class="glance" style="margin-top:1.2rem">')
    for t in THEMES:
        hits = [i for i in relevant if t in (i["analysis"].get("topics") or [])]
        if hits:
            links = ", ".join(f'<a href="#item-{e(i["id"])}">{e(i["party_name"])}</a>'
                              for i in sorted(hits, key=lambda x: (x.get("provenance_rank") or 9)))
            body.append(f'<div><span class="th">{THEME_LABEL[t]}</span> — {links}</div>')
        else:
            body.append(f'<div><span class="th">{THEME_LABEL[t]}</span> '
                        f'<span class="meta">— nothing this week</span></div>')
    body.append('</div>')

    if shifts_by_party:
        body.append('<div class="box flag"><h4>Changes against the record</h4>')
        for pname, sh in shifts_by_party.items():
            for sft in sh:
                verb = "took up" if sft["kind"] == "new" else "dropped"
                body.append(f'<p>{e(pname)} {verb} <strong>{e(THEME_LABEL[sft["theme"]])}</strong> '
                            f'<span class="meta">({e(sft["detail"])})</span></p>')
        body.append('</div>')

    if retractions:
        body.append('<div class="box flag"><h4>Source pages gone or rewritten</h4>'
                    '<p class="meta">Previously collected pages that no longer resolve, or '
                    'that differ materially from what was captured. A pulled statement is a '
                    'political act; the snapshot is why you still have the text.</p>')
        for r in retractions[:20]:
            tail = (f'<a href="{e(r["archive_url"])}" rel="noreferrer">archived</a>'
                    if r.get("archive_url")
                    else f'<span class="meta">{e(r.get("snapshot_path") or "")}</span>')
            body.append(f'<p><strong>{e(r.get("party"))}</strong> '
                        f'<span class="meta">{e(r.get("date"))} · {e(r.get("status"))}</span> — '
                        f'{e((r.get("summary") or "")[:150])} {tail}</p>')
        body.append('</div>')

    if page_changes:
        body.append('<div class="box flag"><h4>Programme pages edited</h4>'
                    '<p class="meta">Watched manifesto pages that changed since the '
                    'previous capture. No announcement accompanies these.</p>')
        for ch in page_changes:
            body.append(f'<p><strong>{e(ch["party"])}</strong> '
                        f'<a href="{e(ch["url"])}" rel="noreferrer">page</a> '
                        f'<span class="meta">since {e(ch["since"])}, '
                        f'+{ch["added_total"]} / −{ch["removed_total"]} sentences</span></p>')
            for line in (ch.get("removed") or [])[:3]:
                body.append(f'<p class="rm">− {e(line[:220])}</p>')
            for line in (ch.get("added") or [])[:3]:
                body.append(f'<p class="ad">+ {e(line[:220])}</p>')
        body.append('</div>')

    if convergence:
        body.append('<div class="box"><h4>Language appearing on both flanks</h4>'
                    '<p class="meta">Terms used this week by parties in both camps, in the '
                    'same language, taken from verbatim quotes only. A candidate, not a '
                    'finding — shared vocabulary is not a shared position.</p>')
        for c in convergence:
            body.append(f'<p><strong>{e(c["term"])}</strong> <span class="meta">[{e(c["lang"])}] — '
                        f'left: {e(", ".join(c["left"]))} · right: {e(", ".join(c["right"]))}</span></p>')
        body.append('</div>')

    # 3 — country by country, party by party
    body.append('<h2>By country</h2>')
    used = set()
    codes = sorted({i["country"] for i in relevant} | set(briefings.keys()))
    for code in codes:
        body.append(f'<h3><span class="cc">{e(code)}</span> {e(country_names.get(code, code))}</h3>')
        body.append(baseline_block(code, baselines, reference))
        if briefings.get(code):
            body.append(f'<p class="brief">{e(briefings[code])}</p>')
        for ab in [a for a in absences if a.get("country") == code]:
            body.append(f'<div class="box"><h4>{e(ab["occasion"])} · {e(ab["date"])}</h4>'
                        f'<p class="meta">Engaged: {e(", ".join(ab["spoke"]) or "none")}. '
                        f'Silent: {e(", ".join(ab["silent_names"]) or "none")}.</p></div>')

        here = [i for i in relevant if i["country"] == code]
        for pid in sorted({i["party_id"] for i in here},
                          key=lambda x: (by_id.get(x, {}).get("short") or x)):
            mine = [i for i in here if i["party_id"] == pid]
            p = by_id.get(pid, {})
            body.append(f'<div class="partyblock"><div class="ph">'
                        f'<span class="camp {e(p.get("camp","right"))}"></span>'
                        f'<a href="../parties/{e(pid)}.html">{e(p.get("short") or pid)}</a>'
                        f'<span class="full"> {e(p.get("name",""))}</span></div>')
            shown = set()
            for t in THEMES:
                for i in sorted([x for x in mine if t in (x["analysis"].get("topics") or [])],
                                key=lambda x: (x.get("provenance_rank") or 9)):
                    if i["id"] in shown:
                        continue
                    shown.add(i["id"]); used.add(i["id"])
                    body.append(item_html(i, show_party=False, cluster_sizes=cluster_sizes))
            for i in sorted([x for x in mine if x["id"] not in shown],
                            key=lambda x: (x.get("provenance_rank") or 9))[:8]:
                body.append(item_html(i, show_party=False, cluster_sizes=cluster_sizes))
            body.append('</div>')

    active = {i["party_id"] for i in relevant}
    collected = {i["party_id"] for i in all_items}
    quiet = [p for p in parties if p["id"] not in active]
    if quiet:
        body.append('<h2>No substantive items</h2><div class="grid">')
        for p in sorted(quiet, key=lambda x: x.get("short") or x["id"]):
            bad = ("" if p["id"] in collected
                   else '<span class="meta bad">unreachable</span>')
            body.append(f'<div class="grow"><span>'
                        f'<a href="../parties/{e(p["id"])}.html">{e(p.get("short") or p["id"])}</a> '
                        f'<span class="meta">{e(p.get("country",""))}</span></span>{bad}</div>')
        body.append('</div>')

    # 4 — what to read
    body.append('<h2>Worth reading</h2>')
    if reading:
        body.append('<p class="meta">Commentary, analysis, surveys and reporting from this '
                    'week — secondary literature rather than party output.</p>')
        for r in reading:
            body.append(
                f'<div class="read"><span class="kind">{e(r.get("kind",""))}</span>'
                f'<a href="{e(r.get("url",""))}" rel="noreferrer">{e(r.get("title",""))}</a>'
                f'<span class="src"> · {e(r.get("source",""))}</span>'
                + (f'<p class="meta">{e(r["why"])}</p>' if r.get("why") else "")
                + '</div>')
    else:
        body.append('<div class="box dashed"><p>Nothing collected for the reading list.</p>'
                    '<p class="meta">Check the feeds in config/reading.yaml — a persistent '
                    'blank here is a broken feed list, not a quiet week in the literature.</p></div>')

    # 5 — audit trail
    body.append('<h2>Everything reviewed</h2>'
                f'<p class="meta">{len(all_items)} items reached analysis; {len(relevant)} were '
                'carried. Check what was dropped rather than trusting the filter.</p>'
                '<table class="rev"><thead><tr><th>Party</th><th>Date</th><th>Source</th>'
                '<th>Item</th><th>Status</th></tr></thead><tbody>')
    for it in sorted(all_items, key=lambda x: (x.get("party_id") or "", x.get("published") or "")):
        a = it.get("analysis") or {}
        keep = bool(a.get("relevant"))
        if keep:
            status = f'<a href="#item-{e(it["id"])}">in issue</a>'
        elif a.get("triaged_out"):
            status = e(a["triaged_out"])
        elif a.get("skipped"):
            status = "too short"
        elif a.get("error"):
            status = "analysis failed"
        elif a:
            status = "filtered"
        else:
            status = "not analysed"
        title = (it.get("title") or "")[:90]
        link = (f'<a href="{e(it["url"])}" rel="noreferrer">{e(title)}</a>'
                if it.get("url") else e(title))
        p = by_id.get(it["party_id"], {})
        body.append(f'<tr class="{"" if keep else "filtered"}">'
                    f'<td class="n">{e(p.get("short") or it["party_id"])}</td>'
                    f'<td class="n">{e((it.get("published") or "")[:10])}</td>'
                    f'<td class="n">{e(it.get("outlet") or it.get("source_type") or "")}</td>'
                    f'<td>{link}</td><td class="n">{status}</td></tr>')
    body.append('</tbody></table>')

    os.makedirs(os.path.join(out_dir, "issues"), exist_ok=True)
    path = os.path.join(out_dir, "issues", f"{week}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout(f"Week {week}", "".join(body), depth=1, subtitle=week))
    return path


def baseline_block(code, baselines, reference=None):
    rows = (baselines or {}).get(code) or []
    if not rows:
        return ""
    cells = "".join(
        f'<div class="b"><div class="bv">{e(r["value"])}{e(r.get("unit",""))}</div>'
        f'<div class="bk">{e(r["label"])}'
        + (f'<br>{e(r["note"])}' if r.get("note") else "")
        + '</div></div>' for r in rows)
    if reference:
        cells += (f'<div class="b"><div class="bv" style="color:var(--grey)">'
                  f'{e(reference["value"])}{e(reference.get("unit",""))}</div>'
                  f'<div class="bk">{e(reference["label"])}</div></div>')
    return f'<div class="baseline">{cells}</div>'


def health_page(rows, weeks, silent, prompt_versions, link_summary, out_dir):
    """Whether collection is still working. The per-issue 'unreachable' line is
    a snapshot; this is the series, which is what distinguishes a party that
    went quiet from a feed that died."""
    bad = [r for r in rows if r["state"] in ("regressed", "intermittent")]
    body = ['<h1>Source health</h1>',
            '<p class="lede">Every collection attempt, successful or not, across the '
            'weeks on file. A source that stopped working is new information; one that '
            'never worked is a configuration error you already know about. They are '
            'listed separately for that reason.</p>',
            f'<div class="statline">'
            f'<div class="stat"><div class="v">{len(rows)}</div>'
            f'<div class="k">party-channel pairs</div></div>'
            f'<div class="stat"><div class="v">{len(bad)}</div>'
            f'<div class="k">degraded</div></div>'
            f'<div class="stat"><div class="v">{len(weeks)}</div>'
            f'<div class="k">weeks observed</div></div></div>']

    if silent:
        body.append('<div class="box flag"><h4>Collecting successfully, returning nothing</h4>'
                    '<p class="meta">These parties\' channels report success but produce no '
                    'items. Either the party is genuinely silent or a selector is matching '
                    'an empty page and reporting success. Worth one manual check each.</p>')
        for sdata in silent:
            body.append(f'<p>{e(sdata["party"])} <span class="meta">{e(sdata["country"])} · '
                        f'{sdata["weeks"]} weeks</span></p>')
        body.append('</div>')

    body.append('<h2>By party and channel</h2>'
                '<table class="rev"><thead><tr><th>Party</th><th>Channel</th>'
                '<th>State</th><th>Last 12 weeks</th><th>Rate</th><th>Items</th>'
                '<th>Last error</th></tr></thead><tbody>')
    for r in rows:
        spark = "".join(f'<i class="{"ok" if v else ""}"></i>' for v in r["series"])
        cls = r["state"].split()[0]
        body.append(
            f'<tr><td class="n">{e(r["party"])} <span class="meta">{e(r["country"])}</span></td>'
            f'<td class="n">{e(r["channel"])}</td>'
            f'<td class="n"><span class="hstate {e(cls)}">{e(r["state"])}</span></td>'
            f'<td class="n"><span class="spark12">{spark}</span></td>'
            f'<td class="n kap">{r["rate"]:.0%}</td><td class="n kap">{r["items"]}</td>'
            f'<td class="meta">{e((r["last_error"] or "")[:70])}</td></tr>')
    body.append('</tbody></table>')

    if link_summary:
        body.append('<h2>Source pages re-checked</h2>'
                    '<p class="meta">Collected URLs re-fetched to catch deletions and quiet '
                    'revisions. The local snapshot remains the record either way.</p>'
                    '<div class="statline">')
        for k, v in link_summary.items():
            body.append(f'<div class="stat"><div class="v">{v}</div><div class="k">{e(k)}</div></div>')
        body.append('</div>')

    body.append('<h2>What produced the analysis</h2>'
                '<p class="meta">Prompts change. Items analysed under different versions are '
                'not strictly comparable, so the corpus records which produced what. A mixed '
                'corpus is not a fault; not knowing it is mixed would be.</p>'
                '<table class="rev"><thead><tr><th>Stage</th><th>Model</th><th>Prompt</th>'
                '<th>Items</th><th>First</th><th>Last</th></tr></thead><tbody>')
    for m in prompt_versions:
        body.append(f'<tr><td class="n">{e(m["stage"])}</td><td class="n">{e(m["model"])}</td>'
                    f'<td class="n">{e(m["prompt_ver"])}</td><td class="n kap">{m["n"]}</td>'
                    f'<td class="n">{e((m["first"] or "")[:10])}</td>'
                    f'<td class="n">{e((m["last"] or "")[:10])}</td></tr>')
    body.append('</tbody></table>')

    path = os.path.join(out_dir, "health.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Source health", "".join(body),
                       subtitle=f"{len(bad)} degraded"))
    return path


def network_page(edges, parties, out_dir):
    """Ties between organisations, extracted from item text. Joint appearances,
    endorsements, delegations, splits. Network data the system would otherwise
    read and discard."""
    from collections import Counter
    pair = Counter()
    kinds = {}
    detail = {}
    for ed in edges:
        key = tuple(sorted([ed["source"], ed["target"]]))
        if not key[0] or not key[1] or key[0] == key[1]:
            continue
        pair[key] += 1
        kinds.setdefault(key, Counter())[ed.get("kind") or "unspecified"] += 1
        detail.setdefault(key, []).append(ed)

    body = ['<h1>Ties between organisations</h1>',
            '<p class="lede">Joint appearances, endorsements, delegations, shared platforms '
            'and splits, extracted from item text. Two parties appearing in the same article '
            'is not a tie; only items that evidence an actual relation are counted.</p>',
            f'<p class="meta">{len(pair)} distinct pairs across {len(edges)} recorded ties.</p>']
    if not pair:
        body.append('<div class="box dashed"><p>No ties recorded yet.</p>'
                    '<p class="meta">Relations are extracted during analysis, so this fills '
                    'up only from items analysed after the feature was added.</p></div>')
    for (a, b), n in pair.most_common(200):
        ks = ", ".join(f"{k} ×{v}" for k, v in kinds[(a, b)].most_common())
        body.append(f'<div class="edge"><span><strong>{e(a)}</strong> — <strong>{e(b)}</strong>'
                    f'<br><span class="meta">{e(ks)}</span></span>'
                    f'<span class="meta kap">{n}</span></div>')

    body.append('<h2>Export</h2><p class="meta">Edge list, one row per recorded tie.</p>'
                '<pre class="bib">source,target,kind,item_id\n'
                + "\n".join(f'{e(ed["source"])},{e(ed["target"])},{e(ed.get("kind",""))},'
                             f'{e(ed["item_id"])}' for ed in edges[:400]) + '</pre>')

    path = os.path.join(out_dir, "network.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Network", "".join(body), subtitle=f"{len(pair)} pairs"))
    return path


def _kap(v):
    """Kappa or an em dash. A helper rather than an inline conditional because
    nested same-quote f-strings are a 3.12+ feature and the workflow runs 3.11."""
    return "—" if v is None else f"{v:.2f}"


def reliability_page(reports, out_dir):
    """Agreement between your coding and the model's tagging."""
    body = ['<h1>Coding reliability</h1>',
            '<p class="lede">Blind rounds: you code a reproducible sample without seeing the '
            'model\'s tags, and agreement is computed afterwards. Raw agreement is shown '
            'beside kappa because kappa is unstable on rare labels — and one of these labels '
            'is rare by construction.</p>']
    if not reports:
        body.append('<div class="box dashed"><p>No completed rounds.</p>'
                    '<p class="meta">Start one with <code>python run.py reliability</code>.</p></div>')
    for rep in reports:
        body.append(f'<h2>Round {e(rep["round_id"])}</h2>'
                    f'<p class="meta">{rep["n_items"]} items · coders: '
                    f'{e(", ".join(rep["coders"]))}</p>')
        for coder, res in rep["vs_model"].items():
            body.append(f'<h3>{e(coder)} against the model</h3>'
                        '<table class="rev"><thead><tr><th>Theme</th><th>Raw agreement</th>'
                        '<th>Kappa</th><th>Prevalence</th><th>Model only</th>'
                        '<th>You only</th><th>Note</th></tr></thead><tbody>')
            for lab, v in res.items():
                body.append(
                    f'<tr><td>{e(THEME_LABEL.get(lab, lab))}</td>'
                    f'<td class="n kap">{v["raw_agreement"]:.0%}</td>'
                    f'<td class="n kap">{_kap(v["kappa"])}</td>'
                    f'<td class="n kap">{v["prevalence"]:.0%}</td>'
                    f'<td class="n kap">{v["model_only"]}</td>'
                    f'<td class="n kap">{v["human_only"]}</td>'
                    f'<td class="meta">{e(v["note"])}</td></tr>')
            body.append('</tbody></table>')
        if rep.get("inter_coder"):
            body.append('<h3>Between coders</h3><table class="rev"><thead><tr><th>Theme</th>'
                        '<th>Raw agreement</th><th>Kappa</th></tr></thead><tbody>')
            for lab, v in rep["inter_coder"].items():
                body.append(f'<tr><td>{e(THEME_LABEL.get(lab, lab))}</td>'
                            f'<td class="n kap">{v["raw_agreement"]:.0%}</td>'
                            f'<td class="n kap">{_kap(v["kappa"])}</td></tr>')
            body.append('</tbody></table>')
    path = os.path.join(out_dir, "reliability.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Reliability", "".join(body), subtitle=f"{len(reports)} round(s)"))
    return path


def party_page(party, series, items, out_dir):
    camp = party.get("camp", "right")
    body = [f'<h1>{e(party.get("name"))}</h1>',
            f'<p class="meta">{e(party.get("country",""))} · '
            f'{"radical left" if camp == "left" else "far right"}'
            f'{" · " + e(party["site"]) if party.get("site") else ""}</p>']

    total_all = len(items)
    themed = sum(1 for i in items
                 if (i.get("analysis") or {}).get("topics"))
    quoted = sum(1 for i in items
                 if ((i.get("analysis") or {}).get("quotes") or []))
    body.append('<div class="statline">'
                f'<div class="stat"><div class="v">{total_all}</div>'
                f'<div class="k">items on file</div></div>'
                f'<div class="stat"><div class="v">{themed}</div>'
                f'<div class="k">on your themes</div></div>'
                f'<div class="stat"><div class="v">{quoted}</div>'
                f'<div class="k">with a captured quote</div></div></div>')

    body.append('<h2>Themes over time</h2>')
    body.append(f'<p class="meta">{len(series)} weeks, oldest first.</p>')
    for t in THEMES:
        vals = [w[t] for w in series]
        top = max(vals + [1])
        cells = "".join(f'<i class="{"on" if v else ""}" '
                        f'style="height:{max(2, int(36*v/top))}px" '
                        f'title="{e(series[n]["week"])}: {v}"></i>'
                        for n, v in enumerate(vals))
        body.append(f'<div class="meta">{THEME_LABEL[t]} · {sum(vals)} items</div>'
                    f'<div class="bars {e(camp)}">{cells}</div>')

    body.append('<h2>Everything collected</h2>')
    for it in sorted(items, key=lambda x: (x.get("published") or ""), reverse=True)[:200]:
        body.append(item_html(it, show_party=False))
    if not items:
        body.append('<div class="box dashed"><p>Nothing collected yet.</p>'
                    '<p class="meta">A persistent blank here means the source '
                    'configuration needs attention rather than the party being quiet.</p></div>')

    os.makedirs(os.path.join(out_dir, "parties"), exist_ok=True)
    path = os.path.join(out_dir, "parties", f"{party['id']}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout(party.get("name"), "".join(body), depth=1,
                       subtitle=party.get("country", "")))
    return path


def speakers_page(index, out_dir):
    """Named figures across all parties. Items are attributed to parties,
    which hides intra-party variation; this is where a figure who diverges
    from the party line becomes visible."""
    rows = sorted(index.items(), key=lambda kv: -len(kv[1]["items"]))
    body = ['<h1>Speakers</h1>',
            '<p class="lede">Named figures extracted from items across every issue. '
            'A party page aggregates; this disaggregates, which is where factional '
            'divergence shows up.</p>',
            f'<p class="meta">{len(rows)} named figures.</p>',
            '<p><input class="q" id="q" placeholder="Filter speakers" autocomplete="off"></p>',
            '<div id="rows">']
    for key, rec in rows:
        themes = ", ".join(f"{THEME_LABEL.get(t,t)} ({n})"
                           for t, n in sorted(rec["themes"].items(), key=lambda x: -x[1])
                           if t in THEME_LABEL)
        body.append(
            f'<div class="spk"><span>'
            f'<a href="speakers/{e(slug(key))}.html">{e(rec["display"])}</a> '
            f'<span class="meta">{e(", ".join(rec["parties"]))}'
            f'{" · " + e(themes) if themes else ""}</span></span>'
            f'<span class="meta">{len(rec["items"])} items · {rec["quoted"]} quoted</span></div>')
    body += ['</div>', """<script>
const q=document.getElementById('q');
q.addEventListener('input',()=>{const v=q.value.toLowerCase();
 for(const d of document.querySelectorAll('#rows .spk'))
   d.style.display=d.textContent.toLowerCase().includes(v)?'':'none';});
</script>"""]
    path = os.path.join(out_dir, "speakers.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Speakers", "".join(body), subtitle=f"{len(rows)} figures"))
    return path


def slug(name):
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "unnamed"


def speaker_page(key, rec, items, out_dir):
    body = [f'<h1>{e(rec["display"])}</h1>',
            f'<p class="meta">{e(", ".join(rec["parties"]))} · '
            f'{len(rec["items"])} items · {rec["quoted"]} directly quoted</p>']
    if rec["themes"]:
        body.append('<h2>Themes</h2><div class="glance">')
        for t, n in sorted(rec["themes"].items(), key=lambda x: -x[1]):
            if t in THEME_LABEL:
                body.append(f'<div><span class="th">{THEME_LABEL[t]}</span> '
                            f'<span class="meta">— {n} items</span></div>')
        body.append('</div>')
    body.append('<h2>Items</h2>')
    for it in sorted(items, key=lambda x: (x.get("published") or ""), reverse=True)[:120]:
        body.append(item_html(it))
    if not items:
        body.append('<div class="box dashed"><p>No items on file.</p></div>')
    os.makedirs(os.path.join(out_dir, "speakers"), exist_ok=True)
    path = os.path.join(out_dir, "speakers", f"{slug(key)}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout(rec["display"], "".join(body), depth=1,
                       subtitle=", ".join(rec["parties"])))
    return path


def roster_page(candidates, out_dir):
    """Parties the monthly check thinks are missing. Proposals only — adding
    one changes any dataset built on the roster, so it stays your decision."""
    body = ['<h1>Roster gaps</h1>',
            '<p class="lede">Parties the monthly check found that are not monitored. '
            'A fixed roster is blind to splits and new entrants, which are exactly '
            'the events worth catching. Nothing here is added automatically.</p>']
    if not candidates:
        body.append('<div class="box dashed"><p>No gaps found in the last check.</p></div>')
    for c in candidates:
        body.append(
            f'<div class="box"><h4>{e(c.get("name"))} '
            f'<span class="meta">{e(c.get("country",""))} · '
            f'{"radical left" if c.get("camp")=="left" else "far right"}</span></h4>'
            f'<p>{e(c.get("why",""))}</p>'
            f'<p class="meta">{e(c.get("origin",""))} · founded {e(c.get("founded","?"))} · '
            f'{e(c.get("polling",""))} · seats: {e(c.get("seats",""))}'
            f'{" · " + e(c["site"]) if c.get("site") else ""}</p></div>')
    path = os.path.join(out_dir, "roster.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Roster gaps", "".join(body),
                       subtitle=f"{len(candidates)} candidate(s)"))
    return path


def archive_page(index, out_dir):
    rows = "".join(
        f'<tr><td class="n"><a href="issues/{e(r["week"])}.html">{e(r["week"])}</a></td>'
        f'<td class="n">{e(r["range"])}</td>'
        f'<td>{e(r["headline"])}</td>'
        f'<td class="n">{r["items"]} items · {r["parties"]} parties</td>'
        f'<td class="n"><a href="data/{e(r["week"])}.csv">CSV</a></td></tr>'
        for r in index
    )
    body = f"""<h1>Archive</h1>
<p class="lede">Every issue built, oldest at the bottom. Issues are permanent —
nothing is regenerated once published, so a quote you cited last March still
reads as it did then.</p>
<p><input class="q" id="q" placeholder="Filter issues" autocomplete="off"></p>
<table class="idx"><thead><tr><th>Week</th><th>Dates</th><th>Lead</th><th>Volume</th><th>Data</th></tr></thead>
<tbody id="rows">{rows}</tbody></table>
<script>
const q=document.getElementById('q');
q.addEventListener('input',()=>{{
  const v=q.value.toLowerCase();
  for(const tr of document.querySelectorAll('#rows tr'))
    tr.style.display = tr.textContent.toLowerCase().includes(v) ? '' : 'none';
}});
</script>"""
    path = os.path.join(out_dir, "archive.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Archive", body, subtitle=f"{len(index)} issues"))
    return path


def parties_page(parties, totals, out_dir):
    def block(camp, title):
        rows = "".join(
            f'<div class="grow"><span><a href="parties/{e(p["id"])}.html">'
            f'{e(p.get("short") or p["id"])}</a> <span class="meta">{e(p.get("country",""))}</span></span>'
            f'<span class="meta">{totals.get(p["id"],0)}</span></div>'
            for p in sorted(parties, key=lambda x: (x.get("country",""), x.get("short","")))
            if p.get("camp") == camp)
        return f'<h2>{title}</h2><div class="grid">{rows}</div>'

    body = (f'<h1>Parties</h1><p class="lede">{len(parties)} parties across '
            f'{len({p.get("country") for p in parties if p.get("country")})} countries. '
            'The figure is everything collected to date.</p>'
            + block("right", "Far right and radical right")
            + block("left", "Radical left"))
    path = os.path.join(out_dir, "parties.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Parties", body, subtitle=f"{len(parties)} monitored"))
    return path


def home_page(latest, index, out_dir):
    if not latest:
        body = ('<h1>Radical Party Watch</h1>'
                '<div class="box dashed"><p>No issues yet.</p>'
                '<p class="meta">Run <code>python run.py weekly</code> to build the first one.</p></div>')
    else:
        recent = "".join(
            f'<div class="grow"><span><a href="issues/{e(r["week"])}.html">{e(r["week"])}</a> '
            f'<span class="meta">{e(r["range"])}</span></span>'
            f'<span class="meta">{r["items"]}</span></div>' for r in index[:8])
        body = f"""<h1>Radical Party Watch</h1>
<p class="lede">A weekly record of what monitored European and Israeli radical-left and
far/right radical-right parties said and did, with the original-language sentence and an
archived source behind every claim.</p>
<div class="box"><h4>Latest issue · week {e(latest['week'])}</h4>
<p>{e(latest['headline'])}</p>
<p><a href="issues/{e(latest['week'])}.html">Read week {e(latest['week'])}</a>
 · <a href="data/{e(latest['week'])}.csv">coding rows (CSV)</a></p></div>
<h2>Recent</h2><div class="grid">{recent}</div>
<p style="margin-top:1.4rem"><a href="archive.html">All {len(index)} issues</a>
 · <a href="parties.html">Party pages</a></p>"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Radical Party Watch", body,
                       subtitle=f"{len(index)} issues"))
    return path


def corpus_json(items, out_dir):
    """Ship the corpus as JSON so the report builder runs entirely in the
    browser. Sharded by year, and interpretations kept in a separate file:
    metadata and summaries are small, analytical notes are not, and most
    reports do not need them. The report page fetches only the years the
    requested range touches.
    """
    os.makedirs(os.path.join(out_dir, "corpus"), exist_ok=True)
    by_year, interp_by_year = {}, {}
    for it in items:
        a = it.get("analysis") or {}
        if not a.get("relevant"):
            continue
        year = (it.get("published") or it.get("collected_at") or "")[:4] or "unknown"
        by_year.setdefault(year, []).append({
            "id": it["id"], "w": it.get("week"), "d": (it.get("published") or "")[:10],
            "p": it["party_id"], "pn": it.get("party_name"), "c": it.get("country"),
            "cm": it.get("camp"), "pr": it.get("provenance"),
            "prr": it.get("provenance_rank"), "o": it.get("outlet"),
            "u": it.get("url"), "au": it.get("archive_url"),
            "t": a.get("topics") or [], "ac": a.get("actors") or [],
            "s": a.get("summary", ""), "cf": a.get("confidence"),
            "rtl": bool(it.get("rtl")),
            "q": [{"o": q.get("original", ""), "t": q.get("translation", ""),
                   "sp": q.get("speaker", "")}
                  for q in (a.get("quotes") or []) if q.get("original")],
            "cd": it.get("coded"),
        })
        ip = it.get("interpretation") or {}
        if ip.get("reading") or ip.get("explanation"):
            interp_by_year.setdefault(year, {})[it["id"]] = {
                "sg": ip.get("significance"), "ex": ip.get("explanation", ""),
                "rd": ip.get("reading", ""), "wn": ip.get("why_now", ""),
                "co": ip.get("continuity"), "cn": ip.get("continuity_note", ""),
                "cp": ip.get("comparison", ""), "wa": ip.get("watch", ""),
                "fw": ip.get("frameworks") or [], "cv": ip.get("caveat", ""),
                "cf": ip.get("confidence"),
            }

    years = sorted(by_year)
    for y in years:
        with open(os.path.join(out_dir, "corpus", f"{y}.json"), "w", encoding="utf-8") as f:
            json.dump(by_year[y], f, ensure_ascii=False, separators=(",", ":"))
        with open(os.path.join(out_dir, "corpus", f"{y}-interp.json"), "w", encoding="utf-8") as f:
            json.dump(interp_by_year.get(y, {}), f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "corpus", "index.json"), "w", encoding="utf-8") as f:
        json.dump({"years": years,
                   "counts": {y: len(by_year[y]) for y in years}}, f)
    return years


def write_assets(out_dir):
    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)
    with open(os.path.join(out_dir, "assets", "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    # Stops GitHub Pages running the output through Jekyll, which would drop
    # any file or directory beginning with an underscore.
    open(os.path.join(out_dir, ".nojekyll"), "w").close()


def write_index_json(index, out_dir):
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)


def copy_export(csv_path, week, out_dir):
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    if os.path.exists(csv_path):
        shutil.copy(csv_path, os.path.join(out_dir, "data", f"{week}.csv"))
