"""Browser-only report builder generated with the static portal."""

from __future__ import annotations

import os


REPORT_CSS = r"""
.builder{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;
  padding:1rem;background:var(--surface);border:1px solid var(--hair);margin:1rem 0}
.builder label{font-size:12px;color:var(--muted)}
.builder input,.builder select{display:block;width:100%;margin-top:.2rem;padding:.5rem;
  border:1px solid var(--hair);background:white;color:var(--ink);font:inherit;font-size:14px}
.builder .wide{grid-column:1/-1}.builder .actions{grid-column:1/-1;display:flex;gap:.6rem;flex-wrap:wrap}
.builder button{border:1px solid var(--ink);background:var(--ink);color:white;padding:.5rem .8rem;
  font:inherit;cursor:pointer}.builder button.secondary{background:white;color:var(--ink)}
.history-action{margin:1rem 0}.history-action a{font-weight:700}
.report-group{margin:2rem 0}.report-card{padding:.8rem 0;border-bottom:1px solid var(--hair)}
.report-card h4{margin:0}.report-card .summary{margin:.3rem 0}.report-empty{padding:1rem;border:1px dashed var(--hair)}
@media(max-width:600px){.builder{grid-template-columns:1fr}.builder .wide,.builder .actions{grid-column:1}}
@media print{nav.top,.builder,.no-print,footer{display:none!important}.wrap{max-width:none;padding:0}}
"""


BODY = r"""
<h1>Build a report</h1>
<p class="lede">Filter the archived items, choose how to group them, then print to PDF or
download the matching rows as CSV. Everything runs in your browser.</p>
<p class="meta">Corpus configured for __PARTIES__ parties in __COUNTRIES__ countries.</p>
<div class="box history-action no-print">
  <h4>Need dates that are not in the archive?</h4>
  <p>The builder filters existing data. Historical collection runs privately inside your
  GitHub repository, where the API key stays protected.</p>
  <p><a id="history-link" hidden target="_blank" rel="noreferrer">Open historical collection in GitHub Actions →</a></p>
</div>

<form class="builder" id="builder">
  <label>From<input type="date" id="from"></label>
  <label>To<input type="date" id="to"></label>
  <label>Country<select id="country"><option value="">All countries</option></select></label>
  <label>Party<select id="party"><option value="">All parties</option></select></label>
  <label>Theme<select id="theme"><option value="">All themes</option>
    <option value="israel_palestine">Israel and Palestine</option>
    <option value="jews_antisemitism">Jews and antisemitism</option>
    <option value="immigration">Immigration</option></select></label>
  <label>Camp<select id="camp"><option value="">Both camps</option>
    <option value="left">Radical left</option><option value="right">Far/right radical right</option></select></label>
  <label>Group by<select id="group"><option value="country">Country</option>
    <option value="party">Party</option><option value="theme">Theme</option>
    <option value="actor">Actor</option><option value="month">Month</option>
    <option value="camp">Camp</option><option value="source">Evidence class</option>
    <option value="none">No grouping</option></select></label>
  <label>Include interpretation<select id="interp"><option value="no">No</option>
    <option value="yes">Yes</option></select></label>
  <label class="wide">Words anywhere<input id="query" type="search" placeholder="e.g. deportation, coalition, Gaza"></label>
  <div class="actions"><button type="submit">Build report</button>
    <button type="button" class="secondary" id="csv">Download CSV</button>
    <button type="button" class="secondary" onclick="window.print()">Print / save PDF</button></div>
</form>
<div id="status" class="meta">Loading corpus…</div>
<div id="report"></div>

<script>
const el=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={israel_palestine:'Israel and Palestine',jews_antisemitism:'Jews and antisemitism',immigration:'Immigration'};
let corpus=[], interps={}, shown=[];

function setHistoryLink(){
  const suffix='.github.io';
  if(!location.hostname.endsWith(suffix))return;
  const owner=location.hostname.slice(0,-suffix.length);
  const parts=location.pathname.split('/').filter(Boolean);
  const repo=parts.length&& !parts[0].endsWith('.html')?parts[0]:`${owner}.github.io`;
  const link=el('history-link');
  link.href=`https://github.com/${owner}/${repo}/actions/workflows/backfill.yml`;
  link.hidden=false;
}

async function loadCorpus(){
  try{
    const idx=await fetch('corpus/index.json').then(r=>{if(!r.ok)throw Error(r.status);return r.json()});
    const chunks=await Promise.all(idx.years.map(y=>fetch(`corpus/${y}.json`).then(r=>r.json())));
    corpus=chunks.flat();
    const countries=[...new Set(corpus.map(x=>x.c).filter(Boolean))].sort();
    const parties=[...new Map(corpus.map(x=>[x.p,x.pn||x.p])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
    countries.forEach(x=>el('country').insertAdjacentHTML('beforeend',`<option>${esc(x)}</option>`));
    parties.forEach(([id,name])=>el('party').insertAdjacentHTML('beforeend',`<option value="${esc(id)}">${esc(name)}</option>`));
    const dates=corpus.map(x=>x.d).filter(Boolean).sort();
    if(dates.length){el('from').value=dates[0];el('to').value=dates.at(-1)}
    el('status').textContent=`${corpus.length} archived items loaded.`;
    build();
  }catch(err){
    el('status').innerHTML='Could not load the corpus. This page works at the GitHub Pages URL; for local use start <code>python -m http.server</code> inside <code>site/</code>.';
  }
}

async function ensureInterps(){
  if(el('interp').value!=='yes'||Object.keys(interps).length)return;
  const idx=await fetch('corpus/index.json').then(r=>r.json());
  const rows=await Promise.all(idx.years.map(y=>fetch(`corpus/${y}-interp.json`).then(r=>r.json())));
  rows.forEach(x=>Object.assign(interps,x));
}

function selected(){
  const from=el('from').value,to=el('to').value,c=el('country').value,p=el('party').value;
  const theme=el('theme').value,camp=el('camp').value,q=el('query').value.trim().toLowerCase();
  return corpus.filter(x=>(!from||x.d>=from)&&(!to||x.d<=to)&&(!c||x.c===c)&&(!p||x.p===p)&&
    (!theme||x.t.includes(theme))&&(!camp||x.cm===camp)&&(!q||JSON.stringify(x).toLowerCase().includes(q)));
}

function groupKeys(x){
  switch(el('group').value){
    case 'country':return[x.c||'—'];case 'party':return[x.pn||x.p];case 'theme':return x.t.length?x.t.map(t=>labels[t]||t):['No tagged theme'];
    case 'actor':return x.ac.length?x.ac:['No named actor'];case 'month':return[x.d.slice(0,7)||'—'];
    case 'camp':return[x.cm==='left'?'Radical left':'Far/right radical right'];case 'source':return[x.pr||'—'];default:return['All items'];
  }
}

function card(x){
  const qs=(x.q||[]).map(q=>`<blockquote${x.rtl?' dir="rtl"':''}><div class="orig">${esc(q.o)}</div>${q.t?`<div class="tr">${esc(q.t)}</div>`:''}</blockquote>`).join('');
  const ip=interps[x.id];
  const note=ip&&el('interp').value==='yes'?`<div class="interp sig-${esc(ip.sg||'routine')}"><div class="ih">Interpretation — model inference, not evidence</div><p>${esc(ip.rd||'')}</p></div>`:'';
  return `<article class="report-card"><h4>${esc(x.pn||x.p)} <span class="meta">${esc(x.c)} · ${esc(x.d)}</span></h4>
    <p class="summary">${esc(x.s)}</p>${qs}${note}<p class="meta">${(x.t||[]).map(t=>esc(labels[t]||t)).join(' · ')}
    ${x.u?` · <a href="${esc(x.u)}" rel="noreferrer">source</a>`:''}${x.au?` · <a href="${esc(x.au)}" rel="noreferrer">archived</a>`:''}</p></article>`;
}

async function build(ev){
  if(ev)ev.preventDefault();
  await ensureInterps();shown=selected();
  const groups=new Map();shown.forEach(x=>groupKeys(x).forEach(k=>{if(!groups.has(k))groups.set(k,[]);groups.get(k).push(x)}));
  const ordered=[...groups.entries()].sort((a,b)=>b[1].length-a[1].length||a[0].localeCompare(b[0]));
  el('status').textContent=`${shown.length} matching item${shown.length===1?'':'s'} in ${ordered.length} group${ordered.length===1?'':'s'}.`;
  el('report').innerHTML=ordered.length?ordered.map(([name,rows])=>`<section class="report-group"><h2>${esc(name)} <span class="meta">${rows.length} items</span></h2>${rows.sort((a,b)=>a.d.localeCompare(b.d)).map(card).join('')}</section>`).join(''):
    '<div class="report-empty">No items match. Widen the dates or remove a filter.</div>';
}

function csv(){
  const fields=['date','country','party','camp','provenance','themes','actors','summary','source_url','archive_url'];
  const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';
  const lines=[fields.join(',')].concat(shown.map(x=>[x.d,x.c,x.pn,x.cm,x.pr,x.t.join('; '),x.ac.join('; '),x.s,x.u,x.au].map(quote).join(',')));
  const blob=new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'}),a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download='radical-party-watch-report.csv';a.click();URL.revokeObjectURL(a.href);
}
el('builder').addEventListener('submit',build);el('csv').addEventListener('click',csv);
setHistoryLink();loadCorpus();
</script>
"""


def report_page(out_dir: str, party_count: int, country_count: int) -> str:
    # Local import avoids a module-import cycle: portal imports REPORT_CSS.
    from portal import layout

    os.makedirs(out_dir, exist_ok=True)
    body = BODY.replace("__PARTIES__", str(party_count)).replace("__COUNTRIES__", str(country_count))
    path = os.path.join(out_dir, "report.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(layout("Report builder", body, subtitle="build from the archive"))
    return path
