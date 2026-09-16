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
import trends as trend_utils

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
.wrap{max-width:1180px;margin:0 auto;padding:0 1.25rem 5rem}
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
.item-title{font-size:1.05rem;line-height:1.3;margin:.35rem 0 .2rem}
.item-title a{color:var(--ink);text-decoration-thickness:1px;text-underline-offset:2px}

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

/* weekly overview and collapsible report structure */
.weekly-panels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.85rem;
  margin:1.5rem 0 2.2rem}
.weekly-card{border:1px solid var(--hair);border-top:4px solid var(--accent);
  padding:.85rem;background:var(--surface);min-width:0}
.weekly-card h2{font-size:1.05rem;margin:0 0 .55rem;padding:0;border:0}
.weekly-card ul{margin:.2rem 0 0;padding-left:1.1rem}
.weekly-card li{margin:.6rem 0;line-height:1.35}
.weekly-card .desc{display:block;color:#2B3947;font-size:.88rem;margin-top:.15rem}
.weekly-card .pub{display:block;color:var(--muted);font-size:.75rem;margin-top:.12rem}

.action-tag{display:inline-block;font-size:10.5px;line-height:1.25;padding:.12rem .42rem;
  border:1px solid var(--rule);color:var(--accent-dk);background:#F2FAFC;
  border-radius:2px;margin:.1rem .35rem .1rem 0;vertical-align:.08em}
.minute{border:2px solid var(--ink);padding:.9rem 1.05rem;margin:1.25rem 0}
.minute h2,.change-box h2,.watch-box h2{border:0;margin:0 0 .45rem;padding:0;font-size:1.12rem}
.minute ul,.change-list,.watch-list{margin:.3rem 0 0;padding-left:1.2rem}
.minute li,.change-list li,.watch-list li{margin:.55rem 0}
.change-box,.watch-box{background:var(--surface);border-left:4px solid var(--accent);
  padding:.8rem 1rem;margin:1.25rem 0}
.change-kind{font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;
  color:var(--muted);font-weight:600;margin-right:.35rem}
.coverage-strip{display:flex;flex-wrap:wrap;gap:.55rem 1rem;margin:.55rem 0}
.coverage-strip span{font-size:.8rem;color:var(--muted)}
.coverage-strip strong{font-family:'Source Serif 4',Georgia,serif;font-size:1.22rem;
  color:var(--accent-dk);margin-right:.18rem}
.coverage-table{margin-top:.55rem;overflow-x:auto}
.coverage-status{font-weight:600}
.coverage-error{display:block;max-width:38rem;white-space:normal}
.quote-tools,.timeline-tools,.search-tools,.compare-box{display:flex;flex-wrap:wrap;
  align-items:end;gap:.55rem 1rem;padding:.7rem .8rem;background:var(--surface);
  border:1px solid var(--hair);margin:1rem 0}
.quote-tools{justify-content:space-between;align-items:center;padding:.45rem .7rem}
.quote-tools button{border:1px solid var(--hair);background:white;color:var(--ink);
  font:inherit;font-size:.77rem;padding:.25rem .5rem;cursor:pointer}
.quote-tools button.active{border-color:var(--accent);color:var(--accent-dk);font-weight:600}
.quotes-original blockquote .tr{display:none}
.quotes-english blockquote.has-translation .orig{display:none}
.timeline-tools label,.search-tools label,.compare-box label{font-size:.72rem;color:var(--muted)}
.timeline-tools input,.timeline-tools select,.search-tools input,.search-tools select,
.compare-box select{display:block;margin-top:.15rem;padding:.42rem .5rem;border:1px solid var(--hair);
  background:white;color:var(--ink);font:inherit;font-size:.86rem}
.timeline-tools input,.search-tools input{min-width:260px}
details.timeline-period{border-top:2px solid var(--ink);margin:.75rem 0}
details.timeline-period>summary{cursor:pointer;list-style:none;display:flex;
  justify-content:space-between;gap:1rem;padding:.65rem .1rem;font-weight:700}
details.timeline-period>summary::-webkit-details-marker{display:none}
details.timeline-period>summary::before{content:'+';color:var(--accent-dk);width:1rem}
details[open].timeline-period>summary::before{content:'−'}
.timeline-content{padding:0 .2rem .8rem}
.search-result{padding:.8rem 0;border-bottom:1px solid var(--hair)}
.search-result h3{font-size:1rem;margin:0 0 .15rem}
.search-result p{margin:.2rem 0}
.compare-table .pos{color:var(--accent-dk);font-weight:600}
.compare-table .neg{color:#8A4A3A;font-weight:600}
.comparison{overflow-x:auto}
.method-step{display:grid;grid-template-columns:2rem 1fr;gap:.7rem;padding:.65rem 0;
  border-bottom:1px solid var(--hair)}
.method-step .step{font-family:'Source Serif 4',Georgia,serif;font-size:1.35rem;
  color:var(--accent-dk)}

details.country-section{border-top:2px solid var(--ink);margin:1rem 0;background:var(--paper)}
details.country-section>summary,details.party-section>summary,details.reviewed>summary{
  cursor:pointer;list-style:none;display:flex;justify-content:space-between;gap:1rem;
  align-items:baseline}
details.country-section>summary::-webkit-details-marker,
details.party-section>summary::-webkit-details-marker,
details.reviewed>summary::-webkit-details-marker{display:none}
details.country-section>summary{font-size:1.12rem;font-weight:700;padding:.8rem .2rem}
details.country-section>summary::before,details.party-section>summary::before,
details.reviewed>summary::before{content:'+';color:var(--accent-dk);font-weight:700;
  width:1rem;flex:0 0 1rem}
details[open].country-section>summary::before,details[open].party-section>summary::before,
details[open].reviewed>summary::before{content:'−'}
.country-content{padding:0 .2rem 1rem}
details.party-section{border:1px solid var(--hair);margin:.65rem 0;background:var(--surface)}
details.party-section>summary{padding:.65rem .75rem;font-weight:600}
.party-content{padding:.1rem .85rem .9rem;background:var(--paper)}
.party-content h4{margin:1rem 0 .1rem;font-size:.93rem}
.summary-count{margin-left:auto;font-weight:400;color:var(--muted);font-size:.78rem}
ul.link-list{list-style:none;padding:0;margin:.25rem 0}
ul.link-list li{padding:.65rem 0;border-bottom:1px solid var(--hair)}
ul.link-list .link-title{font-weight:600}
ul.link-list .link-meta{display:block;font-size:.76rem;color:var(--muted)}
ul.link-list .link-desc{display:block;font-size:.9rem;color:#2B3947;margin-top:.12rem}
details.reviewed{margin-top:2.4rem;border-top:2px solid var(--ink)}
details.reviewed>summary{font-size:1.25rem;font-weight:700;padding:.8rem .1rem}

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
@media(max-width:850px){.weekly-panels{grid-template-columns:1fr}.wrap{max-width:880px}}
@media(max-width:650px){.timeline-tools input,.search-tools input{min-width:0;width:100%}}
"""

from reportbuilder import REPORT_CSS  # noqa: E402
CSS = CSS + REPORT_CSS



def e(s):
    return html.escape(str(s or ""))


def layout(title, body, depth=0, subtitle=""):
    up = "../" * depth
    page_title = (title if title == "Neil's Parties Report"
                  else f"{title} · Neil's Parties Report")
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{e(page_title)}</title>
<link rel="stylesheet" href="{up}assets/style.css">
</head><body><div class="wrap">
<nav class="top">
  <a class="brand" href="{up}index.html">Neil's Parties Report</a>
  <a href="{up}archive.html">Archive</a>
  <a href="{up}search.html">Search</a>
  <a href="{up}parties.html">Parties</a>
  <a href="{up}speakers.html">Speakers</a>
  <a href="{up}report.html">Report</a>
  <a href="{up}network.html">Network</a>
  <a href="{up}health.html">Health</a>
  <a href="{up}methodology.html">Method</a>
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


def action_tag(item):
    return f'<span class="action-tag">{e(trend_utils.action_type(item))}</span>'


def quote_toolbar():
    return ('<div class="quote-tools"><span class="meta">Quoted text</span>'
            '<span><button type="button" data-quote-mode="both" class="active">Original + English</button> '
            '<button type="button" data-quote-mode="english">English</button> '
            '<button type="button" data-quote-mode="original">Original</button></span></div>')


def item_html(it, show_party=True, cluster_sizes=None):
    a = it.get("analysis") or {}
    cluster_sizes = cluster_sizes or {}
    action = trend_utils.action_type(it)
    direct = "1" if is_party_document(it) else "0"
    search_text = " ".join([
        str(it.get("title") or ""),
        str((it.get("analysis") or {}).get("summary") or ""),
        str(it.get("party_name") or ""),
        action,
    ])
    parts = [f'<article class="item timeline-entry" id="item-{e(it["id"])}" '
             f'data-action="{e(action)}" data-direct="{direct}" '
             f'data-search="{e(search_text.lower())}">'
             f'<div class="rail {e(it.get("camp","right"))}">'
             f'<span class="cc">{e(it.get("country",""))}</span>'
             f'<span>{e((it.get("published") or "")[:10])}</span>'
             f'<a class="anchor" href="#item-{e(it["id"])}" '
             f'title="Permanent link to this item">#</a></div><div>']
    if show_party:
        parts.append(f'<div class="pname">{e(it.get("party_name",""))}'
                     f'<span class="full">{e(it.get("party_full",""))}</span>'
                     f'{prov_tag(it)} {action_tag(it)}</div>')
    else:
        parts.append(f'<div class="meta">{prov_tag(it)} {action_tag(it)}</div>')
    title = it.get("title") or a.get("summary") or "Untitled source"
    if it.get("url"):
        parts.append(f'<h4 class="item-title"><a href="{e(it["url"])}" '
                     f'rel="noreferrer">{e(title)}</a></h4>')
    else:
        parts.append(f'<h4 class="item-title">{e(title)}</h4>')
    summary = a.get("summary") or ""
    if summary and summary.casefold() != str(title).casefold():
        parts.append(f'<p>{e(summary)}</p>')

    for q in (a.get("quotes") or [])[:2]:
        if not q.get("original"):
            continue
        rtl = ' dir="rtl"' if it.get("rtl") else ''
        has_translation = bool(q.get("translation") and q["translation"] != q["original"])
        quote_class = ' class="has-translation"' if has_translation else ''
        parts.append(f'<blockquote{quote_class}{rtl}>')
        parts.append(f'<div class="orig">{e(q["original"])}</div>')
        if has_translation:
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


def is_party_document(item):
    """Direct records get full cards; secondary coverage gets compact links."""
    return trend_utils.is_direct(item)


def compact_link_html(it, show_party=False):
    """One linked title, publication/date line, and brief factual description."""
    a = it.get("analysis") or {}
    title = it.get("title") or a.get("summary") or "Untitled item"
    link = (f'<a class="link-title" href="{e(it["url"])}" rel="noreferrer">{e(title)}</a>'
            if it.get("url") else f'<span class="link-title">{e(title)}</span>')
    source = it.get("outlet") or it.get("source") or it.get("source_type") or "Source"
    party = it.get("party_name") or it.get("party_id") or ""
    meta = " · ".join(x for x in [party if show_party else "", source,
                                   (it.get("published") or "")[:10]] if x)
    desc = str(a.get("summary") or it.get("description") or it.get("why") or "")
    action = trend_utils.action_type(it)
    direct = "1" if is_party_document(it) else "0"
    search_text = " ".join([str(title), str(desc), str(party), action]).lower()
    return (f'<li class="timeline-entry" id="item-{e(it.get("id",""))}" '
            f'data-action="{e(action)}" data-direct="{direct}" '
            f'data-search="{e(search_text)}">{link}'
            f'<span class="link-meta">{action_tag(it)} {e(meta)}</span>'
            + (f'<span class="link-desc">{e(desc)}</span>' if desc and
               desc.casefold() != str(title).casefold() else "")
            + '</li>')


def panel_html(title, rows, item_by_id):
    entries = []
    for row in (rows or [])[:6]:
        item = item_by_id.get(row.get("item_id")) if isinstance(row, dict) else None
        src = item or row
        if not isinstance(src, dict):
            continue
        item_title = src.get("title") or row.get("title") or row.get("line") or "Weekly item"
        url = src.get("url") or row.get("url") or ""
        linked = (f'<a href="{e(url)}" rel="noreferrer">{e(item_title)}</a>'
                  if url else e(item_title))
        source = (src.get("party_name") or src.get("source") or src.get("outlet")
                  or src.get("party_id") or "Source")
        published = (src.get("published") or row.get("published") or "")[:10]
        description = str(row.get("description") or row.get("line")
                          or (src.get("analysis") or {}).get("summary") or "")
        jump = (f' · <a href="#item-{e(item["id"])}">full record</a>' if item else "")
        entries.append(
            f'<li>{linked}<span class="pub">{e(source)}'
            + (f' · {e(published)}' if published else "") + jump + '</span>'
            + (f'<span class="desc">{e(description)}</span>' if description and
               description.casefold() != str(item_title).casefold() else "")
            + '</li>'
        )
    if not entries:
        entries.append('<li><span class="meta">No verified result was retrieved. '
                       'Check Source health before treating this as a quiet week.</span></li>')
    return f'<section class="weekly-card"><h2>{e(title)}</h2><ul>{"".join(entries)}</ul></section>'


def minute_html(rows):
    """Render the deliberately short, evidence-linked issue entry point."""
    entries = []
    for row in (rows or [])[:5]:
        jump = (f'<a href="#item-{e(row.get("item_id"))}">{e(row.get("party"))}</a>'
                if row.get("item_id") else f'<strong>{e(row.get("party"))}</strong>')
        entries.append(f'<li>{jump} {e(row.get("text"))} '
                       f'<span class="action-tag">{e(row.get("action"))}</span></li>')
    if not entries:
        entries.append('<li class="meta">No retained activity was available for a summary.</li>')
    return ('<section class="minute"><h2>The week in one minute</h2>'
            '<p class="meta">The shortest route through the most consequential retained '
            'party activity. Every point opens its supporting record.</p>'
            f'<ul>{"".join(entries)}</ul></section>')


def changes_html(rows, previous_week):
    entries = []
    for row in rows or []:
        party = (f'<a href="#item-{e(row.get("item_id"))}">{e(row.get("party"))}</a>'
                 if row.get("item_id") else f'<strong>{e(row.get("party"))}</strong>')
        entries.append(f'<li><span class="change-kind">{e(row.get("kind"))}</span>'
                       f'{party}: {e(row.get("text"))}</li>')
    if not entries:
        entries.append('<li class="meta">No material change was detected in the retained '
                       'records. Coverage may still have changed.</li>')
    label = f' since {previous_week}' if previous_week else ''
    return (f'<section class="change-box"><h2>What changed{e(label)}</h2>'
            '<p class="meta">A comparison of action types and direct-document volume, not '
            'a claim about ideological movement.</p>'
            f'<ul class="change-list">{"".join(entries)}</ul></section>')


def coverage_html(report):
    report = report or {}
    counts = report.get("counts") or {}
    status_order = [
        "Direct material found", "Outside reporting only", "No dated activity retained",
        "Official source inaccessible", "No archived check", "Search fallback used",
    ]
    figures = [f'<span><strong>{report.get("checked", 0)}/{report.get("total", 0)}</strong> '
               'parties checked</span>']
    figures += [f'<span><strong>{counts.get(status, 0)}</strong> {e(status.lower())}</span>'
                for status in status_order if counts.get(status)]
    rows = []
    for row in report.get("entries") or []:
        fallback = ' · search fallback' if row.get("fallback") else ''
        error = (f'<span class="coverage-error meta">{e(row.get("error"))}</span>'
                 if row.get("error") else '')
        rows.append('<tr>'
                    f'<td><a href="../parties/{e(row.get("party_id"))}.html">'
                    f'{e(row.get("party"))}</a> <span class="meta">{e(row.get("country"))}</span></td>'
                    f'<td class="coverage-status">{e(row.get("status"))}{e(fallback)}</td>'
                    f'<td class="n">{row.get("direct", 0)}</td>'
                    f'<td class="n">{row.get("coverage", 0)}{error}</td></tr>')
    return ('<section><h2>Collection coverage</h2>'
            '<p class="meta">What the collector checked, what it found, and where access '
            'failed. “No activity” is only used when a source was actually checked.</p>'
            f'<div class="coverage-strip">{"".join(figures)}</div>'
            '<details class="coverage-table"><summary>Party-by-party collection record</summary>'
            '<table class="rev"><thead><tr><th>Party</th><th>Result</th>'
            f'<th>Direct</th><th>Coverage</th></tr></thead><tbody>{"".join(rows)}'
            '</tbody></table></details></section>')


def watch_html(rows):
    entries = []
    for row in (rows or [])[:5]:
        evidence = (f'<a href="#item-{e(row.get("item_id"))}">{e(row.get("party"))}</a>'
                    if row.get("item_id") else f'<strong>{e(row.get("party"))}</strong>')
        entries.append(f'<li>{evidence}: {e(row.get("text"))} '
                       f'<span class="action-tag">{e(row.get("action"))}</span></li>')
    if not entries:
        entries.append('<li class="meta">No evidence-linked watchpoint was generated.</li>')
    return ('<section class="watch-box"><h2>Watch next week</h2>'
            '<p class="meta">Evidence-linked follow-ups, not a calendar prediction unless '
            'the source itself supplied a date.</p>'
            f'<ul class="watch-list">{"".join(entries)}</ul></section>')


def quote_script(extra=""):
    """Shared original/translation preference, kept locally in the browser."""
    return f"""<script>
function setQuoteMode(mode){{
  document.body.classList.remove('quotes-both','quotes-english','quotes-original');
  document.body.classList.add('quotes-'+mode);
  document.querySelectorAll('[data-quote-mode]').forEach(b=>b.classList.toggle('active',b.dataset.quoteMode===mode));
  try{{localStorage.setItem('npr-quote-mode',mode)}}catch(_e){{}}
}}
document.querySelectorAll('[data-quote-mode]').forEach(b=>b.addEventListener('click',()=>setQuoteMode(b.dataset.quoteMode)));
let savedMode='both';try{{savedMode=localStorage.getItem('npr-quote-mode')||'both'}}catch(_e){{}}
setQuoteMode(['both','english','original'].includes(savedMode)?savedMode:'both');
{extra}
</script>"""


# ------------------------------------------------------------- pages

def issue_page(week, items, overview, briefings, country_names, parties,
               absences, cluster_sizes, out_dir,
               all_items=None, page_changes=None,
               editors_cut=None, world=None, highlights=None, reading=None,
               week_range="", retractions=None, minute=None, changes=None,
               coverage=None, watch=None, previous_week=""):
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
    body.append(quote_toolbar())
    body.append(minute_html(minute))

    # Three short lists share one row. Highlights are drawn from monitored
    # party activity; the other two are linked external context.
    item_by_id = {i["id"]: i for i in relevant}
    body.append('<div class="weekly-panels">')
    body.append(panel_html("Highlights", highlights, item_by_id))
    body.append(panel_html("This week in the world", world, item_by_id))
    body.append(panel_html("Worth reading", reading, item_by_id))
    body.append('</div>')
    if overview:
        body.append(f'<p class="brief"><strong>The monitored week:</strong> {e(overview)}</p>')

    body.append(changes_html(changes, previous_week))
    body.append(coverage_html(coverage))
    body.append(watch_html(watch))

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

    # Country and party sections are collapsed by default so the direct
    # documents remain readable even in a high-volume week.
    body.append('<h2>By country</h2>')
    codes = sorted({p.get("country") for p in parties if p.get("country")}
                   | {i.get("country") for i in relevant if i.get("country")})
    for code in codes:
        here = [i for i in relevant if i.get("country") == code]
        direct_here = [i for i in here if is_party_document(i)]
        body.append('<details class="country-section"><summary>'
                    f'<span><span class="cc">{e(code)}</span> '
                    f'{e(country_names.get(code, code))}</span>'
                    f'<span class="summary-count">{len(direct_here)} direct records · '
                    f'{len(here)} total items</span></summary><div class="country-content">')
        if briefings.get(code):
            body.append(f'<p class="brief">{e(briefings[code])}</p>')
        for ab in [a for a in absences if a.get("country") == code]:
            body.append(f'<div class="box"><h4>{e(ab["occasion"])} · {e(ab["date"])}</h4>'
                        f'<p class="meta">Engaged: {e(", ".join(ab["spoke"]) or "none")}. '
                        f'Silent: {e(", ".join(ab["silent_names"]) or "none")}.</p></div>')

        country_parties = sorted([p for p in parties if p.get("country") == code],
                                 key=lambda p: p.get("short") or p["id"])
        for p in country_parties:
            pid = p["id"]
            mine = [i for i in here if i["party_id"] == pid]
            direct = sorted([i for i in mine if is_party_document(i)],
                            key=lambda x: x.get("published") or "", reverse=True)
            coverage = sorted([i for i in mine if not is_party_document(i)],
                              key=lambda x: x.get("published") or "", reverse=True)
            body.append('<details class="party-section"><summary>'
                        f'<span><a href="../parties/{e(pid)}.html">'
                        f'{e(p.get("short") or pid)}</a> '
                        f'<span class="meta">{e(p.get("name", ""))}</span></span>'
                        f'<span class="summary-count">{len(direct)} direct · '
                        f'{len(coverage)} coverage</span></summary><div class="party-content">')
            if direct:
                body.append('<h4>Party documents and direct records</h4>')
                for item in direct:
                    body.append(item_html(item, show_party=False,
                                          cluster_sizes=cluster_sizes))
            if coverage:
                body.append('<h4>Other reporting and context</h4><ul class="link-list">')
                for item in coverage:
                    body.append(compact_link_html(item))
                body.append('</ul>')
            if not mine:
                site = (f' <a href="{e(p["site"])}" rel="noreferrer">Check official site</a>.'
                        if p.get("site") else "")
                body.append('<p class="meta">No substantive activity was retained for this '
                            f'week.{site} Collection attempts remain visible on Source health.</p>')
            elif not direct:
                body.append('<p class="meta">No direct party document was captured; the linked '
                            'items above are secondary coverage.</p>')
            body.append('</div></details>')
        body.append('</div></details>')

    # Audit trail is present, but no longer overwhelms the weekly findings.
    body.append('<details class="reviewed"><summary><span>Everything reviewed</span>'
                f'<span class="summary-count">{len(all_items)} checked · '
                f'{len(relevant)} retained</span></summary>'
                '<p class="meta">Open this audit trail to inspect what was retained or dropped.</p>'
                '<table class="rev"><thead><tr><th>Party</th><th>Date</th><th>Source</th>'
                '<th>Item</th><th>Status</th></tr></thead><tbody>')
    for it in sorted(all_items, key=lambda x: (x.get("party_id") or "", x.get("published") or "")):
        a = it.get("analysis") or {}
        keep = bool(a.get("relevant"))
        if keep:
            status = f'<a href="#item-{e(it["id"])}">in issue</a>'
        elif a.get("triaged_out"):
            # Older analyses described rejection against the retired topic
            # scheme. Keep the audit decision without leaking those obsolete
            # labels back into a newly generated report.
            status = "not retained"
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
    body.append('</tbody></table></details>')
    issue_js = """
function revealLinkedItem(){
  if(!location.hash)return;
  const target=document.querySelector(location.hash);
  if(!target)return;
  for(const section of target.closest('.country-section')?[target.closest('.country-section'),target.closest('.party-section')]:[]){
    if(section)section.open=true;
  }
}
window.addEventListener('hashchange',revealLinkedItem);
revealLinkedItem();
"""
    body.append(quote_script(issue_js))

    os.makedirs(os.path.join(out_dir, "issues"), exist_ok=True)
    path = os.path.join(out_dir, "issues", f"{week}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout(f"Week {week}", "".join(body), depth=1, subtitle=week))
    return path


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
                    f'<tr><td>{e(lab)}</td>'
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
                body.append(f'<tr><td>{e(lab)}</td>'
                            f'<td class="n kap">{v["raw_agreement"]:.0%}</td>'
                            f'<td class="n kap">{_kap(v["kappa"])}</td></tr>')
            body.append('</tbody></table>')
    path = os.path.join(out_dir, "reliability.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Reliability", "".join(body), subtitle=f"{len(reports)} round(s)"))
    return path


def party_page(party, series, items, out_dir):
    camp = party.get("camp", "right")
    site = (f'<a href="{e(party["site"])}" rel="noreferrer">official website</a>'
            if party.get("site") else "no official website configured")
    body = [f'<h1>{e(party.get("name"))}</h1>',
            f'<p class="meta">{e(party.get("country",""))} · '
            f'{"radical left" if camp == "left" else "far right"}'
            f' · {site}</p>']

    total_all = len(items)
    direct = [i for i in items if is_party_document(i)]
    coverage = [i for i in items if not is_party_document(i)]
    quoted = sum(1 for i in items
                 if ((i.get("analysis") or {}).get("quotes") or []))
    body.append('<div class="statline">'
                f'<div class="stat"><div class="v">{total_all}</div>'
                f'<div class="k">items on file</div></div>'
                f'<div class="stat"><div class="v">{len(direct)}</div>'
                f'<div class="k">direct records</div></div>'
                f'<div class="stat"><div class="v">{quoted}</div>'
                f'<div class="k">with a captured quote</div></div></div>')
    body.append(quote_toolbar())
    actions = sorted({trend_utils.action_type(it) for it in items})
    body.append('<div class="timeline-tools">'
                '<label>Search this party<input id="timeline-query" type="search" '
                'placeholder="words in titles and summaries"></label>'
                '<label>Action type<select id="timeline-action"><option value="">All actions</option>'
                + ''.join(f'<option>{e(action)}</option>' for action in actions)
                + '</select></label><label>Evidence<select id="timeline-source">'
                  '<option value="">All retained items</option>'
                  '<option value="direct">Direct records only</option>'
                  '<option value="coverage">Outside reporting only</option>'
                  '</select></label></div>')

    # A party's archive is a week-by-week timeline. Direct documents remain the
    # full cards; contextual coverage remains a compact linked index.
    by_week = {}
    for it in items:
        period = it.get("week") or (it.get("published") or "Undated")[:7]
        by_week.setdefault(period, []).append(it)
    body.append('<h2>Activity timeline</h2>')
    for n, period in enumerate(sorted(by_week, reverse=True)):
        rows = by_week[period]
        period_direct = sorted([it for it in rows if is_party_document(it)],
                               key=lambda x: x.get("published") or "", reverse=True)
        period_coverage = sorted([it for it in rows if not is_party_document(it)],
                                 key=lambda x: x.get("published") or "", reverse=True)
        body.append(f'<details class="timeline-period" {"open" if n == 0 else ""}>'
                    f'<summary><span>{e(period)}</span><span class="summary-count">'
                    f'{len(period_direct)} direct · {len(period_coverage)} coverage</span></summary>'
                    '<div class="timeline-content">')
        if period_direct:
            body.append('<h3>Party documents and direct records</h3>')
            for it in period_direct:
                body.append(item_html(it, show_party=False))
        if period_coverage:
            body.append('<h3>Other reporting and context</h3><ul class="link-list">')
            for it in period_coverage:
                body.append(compact_link_html(it))
            body.append('</ul>')
        body.append('</div></details>')

    if not direct and items:
        body.append('<div class="box dashed"><p>No direct records captured yet.</p>'
                    '<p class="meta">The timeline contains outside reporting only. Check '
                    'Source health to distinguish a quiet period from a blocked source.</p></div>')
    if not items:
        body.append('<div class="box dashed"><p>Nothing collected yet.</p>'
                    '<p class="meta">A persistent blank here means the source '
                    'configuration needs attention rather than the party being quiet.</p></div>')

    timeline_js = """
const timelineQuery=document.getElementById('timeline-query');
const timelineAction=document.getElementById('timeline-action');
const timelineSource=document.getElementById('timeline-source');
function filterTimeline(){
  const q=(timelineQuery?.value||'').trim().toLocaleLowerCase();
  const action=timelineAction?.value||'',source=timelineSource?.value||'';
  document.querySelectorAll('.timeline-entry').forEach(row=>{
    const direct=row.dataset.direct==='1';
    const visible=(!q||(row.dataset.search||'').includes(q))&&
      (!action||row.dataset.action===action)&&
      (!source||(source==='direct'?direct:!direct));
    row.hidden=!visible;
  });
  document.querySelectorAll('.timeline-period').forEach(period=>{
    const any=[...period.querySelectorAll('.timeline-entry')].some(row=>!row.hidden);
    period.hidden=!any;
    if(any&&(q||action||source))period.open=true;
  });
}
[timelineQuery,timelineAction,timelineSource].forEach(control=>control?.addEventListener('input',filterTimeline));
"""
    body.append(quote_script(timeline_js))

    os.makedirs(os.path.join(out_dir, "parties"), exist_ok=True)
    path = os.path.join(out_dir, "parties", f"{party['id']}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout(party.get("name"), "".join(body), depth=1,
                       subtitle=party.get("country", "")))
    return path


def search_page(out_dir):
    """Full-text search across the compact public corpus."""
    body = r'''
<h1>Search the archive</h1>
<p class="lede">Search titles, summaries, parties, named actors, action types, and captured
quotes across every report. Results link back to the complete evidence record.</p>
<div class="search-tools">
  <label>Words<input id="search-query" type="search" placeholder="e.g. coalition, protest, deportation"></label>
  <label>Party<select id="search-party"><option value="">All parties</option></select></label>
  <label>Action<select id="search-action"><option value="">All actions</option></select></label>
  <label>Evidence<select id="search-source"><option value="">All evidence</option>
    <option value="direct">Direct records</option><option value="coverage">Outside reporting</option></select></label>
</div>
<p id="search-status" class="meta">Loading archive…</p>
<div id="search-results"></div>
<script>
const searchEl=id=>document.getElementById(id);
const searchEsc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let searchCorpus=[];
function searchable(x){return [x.ti,x.s,x.pn,x.p,x.c,x.at,x.o,...(x.ac||[]),...(x.q||[]).flatMap(q=>[q.o,q.t,q.sp])].join(' ').toLocaleLowerCase()}
function renderSearch(){
  const q=searchEl('search-query').value.trim().toLocaleLowerCase();
  const party=searchEl('search-party').value,action=searchEl('search-action').value,source=searchEl('search-source').value;
  const found=searchCorpus.filter(x=>(!q||searchable(x).includes(q))&&(!party||x.p===party)&&
    (!action||x.at===action)&&(!source||(source==='direct'?x.di:!x.di)))
    .sort((a,b)=>(b.d||'').localeCompare(a.d||'')).slice(0,100);
  searchEl('search-status').textContent=`${found.length}${found.length===100?' shown':''} matching record${found.length===1?'':'s'}.`;
  searchEl('search-results').innerHTML=found.length?found.map(x=>{
    const issue=x.w?`issues/${encodeURIComponent(x.w)}.html#item-${encodeURIComponent(x.id)}`:'';
    const title=x.ti||x.s||'Untitled item';
    return `<article class="search-result"><h3>${issue?`<a href="${issue}">${searchEsc(title)}</a>`:searchEsc(title)}</h3>
      <p class="meta"><span class="action-tag">${searchEsc(x.at||'Recorded development')}</span>
      ${searchEsc(x.pn||x.p)} · ${searchEsc(x.c)} · ${searchEsc(x.d)} · ${x.di?'direct record':'outside reporting'}</p>
      <p>${searchEsc(x.s||'')}</p>${x.u?`<p class="meta"><a href="${searchEsc(x.u)}" rel="noreferrer">original source</a></p>`:''}</article>`;
  }).join(''):'<div class="box dashed">No records match. Try fewer words or clear a filter.</div>';
}
async function loadSearch(){
  try{
    const idx=await fetch('corpus/index.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json()});
    searchCorpus=(await Promise.all(idx.years.map(y=>fetch(`corpus/${y}.json`).then(r=>r.json())))).flat();
    const parties=[...new Map(searchCorpus.map(x=>[x.p,x.pn||x.p])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
    parties.forEach(([id,name])=>searchEl('search-party').insertAdjacentHTML('beforeend',`<option value="${searchEsc(id)}">${searchEsc(name)}</option>`));
    [...new Set(searchCorpus.map(x=>x.at).filter(Boolean))].sort().forEach(action=>searchEl('search-action').insertAdjacentHTML('beforeend',`<option>${searchEsc(action)}</option>`));
    renderSearch();
  }catch(err){searchEl('search-status').textContent='The archive could not be loaded. Open this page through the GitHub Pages URL.'}
}
['search-query','search-party','search-action','search-source'].forEach(id=>searchEl(id).addEventListener('input',renderSearch));
loadSearch();
</script>'''
    path = os.path.join(out_dir, "search.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Search", body, subtitle="full archive"))
    return path


def methodology_page(parties, prompt_versions, revisions, out_dir):
    """Plain-language method, limitations, and a visible revision history."""
    body = ['<h1>Methodology and revision log</h1>',
            '<p class="lede">This is an evidence-led monitoring archive. It records what '
            'the listed parties did and published; it does not infer that absence from the '
            'archive means political inactivity.</p>',
            '<h2>How one weekly report is made</h2>']
    steps = [
        ("Collect", "Check configured party sites and feeds, official parliamentary records, and configured discovery searches."),
        ("Preserve", "Store the source URL and a local text snapshot so later deletion or editing does not erase the record."),
        ("Screen", "Retain dated, substantive material about a monitored party; keep rejected rows visible in the review audit."),
        ("Describe", "Extract a factual summary, named actors, verbatim quotations, and an observable action type."),
        ("Present", "Give direct party documents full evidence cards; present outside reporting as linked context."),
        ("Compare", "Compare retained action types and direct-document volume with the preceding archived week."),
    ]
    for n, (title, text) in enumerate(steps, 1):
        body.append(f'<div class="method-step"><div class="step">{n}</div><div>'
                    f'<strong>{e(title)}</strong><p>{e(text)}</p></div></div>')
    body += [
        '<h2>What the labels mean</h2>',
        '<p><strong>Direct record</strong> means a party-controlled source, a named leader’s '
        'direct channel, or an official parliamentary record. <strong>Outside reporting</strong> '
        'means journalism or another contextual source. Action labels describe the form of an '
        'observable act, such as a parliamentary intervention or mobilisation; they are not '
        'ideological topic labels.</p>',
        '<h2>Coverage and limits</h2>',
        '<p>Collection coverage is reported party by party. “No dated activity retained” means '
        'the configured source was checked but produced no qualifying dated record. “Official '
        'source inaccessible” means the check failed. “No archived check” means this database '
        'contains no collection log for that party and week. Search fallback use is shown '
        'separately. Automated collection can still miss posts, dynamic pages, deleted content, '
        'and material on unconfigured platforms.</p>',
        '<p>Translations and model-written interpretations can contain errors. Original text, '
        'source links, prompt-version records, confidence labels, and the audit trail exist so '
        'a reader can verify the evidence. Week-over-week change describes the retained archive, '
        'not the totality of a party’s behaviour.</p>',
        '<h2>Monitored roster</h2>',
        f'<p class="meta">{len(parties)} parties are configured. Inclusion is a research-roster '
        'decision, not an endorsement or a claim that every party is equivalent.</p>',
        '<ul class="link-list">']
    for party in sorted(parties, key=lambda p: (p.get("country", ""), p.get("short", ""))):
        body.append(f'<li><a class="link-title" href="parties/{e(party["id"])}.html">'
                    f'{e(party.get("short") or party.get("name"))}</a>'
                    f'<span class="link-meta">{e(party.get("country"))} · '
                    f'{e(party.get("name"))}</span></li>')
    body.append('</ul><h2>Analysis versions in this archive</h2>'
                '<table class="rev"><thead><tr><th>Stage</th><th>Model</th><th>Prompt</th>'
                '<th>Records</th><th>First run</th><th>Latest run</th></tr></thead><tbody>')
    for row in prompt_versions:
        body.append(f'<tr><td>{e(row.get("stage"))}</td><td>{e(row.get("model"))}</td>'
                    f'<td>{e(row.get("prompt_ver"))}</td><td class="n">{row.get("n", 0)}</td>'
                    f'<td class="n">{e((row.get("first") or "")[:10])}</td>'
                    f'<td class="n">{e((row.get("last") or "")[:10])}</td></tr>')
    body.append('</tbody></table><h2>Revision log</h2>')
    if not revisions:
        body.append('<p class="meta">No revisions have been recorded yet.</p>')
    for revision in revisions:
        body.append(f'<h3>{e(revision.get("date"))} · {e(revision.get("title"))}</h3><ul>')
        for change in revision.get("changes") or []:
            body.append(f'<li>{e(change)}</li>')
        body.append('</ul>')
    path = os.path.join(out_dir, "methodology.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Methodology", "".join(body), subtitle="method and changes"))
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
        body.append(
            f'<div class="spk"><span>'
            f'<a href="speakers/{e(slug(key))}.html">{e(rec["display"])}</a> '
            f'<span class="meta">{e(", ".join(rec["parties"]))}</span></span>'
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
<p class="lede">Every issue built, oldest at the bottom. The presentation can be
rebuilt when the report format improves; captured source text and links remain
in the research database.</p>
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
        body = ("<h1>Neil's Parties Report</h1>"
                '<div class="box dashed"><p>No issues yet.</p>'
                '<p class="meta">Run <code>python run.py weekly</code> to build the first one.</p></div>')
    else:
        recent = "".join(
            f'<div class="grow"><span><a href="issues/{e(r["week"])}.html">{e(r["week"])}</a> '
            f'<span class="meta">{e(r["range"])}</span></span>'
            f'<span class="meta">{r["items"]}</span></div>' for r in index[:8])
        body = f"""<h1>Neil's Parties Report</h1>
<p class="lede">A weekly record of what monitored European and Israeli radical-left and
far/right radical-right parties did and said. Direct party documents are shown first;
reporting and broader context stay as short, clearly attributed links.</p>
<div class="box"><h4>Latest issue · week {e(latest['week'])}</h4>
<p>{e(latest['headline'])}</p>
<p><a href="issues/{e(latest['week'])}.html">Read week {e(latest['week'])}</a>
 · <a href="data/{e(latest['week'])}.csv">coding rows (CSV)</a></p></div>
<h2>Recent</h2><div class="grid">{recent}</div>
<p style="margin-top:1.4rem"><a href="archive.html">All {len(index)} issues</a>
 · <a href="parties.html">Party pages</a></p>"""
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Neil's Parties Report", body,
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
            "ti": it.get("title", ""), "di": is_party_document(it),
            "ac": a.get("actors") or [], "s": a.get("summary", ""),
            "at": trend_utils.action_type(it),
            "cf": a.get("confidence"),
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
