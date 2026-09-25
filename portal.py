"""Static site generator.

Produces a self-contained portal: latest issue, a permanent archive of every
issue ever built, and a page per party showing that party's whole run rather
than one week of it. No server, no build step, no framework — plain files that
any static host will serve.

Camp colour follows the two roster buckets: cyan for far-left and navy for
far-right. It encodes a real dimension of the data, so
scanning a page tells you the composition of a week before you read a word.
"""

import csv
import html
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from evidence import PROVENANCE
import trends as trend_utils

SITE_NAME = "RAPPORT"
SITE_EXPANSION = "Radicalism and Party Politics: Observation, Reporting and Tracking"
SITE_DESCRIPTION = ("A weekly record of what monitored European and Israeli far-left "
                    "and far-right parties did and said.")
PUBLIC_URL = "https://neilmegas.github.io/radicalneilbar/"

CSS = """
:root{
  --paper:#FCFDFD; --surface:#F3F6F7; --ink:#102432; --muted:#607079;
  --accent:#168EAA; --accent-dk:#08677A; --grey:#87939A;
  --track:#E7ECEE; --rule:#B2D9E2; --hair:#D9E3E6;
  --shadow:0 12px 34px rgba(16,36,50,.11); --soft-shadow:0 3px 14px rgba(16,36,50,.055);
  --radius:6px;
  /* Camps take navy and cyan from the palette. */
  --right:#0A1B2E; --left:#00A3C8;
}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:5.5rem}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  font-size:16px;line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1140px;margin:0 auto;padding:0 1.35rem 5rem}
main{min-height:55vh}
.meta{font-size:12.5px;line-height:1.45;color:var(--muted)}
.num{font-family:Georgia,'Times New Roman',serif;font-variant-numeric:tabular-nums}
a{color:var(--accent-dk);text-underline-offset:.16em} a:hover{color:var(--ink)}
a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible,
select:focus-visible,textarea:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
[dir="rtl"]{text-align:right}
button,input,select,textarea{font:inherit}
button{touch-action:manipulation}
.skip-link{position:fixed;left:1rem;top:.5rem;z-index:1000;transform:translateY(-160%);
  padding:.5rem .75rem;background:var(--ink);color:white;text-decoration:none;font-weight:700}
.skip-link:focus{transform:translateY(0);color:white}

nav.top{border-bottom:1px solid var(--hair);padding:1rem .1rem .85rem;margin-bottom:2rem;
  display:flex;flex-wrap:wrap;gap:.4rem 1rem;align-items:center;position:sticky;top:0;z-index:20;
  background:rgba(252,253,253,.97);backdrop-filter:blur(12px);box-shadow:0 7px 17px -17px rgba(16,36,50,.75)}
nav.top .brand{font-weight:750;font-size:1.18rem;letter-spacing:.035em;
  text-decoration:none;color:var(--ink)}
nav.top a:not(.brand),nav.top summary{font-size:13px;color:var(--muted);text-decoration:none}
nav.top a:not(.brand):hover{color:var(--accent-dk)}
nav.top a[aria-current="page"]{color:var(--ink);font-weight:700}
nav.top .spacer{flex:1}
.nav-menu{position:relative}
.nav-menu summary{cursor:pointer;list-style:none;padding:.28rem .15rem;white-space:nowrap;
  touch-action:manipulation}
.nav-menu summary::-webkit-details-marker{display:none}
.nav-menu summary::after{content:' ▾';font-size:.68em;color:var(--accent-dk)}
.nav-menu[open] summary{color:var(--ink);font-weight:600}
.nav-menu[open] summary::after{content:' ▴'}
.nav-dropdown{position:absolute;left:-.65rem;top:calc(100% + .35rem);min-width:205px;
  padding:.45rem;background:var(--paper);border:1px solid var(--hair);
  box-shadow:var(--shadow);display:grid;z-index:30;border-radius:var(--radius)}
.nav-dropdown a{padding:.42rem .55rem;white-space:nowrap;border-radius:3px}
.nav-dropdown a:hover{background:var(--surface)}
.nav-dropdown-wide{left:auto;right:-.65rem;min-width:440px;
  grid-template-columns:repeat(2,minmax(190px,1fr));gap:.2rem .55rem}
.nav-column{display:grid;align-content:start}
.nav-label{padding:.35rem .55rem .2rem;color:var(--muted);font-size:.62rem;font-weight:700;
  letter-spacing:.08em;text-transform:uppercase}
.brand-lockup{display:flex;flex-direction:column;line-height:1.05;margin-right:.25rem}
.brand-lockup small{font-size:.55rem;color:var(--muted);font-weight:500;
  letter-spacing:.025em;margin-top:.18rem;max-width:235px}

h1{font-family:Georgia,'Times New Roman',serif;font-size:clamp(2.15rem,5.4vw,3rem);
  font-weight:600;letter-spacing:-.025em;line-height:1.04;margin:0 0 .45rem}
h2{font-size:1.28rem;font-weight:700;letter-spacing:-.012em;margin:2.5rem 0 .3rem;
  padding-bottom:.45rem;border-bottom:1px solid var(--rule)}
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
blockquote .orig{font-family:Georgia,'Times New Roman',serif;font-size:1.05rem}
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
.ai-labels{display:flex;flex-wrap:wrap;gap:.25rem;margin:.45rem 0}
.ai-label{display:inline-block;padding:.08rem .38rem;border:1px solid var(--hair);
  color:var(--muted);font-size:10.5px;line-height:1.35;background:var(--surface)}
.ai-label.ai{border-color:var(--accent);color:var(--accent-dk);background:#F2FAFC}
.ai-label.human{border-color:var(--ink);color:var(--ink);background:white}
details.provenance-card{margin-top:.55rem;border:1px solid var(--hair);background:var(--surface)}
details.provenance-card>summary{cursor:pointer;padding:.38rem .55rem;font-size:12px;
  color:var(--accent-dk);font-weight:600}
.provenance-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem .8rem;
  padding:.55rem;border-top:1px solid var(--hair);font-size:.78rem}
.provenance-grid div{min-width:0;overflow-wrap:anywhere}.provenance-grid strong{display:block;
  color:var(--muted);font-size:.66rem;text-transform:uppercase;letter-spacing:.04em}
.confidence-row{display:flex;flex-wrap:wrap;gap:.25rem;margin-top:.25rem}
.confidence-chip{font-size:.67rem;border:1px solid var(--hair);padding:.06rem .3rem;background:white}

/* blocks */
.box{background:var(--surface);border:1px solid var(--hair);padding:1rem 1.08rem;margin:1rem 0;
  border-radius:var(--radius);box-shadow:var(--soft-shadow)}
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
.weekly-card{border:1px solid var(--hair);border-top:3px solid var(--accent);
  padding:.9rem;background:var(--surface);min-width:0;border-radius:var(--radius);
  box-shadow:var(--soft-shadow)}
.weekly-card h2{font-size:1.05rem;margin:0 0 .55rem;padding:0;border:0}
.weekly-card ul{margin:.2rem 0 0;padding-left:1.1rem}
.weekly-card li{margin:.6rem 0;line-height:1.35}
.weekly-card .desc{display:block;color:#2B3947;font-size:.88rem;margin-top:.15rem}
.weekly-card .pub{display:block;color:var(--muted);font-size:.75rem;margin-top:.12rem}

.action-tag{display:inline-block;font-size:10.5px;line-height:1.25;padding:.12rem .42rem;
  border:1px solid var(--rule);color:var(--accent-dk);background:#F2FAFC;
  border-radius:2px;margin:.1rem .35rem .1rem 0;vertical-align:.08em}
.minute{border:1px solid var(--ink);border-left:4px solid var(--ink);padding:.95rem 1.08rem;
  margin:1.25rem 0;border-radius:var(--radius);background:#FFFFFF}
.minute h2,.change-box h2,.watch-box h2{border:0;margin:0 0 .45rem;padding:0;font-size:1.12rem}
.minute ul,.change-list,.watch-list{margin:.3rem 0 0;padding-left:1.2rem}
.minute li,.change-list li,.watch-list li{margin:.55rem 0}
.change-box,.watch-box{background:var(--surface);border:1px solid var(--hair);
  border-left:4px solid var(--accent);padding:.85rem 1rem;margin:1.25rem 0;
  border-radius:var(--radius)}
.change-kind{font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;
  color:var(--muted);font-weight:600;margin-right:.35rem}
.coverage-strip{display:flex;flex-wrap:wrap;gap:.55rem 1rem;margin:.55rem 0}
.coverage-strip span{font-size:.8rem;color:var(--muted)}
.coverage-strip strong{font-family:Georgia,'Times New Roman',serif;font-size:1.22rem;
  color:var(--accent-dk);margin-right:.18rem}
.coverage-table{margin-top:.55rem;overflow-x:auto}
.coverage-status{font-weight:600}
.coverage-error{display:block;max-width:38rem;white-space:normal}
.quote-tools,.timeline-tools,.search-tools,.compare-box{display:flex;flex-wrap:wrap;
  align-items:end;gap:.55rem 1rem;padding:.7rem .8rem;background:var(--surface);
  border:1px solid var(--hair);margin:1rem 0;border-radius:var(--radius)}
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
.profile-links{display:flex;flex-wrap:wrap;gap:.5rem;margin:1rem 0 1.35rem}
.profile-links a{display:inline-block;padding:.38rem .58rem;border:1px solid var(--hair);
  background:var(--surface);font-size:.8rem;text-decoration:none;border-radius:4px}
.party-directory-tools{display:grid;grid-template-columns:minmax(220px,1.5fr) repeat(4,minmax(145px,.7fr));
  gap:.65rem;padding:.85rem;margin:1.1rem 0 1.25rem;border:1px solid var(--hair);
  background:#FFFFFF;border-radius:var(--radius);box-shadow:var(--soft-shadow)}
.party-directory-tools label{font-size:.7rem;color:var(--muted);font-weight:600}
.party-directory-tools input,.party-directory-tools select{display:block;width:100%;margin-top:.2rem;
  min-height:2.45rem;padding:.42rem .5rem;border:1px solid var(--hair);border-radius:4px;
  background:var(--paper);color:var(--ink)}
.party-directory-status{display:flex;align-items:end;justify-content:flex-end;font-size:.76rem;
  color:var(--muted);padding-bottom:.42rem}
.party-directory-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 1.35rem;
  margin-top:.45rem;border-top:2px solid var(--ink)}
.party-row{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:start;gap:.55rem;
  min-width:0;padding:.68rem .35rem;border-bottom:1px solid var(--hair);transition:background .12s ease}
.party-row:hover{background:var(--surface)}
.party-camp-mark{display:block;width:9px;height:9px;margin-top:.35rem;background:var(--right)}
.party-row.left .party-camp-mark{background:var(--left)}
.party-row-main{min-width:0}
.party-row h2{border:0;margin:0 0 .3rem;padding:0;font-size:.9rem;line-height:1.32;font-weight:600}
.party-row h2 a{color:var(--ink);text-decoration-thickness:1px;text-underline-offset:2px}
.party-tags{display:flex;flex-wrap:wrap;gap:.25rem}
.party-tag{display:inline-flex;align-items:center;min-height:1.45rem;padding:.12rem .42rem;
  border:1px solid var(--hair);background:var(--surface);font-size:.65rem;color:#344250;border-radius:999px}
.party-tag.power{border-color:var(--rule);color:var(--accent-dk);background:#F2FAFC;font-weight:600}
.party-row-records{min-width:3.6rem;text-align:right;color:var(--muted);font-size:.65rem;
  white-space:nowrap;padding-top:.05rem}
.party-row-records strong{display:block;color:var(--ink);font-size:.86rem;font-weight:600}
.party-directory-empty{padding:1rem;border:1px dashed var(--hair);color:var(--muted)}
.representation-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem;
  margin:.8rem 0 1rem}
.seat-card{border:1px solid var(--hair);padding:.8rem;background:var(--surface);
  border-radius:var(--radius);box-shadow:var(--soft-shadow)}
.seat-card h3{font-size:.85rem;margin:0 0 .35rem}.seat-card .seat-value{font-family:Georgia,'Times New Roman',serif;
  font-size:1.75rem;line-height:1.1}.seat-bar{height:.45rem;background:var(--track);margin:.55rem 0 .3rem}
.seat-bar i{display:block;height:100%;background:var(--accent);min-width:0}
.seat-pending{color:var(--muted);font-size:.83rem;line-height:1.4}
.election-comparison{display:flex;align-items:flex-end;gap:.65rem;min-height:145px;
  border-bottom:2px solid var(--ink);padding:.75rem .4rem 0;margin:.65rem 0 1rem}
.election-result{flex:1;min-width:72px;text-align:center}.election-result .column{display:block;
  max-width:70px;margin:0 auto .35rem;background:var(--accent);min-height:2px}
.election-result strong,.election-result small{display:block}.election-result small{color:var(--muted);font-size:.68rem}
.research-pages{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;margin:1rem 0}
.research-pages .box{margin:0}
.report-tools{display:flex;flex-wrap:wrap;align-items:center;gap:.45rem .7rem;
  border:1px solid var(--hair);background:var(--surface);padding:.7rem .8rem;margin:1rem 0;
  border-radius:var(--radius)}
.report-tools .citation-text{flex:1 1 420px;font-size:.78rem;color:#2B3947}
.report-tools a,.report-tools button{border:1px solid var(--hair);background:white;color:var(--ink);
  padding:.38rem .58rem;font:inherit;font-size:.76rem;cursor:pointer;text-decoration:none;border-radius:3px}
.report-tools a:hover,.report-tools button:hover{border-color:var(--accent-dk);background:#F2FAFC}
.representation-change{border-left-color:var(--ink)}
.four-week-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.6rem;margin:.65rem 0 1.4rem}
.four-week-card{border:1px solid var(--hair);padding:.7rem;background:var(--surface);min-width:0;
  border-radius:var(--radius)}
.four-week-card h3{font-size:.86rem;margin:0 0 .3rem}.four-week-card ul{margin:.2rem 0 0;padding-left:1rem}
.four-week-card li{font-size:.75rem;line-height:1.35;margin:.42rem 0}.four-week-card .meta{font-size:.67rem}
.method-step{display:grid;grid-template-columns:2rem 1fr;gap:.7rem;padding:.65rem 0;
  border-bottom:1px solid var(--hair)}
.method-step .step{font-family:Georgia,'Times New Roman',serif;font-size:1.35rem;
  color:var(--accent-dk)}
.passport{border:1px solid var(--ink);border-top:4px solid var(--ink);padding:.85rem 1rem;
  margin:1.1rem 0;background:white;border-radius:var(--radius)}
.passport h2{border:0;margin:0 0 .4rem;padding:0;font-size:1.05rem}
.passport-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.55rem}
.passport-grid div{border-top:2px solid var(--rule);padding-top:.35rem;min-width:0}
.passport-grid strong{display:block;font-family:Georgia,'Times New Roman',serif;
  font-size:1.25rem;color:var(--accent-dk);overflow-wrap:anywhere}
.passport-grid span{display:block;font-size:.68rem;color:var(--muted)}
.status-banner{padding:.65rem .8rem;border-left:4px solid var(--grey);background:var(--surface);
  margin:1rem 0}.status-banner.warn{border-left-color:#B46A2F;background:#FFF8F0}
.status-banner.ok{border-left-color:var(--accent)}
.matrix-wrap{overflow:auto;margin:1rem 0}.matrix{border-collapse:collapse;min-width:780px;width:100%}
.matrix th,.matrix td{font-size:.75rem;padding:.35rem .4rem;border:1px solid var(--hair);
  text-align:left}.matrix th{background:var(--surface);position:sticky;top:0}.matrix .zero{color:#9B4B37}
.funnel{display:grid;gap:.35rem;margin:1rem 0;max-width:760px}.funnel-row{display:grid;
  grid-template-columns:9rem 1fr 4rem;gap:.55rem;align-items:center;font-size:.8rem}
.funnel-track{height:.75rem;background:var(--track)}.funnel-track i{display:block;height:100%;background:var(--accent)}
.research-tool{border:1px solid var(--hair);background:var(--surface);padding:.85rem;margin:1rem 0;
  border-radius:var(--radius);box-shadow:var(--soft-shadow)}
.research-tool label{font-size:.72rem;color:var(--muted)}
.research-tool input,.research-tool select,.research-tool textarea{display:block;width:100%;margin-top:.15rem;
  padding:.42rem .5rem;border:1px solid var(--hair);background:white;color:var(--ink);font:inherit;font-size:.86rem}
.tool-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.65rem}
.tool-actions{display:flex;flex-wrap:wrap;gap:.4rem;margin:.7rem 0}
.tool-actions button,.tool-actions a,.download-button{border:1px solid var(--hair);background:white;
  color:var(--ink);padding:.42rem .62rem;font:inherit;font-size:.78rem;cursor:pointer;
  text-decoration:none;border-radius:3px;min-height:2.1rem}
.tool-actions button:hover,.tool-actions a:hover,.download-button:hover,
.profile-links a:hover{border-color:var(--accent-dk);background:#F2FAFC;color:var(--ink)}
.chart-shell{border:1px solid var(--hair);background:white;padding:.6rem;overflow:auto}.chart-shell svg{display:block;width:100%;min-width:600px;height:auto}
.quote-result{padding:.75rem 0;border-bottom:1px solid var(--hair)}
.quote-result blockquote{margin:.35rem 0}.event-card{border-left:4px solid var(--accent);
  padding:.7rem .85rem;margin:.8rem 0;background:var(--surface)}
.event-card h3{margin:0 0 .2rem}.event-card ul{margin:.3rem 0}
.tutorial-step{counter-increment:tutorial;border-top:1px solid var(--hair);padding:.7rem 0}
.tutorial-step::before{content:counter(tutorial);display:inline-grid;place-items:center;width:1.6rem;height:1.6rem;
  border-radius:50%;background:var(--ink);color:white;font-size:.75rem;margin-right:.45rem}
.tutorial{counter-reset:tutorial}.correction-preview{white-space:pre-wrap;background:white;border:1px solid var(--hair);
  padding:.7rem;min-height:9rem;font-size:.8rem}.table-note{font-size:.75rem;color:var(--muted);margin-top:.4rem}

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
details.party-section{border:1px solid var(--hair);margin:.65rem 0;background:var(--surface);
  border-radius:var(--radius);overflow:hidden}
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
table.idx tbody tr:hover,table.rev tbody tr:hover{background:var(--surface)}
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
.stat .v{font-family:Georgia,'Times New Roman',serif;font-size:2rem;line-height:1;
  color:var(--accent);font-variant-numeric:tabular-nums}
.stat .k{font-size:12px;color:var(--muted);margin-top:.2rem}

/* homepage monitoring map */
.research-note{max-width:57rem;margin:.9rem 0 1.35rem;padding:.65rem .8rem;
  border-left:4px solid var(--accent);background:var(--surface);color:#2B3947;
  font-size:.93rem}
.research-note .email{white-space:nowrap;color:var(--ink);font-weight:500}
.front-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.75rem;
  max-width:35rem;margin:1.35rem 0 1.15rem}
.front-stat{display:flex;align-items:baseline;gap:.65rem;padding:.85rem 1rem;
  border:1px solid var(--hair);border-top:3px solid var(--accent);background:var(--surface);
  border-radius:var(--radius);box-shadow:var(--soft-shadow)}
.front-stat .v{font-family:Georgia,'Times New Roman',serif;font-size:2.2rem;
  line-height:1;color:var(--ink);font-variant-numeric:tabular-nums}
.front-stat .k{font-size:.78rem;color:var(--muted);text-transform:uppercase;
  letter-spacing:.04em}
.site-release{display:inline-flex;align-items:center;gap:.35rem;margin:.15rem 0 .9rem;
  padding:.2rem .48rem;border:1px solid var(--hair);background:var(--surface);
  color:var(--muted);font-size:.7rem;line-height:1.35;border-radius:999px}
.quick-actions{display:flex;flex-wrap:wrap;gap:.45rem;margin:-.25rem 0 1.35rem}
.quick-actions a{display:inline-flex;align-items:center;min-height:2.35rem;padding:.42rem .72rem;
  border:1px solid var(--hair);border-radius:3px;background:var(--paper);color:var(--ink);
  font-size:.8rem;font-weight:600;text-decoration:none}
.quick-actions a:hover{border-color:var(--accent-dk);background:#F2FAFC}
.quick-actions a.primary{border-color:var(--ink);background:var(--ink);color:white}
.quick-actions a.primary:hover{background:var(--accent-dk);border-color:var(--accent-dk)}
.map-section{margin:1.1rem 0 2.1rem}
.map-section-head{display:flex;flex-wrap:wrap;align-items:end;justify-content:space-between;
  gap:.35rem 1rem;margin-bottom:.65rem}
.map-section-head h2{flex:1;margin:0;min-width:15rem}
.map-legend{display:flex;gap:.8rem;font-size:.74rem;color:var(--muted)}
.map-legend span{display:inline-flex;align-items:center;gap:.32rem}
.map-legend i{display:inline-block;width:.78rem;height:.78rem;border:1px solid #A9BBC2;
  background:#EDF2F4}
.map-legend i.watched{background:var(--accent);border-color:var(--accent-dk)}
.map-shell{display:grid;grid-template-columns:minmax(0,2.25fr) minmax(240px,.75fr);
  border:1px solid var(--hair);background:var(--surface);border-radius:var(--radius);
  overflow:hidden;box-shadow:var(--soft-shadow)}
.map-visual{position:relative;min-width:0;overflow:hidden;background:#F4FAFC;
  border-right:1px solid var(--hair)}
.map-svg{display:block;width:100%;height:auto;max-height:600px}
.map-sea{fill:#F4FAFC}
.map-country{fill:#E8EEF1;stroke:#FFFFFF;stroke-width:1.25;
  vector-effect:non-scaling-stroke;transition:fill .12s ease,stroke .12s ease}
.map-country-link{cursor:pointer}
.map-country-link .map-country{fill:var(--accent);stroke:#FFFFFF;stroke-width:1.4}
.map-country-link:hover .map-country,
.map-country-link:focus .map-country,
.map-country-link.selected .map-country{fill:var(--ink);stroke:var(--accent);stroke-width:2.5}
.map-country-link:focus{outline:none}
.map-inset-box{fill:rgba(255,255,255,.94);stroke:var(--ink);stroke-width:1.25}
.map-inset-label{fill:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:12px;
  font-weight:700;text-anchor:middle;pointer-events:none}
.map-inset-note{fill:var(--muted);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:8px;
  text-anchor:middle;pointer-events:none}
.map-hit{fill:transparent;pointer-events:all}
.map-pin{fill:#FFFFFF;stroke:var(--accent-dk);stroke-width:3;
  vector-effect:non-scaling-stroke;pointer-events:none}
.map-country-link:hover .map-pin,.map-country-link:focus .map-pin,
.map-country-link.selected .map-pin{fill:var(--ink);stroke:#FFFFFF}
.map-tooltip{position:absolute;z-index:2;max-width:270px;padding:.55rem .65rem;
  border:1px solid var(--ink);background:rgba(255,255,255,.97);box-shadow:0 4px 16px rgba(10,27,46,.14);
  font-size:.76rem;line-height:1.35;pointer-events:none}
.map-tooltip strong{display:block;margin-bottom:.16rem;color:var(--ink);font-size:.84rem}
.map-tooltip span{display:block;color:#2B3947}
.map-detail{padding:1rem 1.05rem;background:var(--paper);min-width:0}
.map-detail .eyebrow{font-size:.68rem;color:var(--accent-dk);font-weight:600;
  text-transform:uppercase;letter-spacing:.08em}
.map-detail h3{margin:.25rem 0 .35rem;font-size:1.18rem}
.map-detail p{font-size:.85rem;color:var(--muted);line-height:1.45}
.map-party-list{display:grid;gap:.35rem;margin-top:.75rem}
.map-party{display:flex;align-items:center;gap:.45rem;padding:.38rem .48rem;
  border:1px solid var(--hair);background:var(--surface);color:var(--ink);
  font-size:.79rem;line-height:1.3;text-decoration:none}
.map-party:hover{border-color:var(--accent);color:var(--ink)}
.map-party .camp-dot{width:.48rem;height:.48rem;flex:0 0 .48rem;
  border-radius:50%;background:var(--right)}
.map-party.left .camp-dot{background:var(--left);border:1px solid var(--accent-dk)}
.map-party small{margin-left:auto;color:var(--muted);font-size:.65rem}
.map-credit{margin:.45rem 0 0;font-size:.67rem;color:var(--muted)}
.country-directory{margin:.65rem 0 0;border-top:1px solid var(--hair)}
.country-directory>summary{cursor:pointer;color:var(--accent-dk);font-size:.82rem;
  padding:.6rem 0}
.country-directory-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:.45rem 1rem;padding:.25rem 0 .8rem}
.country-directory-item{border-bottom:1px solid var(--hair);padding:.35rem 0}
.country-directory-item strong{display:block;font-size:.82rem}
.country-directory-item span{font-size:.73rem;color:var(--muted)}

input.q{font-size:14px;padding:.5rem .6rem;border:1px solid var(--hair);
  background:var(--surface);width:100%;max-width:340px;color:var(--ink);
  font-family:inherit}
footer{margin-top:3.5rem;padding:1.15rem 0 1.5rem;border-top:1px solid var(--rule);max-width:68rem}
@media(max-width:850px){.weekly-panels{grid-template-columns:1fr}.wrap{max-width:880px}
  .four-week-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .party-directory-tools{grid-template-columns:repeat(2,minmax(0,1fr))}
  .map-shell{grid-template-columns:1fr}.map-visual{border-right:0;border-bottom:1px solid var(--hair)}
  .passport-grid,.tool-grid,.provenance-grid{grid-template-columns:1fr 1fr}}
@media(max-width:650px){.timeline-tools input,.search-tools input{min-width:0;width:100%}
  .front-stats{gap:.5rem}.front-stat{display:block;padding:.65rem .7rem}
  .front-stat .k{display:block;margin-top:.2rem}.country-directory-grid{grid-template-columns:1fr}
  .party-directory-tools,.party-directory-list{grid-template-columns:1fr}
  .party-directory-status{justify-content:flex-start;padding-bottom:0}
  .map-section-head h2{min-width:100%}
  nav.top{align-items:flex-start;gap:.35rem .8rem}.brand-lockup{width:100%;margin-bottom:.25rem}
  .representation-grid,.research-pages,.four-week-grid{grid-template-columns:1fr}
  .nav-menu{position:static}.nav-dropdown{position:static;box-shadow:none;border:0;
    border-left:2px solid var(--rule);padding:.2rem 0 .2rem .45rem;min-width:0}
  .nav-dropdown-wide{grid-template-columns:1fr}.nav-label{padding-top:.55rem}}
@media(max-width:520px){.passport-grid,.tool-grid,.provenance-grid{grid-template-columns:1fr}}
@media print{.skip-link,.quick-actions{display:none!important}
  details.country-section:not([open])>:not(summary),details.party-section:not([open])>:not(summary),
  details.reviewed:not([open])>:not(summary){display:block!important}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.map-country{transition:none}}

/* Homepage editorial refresh, version 1.3.  This keeps RAPPORT's original
   navy/cyan/pale-blue identity while making hierarchy and scanning clearer. */
.brand-lockup{display:flex;flex-direction:row;align-items:center;gap:.65rem;line-height:1.05}
.brand-mark{display:grid;place-items:center;width:2.15rem;height:2.15rem;flex:0 0 2.15rem;
  background:var(--ink);color:white;font-family:Georgia,'Times New Roman',serif;
  font-size:1.15rem;font-weight:700}
.brand-copy{display:flex;flex-direction:column;min-width:0}
.brand-copy .brand{font-family:Georgia,'Times New Roman',serif;letter-spacing:.1em}
body.home .wrap{max-width:1280px}
body.home nav.top{margin-bottom:0;padding:1rem .1rem}
.home-page{padding-top:0}
.home-status{display:flex;align-items:center;gap:.55rem 1.35rem;min-height:2.65rem;
  margin:0 0 3rem;padding:.55rem 0;border-bottom:1px solid var(--hair);
  color:var(--muted);font-size:.75rem;overflow-x:auto;white-space:nowrap}
.home-status .status-dot{width:.42rem;height:.42rem;border-radius:50%;background:var(--accent);
  flex:0 0 .42rem}.home-status strong{color:var(--ink)}
.home-status a{margin-left:auto;font-weight:700;text-decoration:none;text-transform:uppercase;
  letter-spacing:.05em}
.home-hero{position:relative;padding:0 0 2rem}
.home-kicker,.section-kicker{color:var(--accent-dk);font-size:.7rem;font-weight:750;
  letter-spacing:.16em;text-transform:uppercase}
.home-title{max-width:51rem;margin:.85rem 0 .9rem;font-size:clamp(2.8rem,6vw,5rem);
  line-height:.96;letter-spacing:-.045em;color:var(--right)}
.home-lede{max-width:60rem;margin:0;color:var(--ink);font-family:Georgia,'Times New Roman',serif;
  font-size:clamp(1.08rem,2vw,1.4rem);line-height:1.48}
.home-page .site-release{position:absolute;right:0;top:.2rem;margin:0;border-color:var(--rule);
  border-radius:3px;background:#F2FAFC;color:var(--ink);font-weight:700;
  letter-spacing:.08em;text-transform:uppercase}
.home-page .research-note{max-width:62rem;margin:1.35rem 0 0;padding:.15rem 0 .15rem .9rem;
  border-left:3px solid var(--accent);background:transparent;color:var(--muted);font-size:.85rem}
.front-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;max-width:none;
  margin:1.5rem 0 3.5rem;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}
.front-stat{display:block;min-height:6.5rem;padding:1.15rem 1.25rem;border:0;border-radius:0;
  background:transparent;box-shadow:none}.front-stat:first-child{padding-left:0}
.front-stat+.front-stat{border-left:1px solid var(--hair)}
.front-stat .v{display:block;font-size:2.25rem;color:var(--right)}
.front-stat .k{display:block;margin-top:.45rem;text-transform:none;letter-spacing:0;font-size:.75rem}
.map-section{margin:0 0 4rem}.map-section-head{align-items:end;margin:.4rem 0 1rem}
.map-section-title h2{margin:.35rem 0 0;padding:0;border:0;color:var(--right);
  font-family:Georgia,'Times New Roman',serif;font-size:clamp(1.8rem,3.2vw,2.65rem);
  font-weight:600;letter-spacing:-.03em}.map-section-title p{margin:.45rem 0 0;color:var(--muted);
  font-size:.86rem}.map-legend{padding-bottom:.25rem}
.map-shell{grid-template-columns:minmax(0,1.8fr) minmax(290px,.8fr);border-radius:0;
  background:white;box-shadow:none}.map-visual{background:#F4FAFC}
.map-detail{padding:1.4rem 1.35rem}.map-detail h3{font-family:Georgia,'Times New Roman',serif;
  font-size:1.8rem;font-weight:600}.map-party{padding:.55rem 0;border:0;border-bottom:1px solid var(--hair);
  background:transparent;font-size:.76rem}.map-party:hover{border-color:var(--accent)}
.map-credit{margin:.5rem 0 0}.country-directory{margin-top:.8rem}
.latest-section{margin:0 0 3.75rem}.latest-head{display:flex;align-items:end;
  justify-content:space-between;gap:1rem;margin-bottom:1rem}
.latest-head h2{margin:.35rem 0 0;padding:0;border:0;color:var(--right);
  font-family:Georgia,'Times New Roman',serif;font-size:clamp(1.8rem,3.2vw,2.65rem);
  font-weight:600;letter-spacing:-.03em}.latest-head p{margin:0;color:var(--muted);font-size:.82rem}
.latest-panel{display:grid;grid-template-columns:minmax(230px,.78fr) minmax(360px,1.45fr) minmax(250px,.78fr);
  border:1px solid var(--hair);border-top:4px solid var(--accent);background:var(--surface)}
.latest-panel>div{padding:1.35rem 1.45rem}.latest-panel>div+div{border-left:1px solid var(--hair)}
.latest-label{display:block;color:var(--muted);font-size:.66rem;font-weight:700;
  letter-spacing:.13em;text-transform:uppercase}.latest-week{display:block;margin:.55rem 0 .2rem;
  color:var(--right);font-family:Georgia,'Times New Roman',serif;font-size:2rem;font-weight:600}
.latest-range{color:var(--muted);font-size:.78rem}.latest-summary{margin:.8rem 0 0;font-size:.84rem;
  line-height:1.5}.latest-numbers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
  gap:.9rem;margin-top:.75rem}.latest-number strong{display:block;color:var(--right);
  font-family:Georgia,'Times New Roman',serif;font-size:1.75rem;font-weight:600}
.latest-number span{display:block;color:var(--muted);font-size:.7rem;line-height:1.35}
.latest-tools{display:grid;gap:.55rem;margin-top:.75rem}.latest-tools a{display:flex;
  align-items:center;justify-content:space-between;min-height:2.45rem;padding:.45rem .7rem;
  border:1px solid var(--rule);background:white;color:var(--ink);font-size:.72rem;
  font-weight:700;text-decoration:none}.latest-tools a:hover{border-color:var(--accent-dk);
  background:#F2FAFC}.latest-tools a.primary{border-color:var(--ink);background:var(--ink);
  color:white}.latest-tools a.primary:hover{background:var(--accent-dk);border-color:var(--accent-dk)}
.research-spine{margin:0 0 3.25rem;border-top:1px solid var(--hair)}
.research-spine-head{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
  padding:1.5rem 0 1rem}.research-spine-head h2{margin:0;padding:0;border:0;color:var(--right);
  font-family:Georgia,'Times New Roman',serif;font-size:1.7rem;font-weight:600}
.research-spine-head p{margin:0;color:var(--muted);font-size:.78rem}
.research-spine-links{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
  border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}
.research-spine-links a{min-height:6.2rem;padding:1.1rem 1.25rem;color:var(--ink);
  text-decoration:none}.research-spine-links a:first-child{padding-left:0}
.research-spine-links a+a{border-left:1px solid var(--hair)}
.research-spine-links strong{display:block;font-family:Georgia,'Times New Roman',serif;
  font-size:1.08rem;font-weight:600}.research-spine-links span{display:block;margin-top:.5rem;
  color:var(--muted);font-size:.7rem;line-height:1.4}.research-spine-links a:hover strong{color:var(--accent-dk)}
.recent-section h2{font-family:Georgia,'Times New Roman',serif;font-size:1.65rem;font-weight:600}
.recent-section .grid{border-top:1px solid var(--hair)}
.recent-section .grow{padding:.6rem 0}.recent-more{margin-top:1.25rem}
@media(max-width:900px){.latest-panel{grid-template-columns:1fr 1.25fr}
  .latest-panel>div:nth-child(3){grid-column:1/-1;border-left:0;border-top:1px solid var(--hair)}
  .map-shell{grid-template-columns:1fr}.front-stats{grid-template-columns:repeat(2,1fr)}
  .front-stat:nth-child(3){border-left:0;border-top:1px solid var(--hair)}
  .front-stat:nth-child(4){border-top:1px solid var(--hair)}}
@media(max-width:650px){.brand-lockup{width:auto;margin:0}.brand-lockup small{display:none}
  .home-status{margin-bottom:2rem}.home-status a{margin-left:0}.home-title{font-size:2.75rem}
  .home-page .site-release{position:static;width:max-content;margin:1rem 0 0}
  .latest-head,.research-spine-head{display:block}.latest-head p,.research-spine-head p{margin-top:.45rem}
  .latest-panel{grid-template-columns:1fr}.latest-panel>div+div{border-left:0;border-top:1px solid var(--hair)}
  .latest-panel>div:nth-child(3){grid-column:auto}.latest-numbers{grid-template-columns:repeat(3,1fr)}
  .research-spine-links{grid-template-columns:1fr 1fr}.research-spine-links a:nth-child(3){border-left:0;border-top:1px solid var(--hair)}
  .research-spine-links a:nth-child(4){border-top:1px solid var(--hair)}
  .map-section-head{display:block}.map-legend{margin-top:.65rem}}
@media(max-width:430px){.front-stats{grid-template-columns:1fr}.front-stat+.front-stat{border-left:0;border-top:1px solid var(--hair)}
  .research-spine-links{grid-template-columns:1fr}.research-spine-links a+a{border-left:0;border-top:1px solid var(--hair)}
  .latest-numbers{grid-template-columns:1fr}.latest-number{padding-bottom:.45rem}}
"""

from reportbuilder import REPORT_CSS  # noqa: E402
CSS = CSS + REPORT_CSS



def e(s):
    return html.escape(str(s or ""))


def camp_label(value):
    """Public label for the compact internal left/right roster value."""
    return "far-left" if value == "left" else "far-right"


def party_display_name(party):
    """Consistent public name: English / original language (acronym)."""
    english = str(party.get("name") or party.get("short") or party.get("id") or "")
    original = str(party.get("original_name") or "").strip()
    acronym = str(party.get("acronym") or "").strip()
    label = f"{english} / {original}" if original else english
    if acronym:
        label += f" ({acronym})"
    return label


def layout(title, body, depth=0, subtitle=""):
    up = "../" * depth
    page_title = title if title == SITE_NAME else f"{title} · {SITE_NAME}"
    body_class = "home" if title == SITE_NAME else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{e(SITE_DESCRIPTION)}">
<meta name="theme-color" content="#0A1B2E">
<meta name="referrer" content="strict-origin-when-cross-origin">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; connect-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self' https://www.neilbar.com">
<title>{e(page_title)}</title>
<link rel="stylesheet" href="{up}assets/style.css">
</head><body class="{body_class}"><a class="skip-link" href="#main-content">Skip to content</a><div class="wrap">
<nav class="top" aria-label="Primary navigation">
  <span class="brand-lockup"><span class="brand-mark" aria-hidden="true">R</span>
    <span class="brand-copy"><a class="brand" href="{up}index.html">{SITE_NAME}</a>
      <small>{e(SITE_EXPANSION)}</small></span></span>
  <details class="nav-menu"><summary>Reports</summary><div class="nav-dropdown">
    <a href="{up}index.html#latest">Latest weekly report</a>
    <a href="{up}archive.html">Report archive</a>
    <a href="{up}report.html">Build custom report</a>
  </div></details>
  <details class="nav-menu"><summary>Explore</summary><div class="nav-dropdown">
    <a href="{up}parties.html">Countries and parties</a>
    <a href="{up}compare.html">Compare parties and periods</a>
    <a href="{up}quotes.html">Quotation explorer</a>
    <a href="{up}events.html">Cross-party events</a>
    <a href="{up}speakers.html">Speakers</a>
    <a href="{up}network.html">Party network</a>
  </div></details>
  <details class="nav-menu"><summary>Research</summary><div class="nav-dropdown nav-dropdown-wide">
    <div class="nav-column"><span class="nav-label">Method and audit</span>
      <a href="{up}methodology.html">Methodology</a>
      <a href="{up}quality.html">Quality and validation</a>
      <a href="{up}sources.html">Source registry</a>
      <a href="{up}inclusion.html">Party-inclusion dossiers</a>
      <a href="{up}prompts.html">Prompt archive</a>
      <a href="{up}health.html">Collection status</a></div>
    <div class="nav-column"><span class="nav-label">Data and reuse</span>
      <a href="{up}elections.html">Verified election series</a>
      <a href="{up}dataset.html">Dataset and exports</a>
      <a href="{up}tutorials.html">Usage tutorials</a>
      <a href="{up}citation.html">Suggested citation</a></div>
  </div></details>
  <a href="{up}search.html">Search</a>
  <span class="spacer"></span>
  <span class="meta">{e(subtitle)}</span>
</nav>
<main id="main-content" tabindex="-1">{body}</main>
<footer class="meta">
<strong>{SITE_NAME}</strong> — {e(SITE_EXPANSION)}. Automated research monitoring
powered by the Claude API. AI-generated material may contain errors; consult the
cited primary sources. <a href="https://www.neilbar.com" rel="me">Dr. Neil Bar</a>.
</footer>
</div><script>
const navMenus=[...document.querySelectorAll('.nav-menu')];
navMenus.forEach(menu=>menu.addEventListener('toggle',()=>{{
  if(menu.open)navMenus.forEach(other=>{{if(other!==menu)other.open=false}});
}}));
document.addEventListener('click',event=>{{
  if(!event.target.closest('.nav-menu'))navMenus.forEach(menu=>menu.open=false);
}});
document.addEventListener('keydown',event=>{{
  if(event.key==='Escape')navMenus.forEach(menu=>{{
    if(menu.open){{menu.open=false;menu.querySelector('summary').focus()}}
  }});
}});
const currentPath=location.pathname.replace(/index\\.html$/,'');
document.querySelectorAll('nav.top a:not(.brand)').forEach(link=>{{
  if(new URL(link.href).pathname.replace(/index\\.html$/,'')===currentPath)
    link.setAttribute('aria-current','page');
}});
</script></body></html>"""


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


def confidence_dimensions(item):
    """Transparent record-level checks; these are not a validity score."""
    analysis = item.get("analysis") or {}
    direct = is_party_document(item)
    quoted = any(q.get("original") for q in analysis.get("quotes") or [])
    translated = any(q.get("translation") and q.get("translation") != q.get("original")
                     for q in analysis.get("quotes") or [])
    audits = item.get("backtranslation") or []
    flagged = any(row.get("flagged") for row in audits)
    if not translated:
        translation = "not used"
    elif flagged:
        translation = "flagged"
    elif audits:
        translation = "round-trip checked"
    else:
        translation = "AI, unaudited"
    return {
        "source identity": "direct/official" if direct else (item.get("outlet") or "external"),
        "date": "recorded" if item.get("published") else "missing",
        "attribution": "quoted/direct" if (quoted or direct) else "reported",
        "translation": translation,
        "relevance": analysis.get("confidence") or "not stated",
    }


def ai_labels_html(item):
    analysis = item.get("analysis") or {}
    labels = ['<span class="ai-label">Source metadata</span>']
    if analysis:
        labels.append('<span class="ai-label ai">AI-assisted screening and summary</span>')
    if any(q.get("translation") and q.get("translation") != q.get("original")
           for q in analysis.get("quotes") or []):
        labels.append('<span class="ai-label ai">AI translation</span>')
    if item.get("interpretation"):
        labels.append('<span class="ai-label ai">AI interpretation</span>')
    if item.get("backtranslation"):
        labels.append('<span class="ai-label ai">AI translation audit</span>')
    if item.get("code_detail"):
        labels.append('<span class="ai-label human">Human-coded</span>')
    else:
        labels.append('<span class="ai-label">Not human-validated</span>')
    return '<div class="ai-labels" aria-label="Authorship labels">' + "".join(labels) + '</div>'


def provenance_card_html(item):
    """Audit information kept beside the claim rather than on a distant page."""
    meta = item.get("analysis_meta") or {}
    stages = "; ".join(
        f'{stage}: {row.get("model") or "unspecified"} / {row.get("prompt_ver") or "unspecified"}'
        for stage, row in sorted(meta.items())) or "No model-run metadata recorded"
    source_url = item.get("url") or ""
    domain = urlparse(source_url).netloc or "Not recorded"
    snapshot = item.get("snapshot_path") or "Not captured"
    if item.get("snapshot_sha256"):
        snapshot += f' · SHA-256 {item["snapshot_sha256"]}'
    link_check = item.get("link_check") or {}
    link_state = link_check.get("status") or "not re-checked"
    if link_check.get("checked_at"):
        link_state += f' · {str(link_check["checked_at"])[:10]}'
    code = item.get("code_detail") or {}
    review = (f'{code.get("category") or "coded"} · {code.get("coder") or "researcher"} · '
              f'{code.get("coded_date") or "date not recorded"}') if code else "Not human-coded"
    chips = "".join(f'<span class="confidence-chip"><strong>{e(k)}:</strong> {e(v)}</span>'
                    for k, v in confidence_dimensions(item).items())
    fields = [
        ("Record ID", item.get("id") or ""),
        ("Source domain", domain),
        ("Published / retrieved", f'{str(item.get("published") or "unknown")[:10]} / '
                                    f'{str(item.get("collected_at") or "unknown")[:10]}'),
        ("Evidence class", f'{item.get("provenance") or "unclassified"} · '
                           f'{"direct" if is_party_document(item) else "outside reporting"}'),
        ("Snapshot", snapshot),
        ("Link re-check", link_state),
        ("Model / prompt", stages),
        ("Human review", review),
    ]
    rows = "".join(f'<div><strong>{e(label)}</strong>{e(value)}</div>' for label, value in fields)
    return (f'<details class="provenance-card"><summary>Record provenance and confidence</summary>'
            f'<div class="provenance-grid">{rows}<div><strong>Confidence dimensions</strong>'
            f'<span class="confidence-row">{chips}</span></div>'
            '</div></details>')


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
    parts.append(ai_labels_html(it))

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
    parts.append(provenance_card_html(it))
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
            + ('<span class="ai-label ai">AI-assisted description</span>' if desc else '')
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
            + ('<span class="ai-label ai">Automated description</span>' if description else '')
            + '</li>'
        )
    if not entries:
        entries.append('<li><span class="meta">No verified result was retrieved. '
                       'Check Collection status before treating this as a quiet week.</span></li>')
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
            '<p class="meta"><span class="ai-label ai">AI-assisted digest</span> The shortest route through the most consequential retained '
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


def representation_changes_html(rows):
    """Verified seat, membership, or parliamentary-status changes in the week."""
    entries = []
    for row in rows or []:
        source = (f' <a href="{e(row.get("source"))}" rel="noreferrer">source</a>'
                  if row.get("source") else "")
        party = row.get("party") or row.get("party_id") or "Party"
        entries.append(f'<li><strong>{e(party)}</strong>: {e(row.get("text"))}{source}</li>')
    if not entries:
        entries.append('<li class="meta">No verified representation change was recorded '
                       'for this reporting week.</li>')
    return ('<section class="change-box representation-change" id="representation-changes">'
            '<h2>Representation changes</h2><p class="meta">Changes in seats or formal '
            'parliamentary status are included only when an institutional source has been '
            'checked.</p><ul class="change-list">' + "".join(entries) + '</ul></section>')


def four_week_timeline_html(periods):
    """Compact, stable-link timeline covering this issue and the prior three."""
    cards = []
    for week, rows in periods or []:
        retained = [row for row in rows if (row.get("analysis") or {}).get("relevant")]
        ordered = sorted(retained, key=lambda row: row.get("published") or "",
                         reverse=True)
        ordered.sort(key=lambda row: not is_party_document(row))
        entries = []
        for row in ordered[:4]:
            title = (row.get("title") or (row.get("analysis") or {}).get("summary")
                     or "Recorded activity")
            entries.append(f'<li><a href="../issues/{e(week)}.html#item-{e(row.get("id"))}">'
                           f'{e(row.get("party_name") or row.get("party_id"))}</a>: '
                           f'{e(title[:92])}</li>')
        if not entries:
            entries.append('<li class="meta">No retained records.</li>')
        cards.append(f'<section class="four-week-card"><h3>{e(week)}</h3>'
                     f'<span class="meta">{len(retained)} retained</span>'
                     f'<ul>{"".join(entries)}</ul></section>')
    if not cards:
        return ""
    return ('<section id="four-week-timeline"><h2>Four-week timeline</h2>'
            '<p class="meta">A compact view of retained party activity. Each party name '
            'opens the stable evidence record in its original weekly issue.</p>'
            f'<div class="four-week-grid">{"".join(cards)}</div></section>')


def issue_tools_html(week, week_range):
    citation = (f'Bar, Neil. “RAPPORT: Week {week} ({week_range}).” '
                'Radicalism and Party Politics: Observation, Reporting and Tracking.')
    return (f'<aside class="report-tools" aria-label="Citation and export">'
            f'<span class="citation-text"><strong>Cite this report:</strong> {e(citation)}</span>'
            f'<button type="button" data-copy-text="{e(citation)}">Copy citation</button>'
            '<button type="button" data-copy-link>Copy stable link</button>'
            f'<a href="../data/{e(week)}.csv" download>CSV</a>'
            '<button type="button" onclick="window.print()">Print / PDF</button></aside>')


def research_passport_html(week, items, all_items, coverage, research=None):
    """Compact reproducibility metadata for one generated report (no Git identifier)."""
    research = research or {}
    retained = [row for row in items if (row.get("analysis") or {}).get("relevant")]
    reviewed = len(all_items or [])
    prompts = sorted({
        f'{stage}:{meta.get("prompt_ver")}'
        for row in (all_items or items)
        for stage, meta in (row.get("analysis_meta") or {}).items()
        if meta.get("prompt_ver")
    })
    models = sorted({
        meta.get("model")
        for row in (all_items or items)
        for meta in (row.get("analysis_meta") or {}).values()
        if meta.get("model")
    })
    human = sum(bool(row.get("code_detail")) for row in retained)
    translated = sum(any(q.get("translation") and q.get("translation") != q.get("original")
                         for q in (row.get("analysis") or {}).get("quotes") or [])
                     for row in retained)
    audited = sum(bool(row.get("backtranslation")) for row in retained)
    checked = (coverage or {}).get("checked", 0)
    total = (coverage or {}).get("total", 0)
    successful = sum(
        row.get("status") not in {"Official source inaccessible", "No archived check"}
        for row in (coverage or {}).get("entries") or [])
    cells = [
        (research.get("version") or "unversioned", "data-release version"),
        (week, "reporting week"),
        (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "site build"),
        (str(total), "configured party roster"),
        (f"{checked}/{total}", "parties with an archived check"),
        (f"{successful}/{total}", "parties with a successful collection result"),
        (str(reviewed), "records screened"),
        (str(len(retained)), "records retained"),
        (str(max(0, reviewed - len(retained))), "records not retained"),
        (str(human), "retained records human-coded"),
        (f"{translated}/{audited}", "translated / translation-audited records"),
        (", ".join(models) or "metadata unavailable", "model(s)"),
        (", ".join(prompts) or "metadata unavailable", "prompt version(s)"),
    ]
    return ('<details class="passport"><summary><strong>Research Passport</strong> — '
            'how this report was produced</summary><p class="meta">Build and coverage '
            'metadata for reproducibility.</p><div class="passport-grid">'
            + "".join(f'<div><strong>{e(value)}</strong><span>{e(label)}</span></div>'
                      for value, label in cells) + '</div></details>')


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
  try{{localStorage.setItem('rapport-quote-mode',mode)}}catch(_e){{}}
}}
document.querySelectorAll('[data-quote-mode]').forEach(b=>b.addEventListener('click',()=>setQuoteMode(b.dataset.quoteMode)));
let savedMode='both';try{{savedMode=localStorage.getItem('rapport-quote-mode')||'both'}}catch(_e){{}}
setQuoteMode(['both','english','original'].includes(savedMode)?savedMode:'both');
{extra}
</script>"""


# ------------------------------------------------------------- pages

def issue_page(week, items, overview, briefings, country_names, parties,
               absences, cluster_sizes, out_dir,
               all_items=None, page_changes=None,
               editors_cut=None, world=None, highlights=None, reading=None,
               week_range="", retractions=None, minute=None, changes=None,
               coverage=None, watch=None, previous_week="",
               representation_changes=None, four_week_periods=None,
               research=None):
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
    body.append(issue_tools_html(week, week_range))
    body.append(research_passport_html(week, items, all_items, coverage, research))
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
        body.append(f'<p class="brief"><span class="ai-label ai">AI-assisted overview</span> '
                    f'<strong>The monitored week:</strong> {e(overview)}</p>')

    body.append(changes_html(changes, previous_week))
    body.append(representation_changes_html(representation_changes))
    body.append(four_week_timeline_html(four_week_periods))
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
                            f'week.{site} Collection attempts remain visible on Collection status.</p>')
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
document.querySelectorAll('[data-copy-text]').forEach(button=>button.addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText(button.dataset.copyText);button.textContent='Copied'}
  catch(_e){button.textContent='Select citation above'}
}));
document.querySelectorAll('[data-copy-link]').forEach(button=>button.addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText(location.href);button.textContent='Link copied'}
  catch(_e){button.textContent='Copy the address bar'}
}));
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
    body = ['<h1>Collection status</h1>',
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
        f.write(layout("Collection status", "".join(body),
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


def _seat_card(label, row, fallback_source=None):
    row = row or {}
    if row.get("seats") is None or not row.get("total"):
        source = fallback_source or {}
        link = (f' <a href="{e(source.get("url"))}" rel="noreferrer">Check official source</a>.'
                if source.get("url") else "")
        return (f'<section class="seat-card"><h3>{e(label)}</h3>'
                '<p class="seat-pending">A verified seat total has not yet been published '
                f'in RAPPORT.{link}</p></section>')
    seats, total = int(row.get("seats", 0)), int(row.get("total", 0))
    width = min(100, max(0, 100 * seats / total)) if total else 0
    source = row.get("source") or (fallback_source or {}).get("url")
    source_link = (f'<a href="{e(source)}" rel="noreferrer">source</a>' if source else "")
    basis = row.get("basis") or ""
    note = row.get("note") or ""
    context = " · ".join(v for v in (str(row.get("as_of") or "current verified total"),
                                      str(basis)) if v)
    note_html = f'<p class="seat-pending">{e(note)}</p>' if note else ""
    return (f'<section class="seat-card"><h3>{e(row.get("label") or label)}</h3>'
            f'<div class="seat-value">{seats} <span class="meta">/ {total}</span></div>'
            f'<div class="seat-bar" aria-label="{seats} of {total} seats"><i style="width:{width:.2f}%"></i></div>'
            f'<p class="meta">{e(context)} {source_link}</p>{note_html}</section>')


def representation_html(party, representation):
    representation = representation or {}
    country = (representation.get("country_sources") or {}).get(party.get("country"), {})
    profile = (representation.get("parties") or {}).get(party.get("id"), {})
    links = []
    if party.get("site"):
        links.append(("Official party website", party["site"]))
    custom_links = profile.get("links") or {}
    domestic = custom_links.get("domestic") or country.get("parliament")
    if domestic and domestic.get("url"):
        label = domestic.get("label") or "Domestic parliament"
        if not custom_links.get("domestic"):
            label += " · institutional directory"
        links.append((label, domestic["url"]))
    european = custom_links.get("european")
    if not european and country.get("eu_member"):
        european = representation.get("european_parliament")
    if european and european.get("url"):
        label = european.get("label") or "European Parliament"
        if not custom_links.get("european"):
            label += " · member directory"
        links.append((label, european["url"]))
    election_source = country.get("elections") or {}
    if election_source.get("url"):
        links.append((election_source.get("label") or "Official election results",
                      election_source["url"]))

    parts = ['<section aria-labelledby="representation-heading"><h2 id="representation-heading">'
             'Representation</h2><p class="meta">Current representation is kept separate '
             'from election-result seats. Figures appear only after source verification.</p>',
             '<div class="profile-links">']
    parts.extend(f'<a href="{e(url)}" rel="noreferrer">{e(label)}</a>'
                 for label, url in links)
    parts.append('</div><div class="representation-grid">')
    current = profile.get("current") or {}
    parts.append(_seat_card("National parliament", current.get("national"),
                            country.get("parliament")))
    if country.get("eu_member") or current.get("european"):
        parts.append(_seat_card("European Parliament", current.get("european"),
                                representation.get("european_parliament")))
    for row in current.get("regional") or []:
        parts.append(_seat_card(row.get("name") or "State or regional parliament", row))
    parts.append('</div>')

    elections = (profile.get("elections") or {}).get("national") or []
    parts.append('<h3>Last two concluded national elections</h3>')
    if elections:
        scale = max((int(row.get("seats") or 0) for row in elections[-2:]), default=1) or 1
        parts.append('<div class="election-comparison">')
        for row in elections[-2:]:
            seats = int(row.get("seats") or 0)
            height = max(2, 90 * seats / scale)
            source = (f'<a href="{e(row.get("source"))}" rel="noreferrer">source</a>'
                      if row.get("source") else "")
            vote = (f'{row.get("vote_share")}% vote' if row.get("vote_share") is not None
                    else "vote share unavailable")
            parts.append(f'<div class="election-result"><span class="column" style="height:{height:.1f}px"></span>'
                         f'<strong>{seats} seats</strong><small>{e(row.get("date"))}</small>'
                         f'<small>{e(vote)} · {source}</small></div>')
        parts.append('</div>')
    else:
        link = (f'<a href="{e(election_source.get("url"))}" rel="noreferrer">official election source</a>'
                if election_source.get("url") else "the official election source")
        parts.append('<div class="box dashed"><p>Election comparison awaiting verification.</p>'
                     f'<p class="meta">RAPPORT will not infer historical seats. Use the {link} '
                     'until two sourced results are entered.</p></div>')
    checked = profile.get("checked_on") or representation.get("checked_on")
    if checked:
        parts.append(f'<p class="meta">Institutional links checked {e(checked)}.</p>')
    parts.append('</section>')
    return "".join(parts)


def party_page(party, series, items, out_dir, representation=None):
    body = [f'<h1>{e(party_display_name(party))}</h1>',
            f'<p class="meta">{e(party.get("country",""))} · '
            f'<a href="../inclusion.html">inclusion dossier</a> · '
            f'<a href="../sources.html">source registry</a></p>',
            representation_html(party, representation)]

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
                    'Collection status to distinguish a quiet period from a blocked source.</p></div>')
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


def methodology_page(parties, prompt_versions, revisions, out_dir, research=None):
    """Plain-language method, limitations, and a visible revision history."""
    body = ['<h1>Methodology and revision log</h1>',
            f'<p class="lede">{SITE_NAME} is an evidence-led, automated AI monitoring '
            'archive powered by the Claude API. It records what '
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
    unit = (research or {}).get("unit_of_analysis") or {}
    body += ['<h2>Unit of analysis</h2>',
             f'<p><strong>{e(unit.get("label") or "Evidence record")}</strong>: '
             f'{e(unit.get("definition") or "")}</p>',
             f'<p><strong>Duplicate rule:</strong> {e(unit.get("duplicate_rule") or "")}</p>',
             f'<p><strong>Time rule:</strong> {e(unit.get("time_rule") or "")}</p>',
             '<p class="meta">The unit is not a party-week, ideological topic, sentence, '
             'or estimate of public opinion.</p>']
    body += [
        '<h2>What the labels mean</h2>',
        '<p><strong>Direct record</strong> means a party-controlled source, a named leader’s '
        'direct channel, or an official parliamentary record. <strong>Outside reporting</strong> '
        'means journalism or another contextual source. Action labels describe the form of an '
        'observable act, such as a parliamentary intervention or mobilisation; they are not '
        'ideological topic labels. <strong>far-left</strong> and <strong>far-right</strong> '
        'are the two operational roster buckets used throughout this project. They are not '
        'claims of academic consensus or party self-identification.</p>',
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
        '<h2>Negative-evidence protocol</h2>',
        '<p>A missing item is not a negative finding. The following rules govern any statement '
        'about silence or non-observation:</p><ol>']
    body.extend(f'<li>{e(rule)}</li>' for rule in (research or {}).get("negative_evidence") or [])
    body += ['</ol>',
        '<h2>AI-output labelling</h2>',
        '<p>Every full evidence card distinguishes source metadata and source quotations from '
        'AI-assisted screening, summary, translation, translation audit, and interpretation. '
        'A separate human-coded label appears only where a researcher code is stored. No '
        'unlabelled model output should be read as source evidence.</p>',
        '<p>See the <a href="prompts.html">versioned prompt archive</a>, '
        '<a href="quality.html">quality and validation dashboard</a>, and '
        '<a href="inclusion.html">party-inclusion dossiers</a>.</p>',
        '<h2>Monitored roster</h2>',
        f'<p class="meta">{len(parties)} parties are configured. Inclusion is a research-roster '
        'decision, not an endorsement or a claim that every party is equivalent.</p>',
        '<ul class="link-list">']
    for party in sorted(parties, key=lambda p: (p.get("country", ""), p.get("short", ""))):
        body.append(f'<li><a class="link-title" href="parties/{e(party["id"])}.html">'
                    f'{e(party.get("short") or party.get("name"))}</a>'
                    f'<span class="link-meta">{e(party.get("country"))} · '
                    f'{camp_label(party.get("camp"))} · {e(party.get("name"))}</span></li>')
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


def dataset_page(index, parties, years, out_dir, research=None, export_info=None):
    """Human-readable dataset landing page and compact codebook."""
    total = sum(int(row.get("items") or 0) for row in index)
    year_links = "".join(
        f'<li><a class="link-title" href="corpus/{e(year)}.json" download>'
        f'{e(year)} corpus (JSON)</a><span class="link-meta">Retained evidence records '
        f'for {e(year)}</span></li>' for year in years)
    week_links = "".join(
        f'<li><a class="link-title" href="data/{e(row.get("week"))}.csv" download>'
        f'{e(row.get("week"))} coding rows (CSV)</a><span class="link-meta">'
        f'{e(row.get("range"))} · {row.get("items", 0)} retained items</span></li>'
        for row in index)
    body = f'''<h1>Dataset and exports</h1>
<p class="lede">Download the public evidence index behind RAPPORT. Each record retains its
source URL, date, party, country, evidence class, observable action type, factual summary,
and stable weekly-report identifier.</p>
<div class="statline"><div class="stat"><div class="v">{total}</div><div class="k">retained records</div></div>
<div class="stat"><div class="v">{len(parties)}</div><div class="k">monitored parties</div></div>
<div class="stat"><div class="v">{len(index)}</div><div class="k">weekly issues</div></div>
<div class="stat"><div class="v">{e((research or {}).get('version') or '—')}</div><div class="k">data release</div></div></div>
<div class="research-pages"><section class="box"><h4>Machine-readable corpus</h4>
<p>Use the <a href="corpus/index.json">corpus index (JSON)</a> to discover annual shards.</p>
<ul class="link-list">{year_links or '<li class="meta">No corpus shards yet.</li>'}</ul></section>
<section class="box"><h4>Weekly coding exports</h4><ul class="link-list">
{week_links or '<li class="meta">No weekly exports yet.</li>'}</ul></section>
<section class="box"><h4>Teaching and replication</h4><ul class="link-list">
<li><a class="link-title" href="downloads/rapport-teaching-sample.csv" download>Teaching sample (CSV)</a><span class="link-meta">{(export_info or {}).get('teaching_rows', 0)} diverse records; review status is explicit</span></li>
<li><a class="link-title" href="downloads/rapport-replication.ipynb" download>Replication quickstart (Jupyter notebook)</a><span class="link-meta">Downloads public shards; no API key required</span></li>
</ul></section><section class="box"><h4>Citation-manager exports</h4><ul class="link-list">
<li><a class="link-title" href="downloads/rapport-records.bib" download>All evidence records (BibTeX)</a></li>
<li><a class="link-title" href="downloads/rapport-records.ris" download>All evidence records (RIS)</a></li>
<li><a class="link-title" href="CITATION.cff" download>Platform citation (CITATION.cff)</a></li>
</ul></section></div>
<h2>Expanded codebook</h2>
<table class="rev"><thead><tr><th>Field</th><th>Meaning</th></tr></thead><tbody>
<tr><td class="n">id / w / d</td><td>Stable record identifier, ISO reporting week, and publication date.</td></tr>
<tr><td class="n">p / pn / c</td><td>Party identifier, display name, and country code.</td></tr>
<tr><td class="n">cm</td><td>Operational roster bucket: far-left or far-right, stored compactly as left/right.</td></tr>
<tr><td class="n">pr / di</td><td>Evidence provenance and whether the record is a direct party or parliamentary document.</td></tr>
<tr><td class="n">st / o / l</td><td>Collector document type, source/outlet, and source-language hint.</td></tr>
<tr><td class="n">ti / s / at</td><td>Source title, AI-assisted factual summary, and observable action type.</td></tr>
<tr><td class="n">u / au</td><td>Original source URL and archived URL, where capture succeeded.</td></tr>
<tr><td class="n">ca / sh / lc</td><td>Retrieval date, abbreviated snapshot SHA-256, and latest link-check state.</td></tr>
<tr><td class="n">ac / q</td><td>Named actors and captured quotations (original, AI translation, speaker).</td></tr>
<tr><td class="n">bt</td><td>Per-quotation round-trip translation audit: quote index, flag, severity, and note.</td></tr>
<tr><td class="n">cf</td><td>Automated relevance confidence; not a probability or human-validation score.</td></tr>
<tr><td class="n">cd</td><td>Researcher coding category, blank when no human code is recorded.</td></tr>
</tbody></table>
<h2>Unit of analysis</h2><p>{e(((research or {}).get('unit_of_analysis') or {}).get('definition') or '')}</p>
<h2>Use and limitations</h2><p>These are records retained by an automated collection and
screening system, not a complete census of political activity. Dynamic, blocked, deleted,
or unconfigured sources may be missed. Verify analytical claims against the linked primary
source and cite the specific weekly issue and record. See the <a href="methodology.html">full methodology</a>
and <a href="citation.html">suggested citation</a>. The teaching sample is not independently
human-validated unless a row explicitly says <em>researcher-coded</em>.</p>
<h2>Stable links</h2><p>Weekly reports use <code>issues/YYYY-Www.html</code>; individual
records add <code>#item-ID</code>; party pages use <code>parties/PARTY-ID.html</code>.
These identifiers do not change when the site is rebuilt.</p>'''
    path = os.path.join(out_dir, "dataset.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Dataset and exports", body, subtitle="public research data"))
    return path


def citation_page(out_dir):
    """Citable descriptions for the project, dataset, and individual issues."""
    site_citation = ("Bar, Neil. RAPPORT: Radicalism and Party Politics: Observation, "
                     "Reporting and Tracking. Automated research monitoring platform. "
                     "https://www.neilbar.com.")
    dataset_citation = ("Bar, Neil. RAPPORT public evidence dataset [data set]. "
                        "Radicalism and Party Politics: Observation, Reporting and Tracking.")
    bib = """@misc{bar_rapport,
  author = {Neil Bar},
  title = {RAPPORT: Radicalism and Party Politics: Observation, Reporting and Tracking},
  howpublished = {Automated research monitoring platform},
  url = {https://www.neilbar.com},
  note = {Accessed: YYYY-MM-DD}
}"""
    body = f'''<h1>Suggested citation</h1>
<p class="lede">Cite the narrowest stable object that supports the claim: an individual
evidence record where possible, otherwise its weekly report, dataset version, or the platform.</p>
<section class="box"><h4>Platform</h4><p>{e(site_citation)}</p>
<button type="button" data-copy-text="{e(site_citation)}">Copy citation</button></section>
<section class="box"><h4>Weekly report</h4><p>Bar, Neil. “RAPPORT: Week YYYY-Www
(date range).” <em>Radicalism and Party Politics: Observation, Reporting and Tracking</em>.
Permanent weekly-report URL.</p></section>
<section class="box"><h4>Dataset</h4><p>{e(dataset_citation)} Add the download date and
the corpus or weekly-export URL used.</p></section>
<div class="tool-actions"><a href="CITATION.cff" download>Download CITATION.cff</a>
<a href="downloads/rapport-records.bib" download>Download record BibTeX</a>
<a href="downloads/rapport-records.ris" download>Download record RIS</a></div>
<h2>BibTeX</h2><pre class="bib">{e(bib)}</pre>
<h2>Stable-link hierarchy</h2><ul>
<li>Report: <code>issues/YYYY-Www.html</code></li>
<li>Evidence record: <code>issues/YYYY-Www.html#item-ID</code></li>
<li>Party archive: <code>parties/PARTY-ID.html</code></li>
</ul><p class="meta">Replace the example access date and use the public RAPPORT URL once
the project domain is finalised.</p>
<script>document.querySelectorAll('[data-copy-text]').forEach(button=>button.addEventListener('click',async()=>{{
try{{await navigator.clipboard.writeText(button.dataset.copyText);button.textContent='Copied'}}
catch(_e){{button.textContent='Select the citation above'}}
}}));</script>'''
    path = os.path.join(out_dir, "citation.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Suggested citation", body, subtitle="how to cite RAPPORT"))
    return path


def compare_page(out_dir):
    """Client-side comparison, longitudinal explorer, exports, and figures."""
    body = r'''<h1>Compare parties and periods</h1>
<p class="lede">Explore retained evidence by party, country, period, action, document type,
and evidence class. Counts measure documents in this archive—not votes, support, salience,
or ideological intensity.</p>
<div class="research-tool"><div class="tool-grid">
<label>Party A<select id="cmp-a"><option value="">All matching records</option></select></label>
<label>Party B<select id="cmp-b"><option value="">No second series</option></select></label>
<label>Country<select id="cmp-country"><option value="">All countries</option></select></label>
<label>Action<select id="cmp-action"><option value="">All actions</option></select></label>
<label>Document type<select id="cmp-type"><option value="">All document types</option></select></label>
<label>Evidence<select id="cmp-evidence"><option value="">All evidence</option>
<option value="direct">Direct/official</option><option value="coverage">Outside reporting</option></select></label>
<label>From<input id="cmp-from" type="date"></label><label>To<input id="cmp-to" type="date"></label>
<label>Time unit<select id="cmp-group"><option value="week">ISO week</option><option value="month">Month</option><option value="year">Year</option></select></label>
</div><div class="tool-actions"><button id="cmp-reset" type="button">Reset filters</button>
<button id="cmp-svg" type="button">Download SVG</button><button id="cmp-png" type="button">Download PNG</button>
<button id="cmp-csv" type="button">Download filtered CSV</button><button id="cmp-json" type="button">Download filtered JSON</button>
<button id="cmp-bib" type="button">Download BibTeX</button><button id="cmp-ris" type="button">Download RIS</button></div></div>
<p id="cmp-status" class="meta">Loading research corpus…</p>
<div class="chart-shell"><svg id="cmp-chart" viewBox="0 0 900 360" role="img" aria-label="Retained document counts over time"></svg></div>
<div class="matrix-wrap"><table class="matrix"><thead><tr><th>Period</th><th id="cmp-head-a">Series A</th><th id="cmp-head-b">Series B</th></tr></thead><tbody id="cmp-table"></tbody></table></div>
<p class="table-note">For reproducibility, download the exact filtered rows with the figure.
The exported BibTeX and RIS files contain one entry per retained record.</p>
<script>
const ce=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let corpus=[], current=[];
const fields=['cmp-a','cmp-b','cmp-country','cmp-action','cmp-type','cmp-evidence','cmp-from','cmp-to','cmp-group'];
function weekKey(date){const d=new Date(`${date}T00:00:00Z`);if(Number.isNaN(d))return 'undated';d.setUTCDate(d.getUTCDate()+4-(d.getUTCDay()||7));const y=new Date(Date.UTC(d.getUTCFullYear(),0,1));const w=Math.ceil((((d-y)/86400000)+1)/7);return `${d.getUTCFullYear()}-W${String(w).padStart(2,'0')}`}
function period(row){const d=row.d||'';return ce('cmp-group').value==='year'?d.slice(0,4):ce('cmp-group').value==='month'?d.slice(0,7):weekKey(d)}
function baseRows(){const country=ce('cmp-country').value,action=ce('cmp-action').value,type=ce('cmp-type').value,evidence=ce('cmp-evidence').value,from=ce('cmp-from').value,to=ce('cmp-to').value;return corpus.filter(x=>(!country||x.c===country)&&(!action||x.at===action)&&(!type||x.st===type)&&(!evidence||(evidence==='direct'?x.di:!x.di))&&(!from||x.d>=from)&&(!to||x.d<=to))}
function counts(rows,pid){const out={};for(const x of rows){if(pid&&x.p!==pid)continue;const k=period(x);out[k]=(out[k]||0)+1}return out}
function seriesName(pid,fallback){const hit=corpus.find(x=>x.p===pid);return pid?(hit?.pn||pid):fallback}
function renderChart(periods,a,b,nameA,nameB){const svg=ce('cmp-chart'),W=900,H=360,L=55,R=20,T=35,B=70,inner=W-L-R,max=Math.max(1,...periods.flatMap(k=>[a[k]||0,b[k]||0])),step=inner/Math.max(1,periods.length),bw=Math.max(2,Math.min(18,step*(nameB?.length?0.34:0.55)));let s=`<rect width="${W}" height="${H}" fill="#fff"/><line x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}" stroke="#0A1B2E"/><line x1="${L}" y1="${T}" x2="${L}" y2="${H-B}" stroke="#0A1B2E"/>`;for(let i=0;i<=4;i++){const val=Math.round(max*i/4),y=H-B-(H-B-T)*i/4;s+=`<line x1="${L}" y1="${y}" x2="${W-R}" y2="${y}" stroke="#DCE3E6"/><text x="${L-8}" y="${y+4}" text-anchor="end" font-size="11" fill="#5C6670">${val}</text>`}const every=Math.max(1,Math.ceil(periods.length/10));periods.forEach((k,i)=>{const x=L+step*i+step/2,ha=(a[k]||0)/max*(H-B-T),hb=(b[k]||0)/max*(H-B-T);s+=`<rect x="${x-bw-(nameB?2:0)}" y="${H-B-ha}" width="${bw}" height="${ha}" fill="#00A3C8"><title>${esc(nameA)} · ${esc(k)}: ${a[k]||0}</title></rect>`;if(nameB)s+=`<rect x="${x+2}" y="${H-B-hb}" width="${bw}" height="${hb}" fill="#0A1B2E"><title>${esc(nameB)} · ${esc(k)}: ${b[k]||0}</title></rect>`;if(i%every===0)s+=`<text x="${x}" y="${H-B+17}" transform="rotate(40 ${x} ${H-B+17})" font-size="10" fill="#5C6670">${esc(k)}</text>`});s+=`<rect x="${L}" y="12" width="10" height="10" fill="#00A3C8"/><text x="${L+15}" y="21" font-size="11">${esc(nameA)}</text>`;if(nameB)s+=`<rect x="${L+220}" y="12" width="10" height="10" fill="#0A1B2E"/><text x="${L+235}" y="21" font-size="11">${esc(nameB)}</text>`;svg.innerHTML=s}
function update(){current=baseRows();const pa=ce('cmp-a').value,pb=ce('cmp-b').value,a=counts(current,pa),b=counts(current,pb),periods=[...new Set([...Object.keys(a),...Object.keys(b)])].sort(),nameA=seriesName(pa,'All matching records'),nameB=pb?seriesName(pb,''):'';renderChart(periods,a,b,nameA,nameB);ce('cmp-head-a').textContent=nameA;ce('cmp-head-b').textContent=nameB||'—';ce('cmp-table').innerHTML=periods.map(k=>`<tr><td>${esc(k)}</td><td>${a[k]||0}</td><td>${nameB?(b[k]||0):'—'}</td></tr>`).join('');const selected=current.filter(x=>(!pa||x.p===pa)&&(!pb||x.p===pb));ce('cmp-status').textContent=`${selected.length} displayed record${selected.length===1?'':'s'} from ${current.length} matching the shared filters. ${periods.length} time period${periods.length===1?'':'s'}.`}
function save(name,type,text){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function exportRows(){const pa=ce('cmp-a').value,pb=ce('cmp-b').value;return current.filter(x=>(!pa&&!pb)||x.p===pa||x.p===pb)}
function csv(rows){const cols=['id','w','d','c','p','pn','at','st','pr','di','ti','s','u','au'];return [cols.join(','),...rows.map(r=>cols.map(k=>`"${String(r[k]??'').replaceAll('"','""')}"`).join(','))].join('\n')}
function bib(rows){return rows.map(r=>`@misc{rapport_${r.id},\n  author = {${r.pn||r.p}},\n  title = {${r.ti||r.s||'RAPPORT evidence record'}},\n  year = {${(r.d||'').slice(0,4)}},\n  url = {${r.au||r.u||''}},\n  note = {RAPPORT record ${r.id}; accessed ${r.ca||''}}\n}`).join('\n\n')}
function ris(rows){return rows.map(r=>`TY  - ELEC\nAU  - ${r.pn||r.p}\nTI  - ${r.ti||r.s||'RAPPORT evidence record'}\nPY  - ${(r.d||'').slice(0,4)}\nUR  - ${r.au||r.u||''}\nN1  - RAPPORT record ${r.id}\nER  -`).join('\n\n')}
fields.forEach(id=>ce(id).addEventListener('input',update));ce('cmp-reset').addEventListener('click',()=>{fields.forEach(id=>{if(id!=='cmp-group')ce(id).value=''});ce('cmp-group').value='week';update()});
ce('cmp-svg').addEventListener('click',()=>save('rapport-comparison.svg','image/svg+xml',new XMLSerializer().serializeToString(ce('cmp-chart'))));
ce('cmp-png').addEventListener('click',()=>{const svg=new XMLSerializer().serializeToString(ce('cmp-chart')),img=new Image(),url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));img.onload=()=>{const canvas=document.createElement('canvas');canvas.width=1800;canvas.height=720;canvas.getContext('2d').drawImage(img,0,0,1800,720);canvas.toBlob(blob=>{const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='rapport-comparison.png';a.click()},'image/png');URL.revokeObjectURL(url)};img.src=url});
ce('cmp-csv').addEventListener('click',()=>save('rapport-filtered.csv','text/csv',csv(exportRows())));ce('cmp-json').addEventListener('click',()=>save('rapport-filtered.json','application/json',JSON.stringify(exportRows(),null,2)));ce('cmp-bib').addEventListener('click',()=>save('rapport-filtered.bib','application/x-bibtex',bib(exportRows())));ce('cmp-ris').addEventListener('click',()=>save('rapport-filtered.ris','application/x-research-info-systems',ris(exportRows())));
async function load(){try{const idx=await fetch('corpus/index.json').then(r=>r.json());corpus=(await Promise.all(idx.years.map(y=>fetch(`corpus/${y}.json`).then(r=>r.json())))).flat();const opts=(id,vals)=>vals.forEach(([v,l])=>ce(id).insertAdjacentHTML('beforeend',`<option value="${esc(v)}">${esc(l)}</option>`));const parties=[...new Map(corpus.map(x=>[x.p,x.pn||x.p])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));opts('cmp-a',parties);opts('cmp-b',parties);opts('cmp-country',[...new Set(corpus.map(x=>x.c).filter(Boolean))].sort().map(x=>[x,x]));opts('cmp-action',[...new Set(corpus.map(x=>x.at).filter(Boolean))].sort().map(x=>[x,x]));opts('cmp-type',[...new Set(corpus.map(x=>x.st).filter(Boolean))].sort().map(x=>[x,x.replaceAll('_',' ')]));update()}catch(err){ce('cmp-status').textContent='The corpus could not be loaded. Open this page through the published GitHub Pages URL.'}}load();
</script>'''
    path = os.path.join(out_dir, "compare.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Compare parties and periods", body, subtitle="interactive longitudinal explorer"))
    return path


def quotes_page(out_dir):
    """Client-side quotation explorer with translation-audit filters."""
    body = r'''<h1>Quotation explorer</h1>
<p class="lede">Search captured source-language quotations and AI English translations.
A quotation is evidence only when its record links to a checkable source or preserved snapshot.</p>
<div class="research-tool"><div class="tool-grid">
<label>Words<input id="quote-q" type="search" placeholder="quotation, speaker, or party"></label>
<label>Party<select id="quote-party"><option value="">All parties</option></select></label>
<label>Language<select id="quote-lang"><option value="">All languages</option></select></label>
<label>Translation status<select id="quote-audit"><option value="">All quotations</option>
<option value="translated">AI-translated</option><option value="audited">Round-trip audited</option>
<option value="flagged">Audit flagged</option><option value="original">No separate translation</option></select></label>
</div><div class="tool-actions"><button id="quote-csv" type="button">Download filtered quotations</button></div></div>
<p id="quote-status" class="meta">Loading quotations…</p><div id="quote-results"></div>
<script>
const qe=id=>document.getElementById(id),qesc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let quotes=[],visible=[];
function showQuotes(){const q=qe('quote-q').value.trim().toLocaleLowerCase(),p=qe('quote-party').value,l=qe('quote-lang').value,a=qe('quote-audit').value;visible=quotes.filter(x=>(!q||[x.o,x.t,x.sp,x.pn,x.ti].join(' ').toLocaleLowerCase().includes(q))&&(!p||x.p===p)&&(!l||x.l===l)&&(!a||(a==='translated'&&x.translated)||(a==='audited'&&x.audited)||(a==='flagged'&&x.flagged)||(a==='original'&&!x.translated)));qe('quote-status').textContent=`${visible.length} matching quotation${visible.length===1?'':'s'}${visible.length>200?' (first 200 shown)':''}.`;qe('quote-results').innerHTML=visible.slice(0,200).map(x=>`<article class="quote-result"><p class="meta"><a href="issues/${encodeURIComponent(x.w)}.html#item-${encodeURIComponent(x.id)}">${qesc(x.pn)}</a> · ${qesc(x.d)} · ${qesc(x.sp||'speaker not recorded')} · ${qesc(x.l||'language unknown')}</p><blockquote${['he','ar'].includes(x.l)?' dir="rtl"':''}><div class="orig">${qesc(x.o)}</div>${x.translated?`<div class="tr">${qesc(x.t)}</div>`:''}</blockquote><div class="ai-labels"><span class="ai-label">Source quotation</span>${x.translated?'<span class="ai-label ai">AI translation</span>':''}${x.audited?`<span class="ai-label ai">Round-trip audit${x.flagged?' · flagged':''}</span>`:'<span class="ai-label">Not translation-audited</span>'}</div><p class="meta">${qesc(x.ti)}</p></article>`).join('')||'<div class="box dashed">No quotations match.</div>'}
function saveQuoteCsv(){const cols=['record_id','week','date','party_id','party','language','speaker','original','translation','audited','flagged','source_url','stable_record'];const rows=visible.map(x=>[x.id,x.w,x.d,x.p,x.pn,x.l,x.sp,x.o,x.t,x.audited,x.flagged,x.u,`issues/${x.w}.html#item-${x.id}`]);const text=[cols,...rows].map(r=>r.map(v=>`"${String(v??'').replaceAll('"','""')}"`).join(',')).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/csv'}));a.download='rapport-quotations.csv';a.click()}
['quote-q','quote-party','quote-lang','quote-audit'].forEach(id=>qe(id).addEventListener('input',showQuotes));qe('quote-csv').addEventListener('click',saveQuoteCsv);
async function loadQuotes(){try{const idx=await fetch('corpus/index.json').then(r=>r.json()),rows=(await Promise.all(idx.years.map(y=>fetch(`corpus/${y}.json`).then(r=>r.json())))).flat();for(const x of rows){(x.q||[]).forEach((q,i)=>{const audit=(x.bt||[]).find(b=>b.i===i);quotes.push({...q,id:x.id,w:x.w,d:x.d,p:x.p,pn:x.pn,l:x.l,ti:x.ti,u:x.u,translated:!!(q.t&&q.t!==q.o),audited:!!audit,flagged:!!audit?.f})})}const parties=[...new Map(quotes.map(x=>[x.p,x.pn||x.p])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));parties.forEach(([v,l])=>qe('quote-party').insertAdjacentHTML('beforeend',`<option value="${qesc(v)}">${qesc(l)}</option>`));[...new Set(quotes.map(x=>x.l).filter(Boolean))].sort().forEach(v=>qe('quote-lang').insertAdjacentHTML('beforeend',`<option>${qesc(v)}</option>`));showQuotes()}catch(err){qe('quote-status').textContent='The corpus could not be loaded. Open this page through the published GitHub Pages URL.'}}loadQuotes();
</script>'''
    path = os.path.join(out_dir, "quotes.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Quotation explorer", body, subtitle="source text and translation audit"))
    return path


def quality_page(parties, items, collection_history, weeks, prompt_versions,
                 research, reliability_reports, out_dir):
    """Validation, coverage, language quality, missingness, and collection funnel."""
    retained = [row for row in items if (row.get("analysis") or {}).get("relevant")]
    direct = [row for row in retained if is_party_document(row)]
    human = [row for row in retained if row.get("code_detail")]
    top = max(1, len(items))
    funnel = [
        ("Collected", len(items)),
        ("Screened", sum(bool(row.get("analysis")) for row in items)),
        ("Retained", len(retained)),
        ("Direct evidence", len(direct)),
        ("Human-coded", len(human)),
    ]
    body = ['<h1>Quality and validation</h1>',
            '<p class="lede">This dashboard separates collection coverage, automated '
            'confidence, translation checks, and human validation. They answer different '
            'questions and are never combined into a single score.</p>']
    validation = (research or {}).get("validation") or {}
    status = validation.get("status") or "Validation status not configured"
    banner = "ok" if reliability_reports else "warn"
    body.append(f'<div class="status-banner {banner}"><strong>{e(status)}</strong>'
                f'<p>{e(validation.get("statement") or "No validation statement is on file.")}</p></div>')
    body.append('<div class="statline">'
                f'<div class="stat"><div class="v">{len(retained)}</div><div class="k">retained records</div></div>'
                f'<div class="stat"><div class="v">{len(direct)}</div><div class="k">direct records</div></div>'
                f'<div class="stat"><div class="v">{len(human)}</div><div class="k">human-coded records</div></div>'
                f'<div class="stat"><div class="v">{len(reliability_reports)}</div><div class="k">completed blind rounds</div></div></div>')

    body.append('<h2>Collection funnel</h2><p class="meta">Counts describe the current '
                'database. Retention is automated unless a human-coding label is shown.</p><div class="funnel">')
    for label, count in funnel:
        body.append(f'<div class="funnel-row"><span>{e(label)}</span><span class="funnel-track">'
                    f'<i style="width:{100 * count / top:.2f}%"></i></span><strong>{count}</strong></div>')
    body.append('</div>')

    recent_weeks = sorted(weeks, reverse=True)[:12]
    logs = defaultdict(list)
    for row in collection_history:
        logs[(row.get("party_id"), row.get("week"))].append(row)
    record_counts = Counter((row.get("party_id"), row.get("week")) for row in retained)
    body.append('<h2>Coverage matrix</h2><p class="meta">✓n = at least one successful '
                'collection channel and n retained records; ! = every archived attempt failed; '
                '— = no archived attempt. A successful zero is not evidence of political silence.</p>'
                '<div class="matrix-wrap"><table class="matrix"><thead><tr><th>Party</th><th>Country</th>')
    body.extend(f'<th>{e(week)}</th>' for week in recent_weeks)
    body.append('</tr></thead><tbody>')
    for party in sorted(parties, key=lambda p: (p.get("country", ""), p.get("short", ""))):
        pid = party["id"]
        body.append(f'<tr><td><a href="parties/{e(pid)}.html">{e(party.get("short") or pid)}</a></td>'
                    f'<td>{e(party.get("country"))}</td>')
        for week in recent_weeks:
            attempts = logs.get((pid, week), [])
            n = record_counts.get((pid, week), 0)
            if not attempts:
                value, cls, title = "—", "zero", "No archived collection attempt"
            elif any(row.get("ok") for row in attempts):
                value, cls, title = f"✓{n}", ("" if n else "zero"), "At least one channel completed"
            else:
                value, cls, title = "!", "zero", "; ".join(row.get("error") or "failed" for row in attempts)[:240]
            body.append(f'<td class="{cls}" title="{e(title)}">{e(value)}</td>')
        body.append('</tr>')
    body.append('</tbody></table></div>')

    lang_rows = []
    for lang in sorted({row.get("lang") or "unknown" for row in retained}):
        mine = [row for row in retained if (row.get("lang") or "unknown") == lang]
        translated = [row for row in mine if any(
            q.get("translation") and q.get("translation") != q.get("original")
            for q in (row.get("analysis") or {}).get("quotes") or [])]
        audited = [row for row in mine if row.get("backtranslation")]
        flagged = [row for row in audited if any(x.get("flagged") for x in row.get("backtranslation") or [])]
        lang_rows.append(f'<tr><td>{e(lang)}</td><td class="n">{len(mine)}</td>'
                         f'<td class="n">{len(translated)}</td><td class="n">{len(audited)}</td>'
                         f'<td class="n">{len(flagged)}</td></tr>')
    body.append('<h2>Language-quality dashboard</h2><table class="rev"><thead><tr>'
                '<th>Source language</th><th>Retained</th><th>With AI translation</th>'
                '<th>Round-trip audited</th><th>Flagged</th></tr></thead><tbody>'
                + "".join(lang_rows) + '</tbody></table><p class="table-note">A round-trip '
                'check is an automated diagnostic, not human translation validation.</p>')

    party_ids = {row.get("party_id") for row in retained}
    logged_ids = {row.get("party_id") for row in collection_history}
    warnings = []
    no_site = [p for p in parties if not p.get("site")]
    no_log = [p for p in parties if p["id"] not in logged_ids]
    no_record = [p for p in parties if p["id"] not in party_ids]
    if no_site:
        warnings.append(f'{len(no_site)} party/parties lack a verified official website and use search fallback: '
                        + ", ".join(p.get("short") or p["id"] for p in no_site))
    if no_log:
        warnings.append(f'{len(no_log)} party/parties have no archived collection log: '
                        + ", ".join(p.get("short") or p["id"] for p in no_log))
    if no_record:
        warnings.append(f'{len(no_record)} party/parties have no retained record in the current database: '
                        + ", ".join(p.get("short") or p["id"] for p in no_record))
    if not human:
        warnings.append("No retained record has a completed researcher code in the current database.")
    body.append('<h2>Missing-data warnings</h2><ul>'
                + "".join(f'<li>{e(warning)}</li>' for warning in warnings)
                + '</ul>')

    body.append('<h2>Confidence dimensions</h2><p>These labels are displayed on every '
                'full evidence card. They are descriptive checks, not probabilities.</p><dl>')
    for key, value in ((research or {}).get("confidence_dimensions") or {}).items():
        body.append(f'<dt><strong>{e(str(key).replace("_", " ").title())}</strong></dt><dd>{e(value)}</dd>')
    body.append('</dl><h2>Prompt and model coverage</h2><table class="rev"><thead><tr>'
                '<th>Stage</th><th>Model</th><th>Prompt</th><th>Records</th><th>First</th><th>Last</th>'
                '</tr></thead><tbody>')
    for row in prompt_versions:
        body.append(f'<tr><td>{e(row.get("stage"))}</td><td>{e(row.get("model"))}</td>'
                    f'<td>{e(row.get("prompt_ver"))}</td><td class="n">{row.get("n", 0)}</td>'
                    f'<td>{e(str(row.get("first") or "")[:10])}</td>'
                    f'<td>{e(str(row.get("last") or "")[:10])}</td></tr>')
    body.append('</tbody></table>')
    path = os.path.join(out_dir, "quality.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Quality and validation", "".join(body), subtitle="coverage, missingness, validation"))
    return path


def source_registry_page(parties, collection_history, out_dir):
    channels = defaultdict(set)
    by_party_week = defaultdict(list)
    for row in collection_history:
        by_party_week[(row.get("party_id"), row.get("week"))].append(row)
        channels[row.get("party_id")].add(row.get("channel") or "unknown")
    latest = {}
    for (pid, week), attempts in by_party_week.items():
        if not latest.get(pid) or str(week or "") > str(latest[pid].get("week") or ""):
            latest[pid] = {"week": week, "ok": any(row.get("ok") for row in attempts),
                           "successes": sum(bool(row.get("ok")) for row in attempts),
                           "attempts": len(attempts)}
    rows = []
    for party in sorted(parties, key=lambda p: (p.get("country", ""), p.get("short", ""))):
        pid = party["id"]
        site = party.get("site")
        site_html = (f'<a href="{e(site)}" rel="noreferrer">{e(urlparse(site).netloc)}</a>'
                     if site else '<span class="hstate never">not verified</span>')
        last = latest.get(pid) or {}
        state = (f'{last.get("successes", 0)}/{last.get("attempts", 0)} channels succeeded'
                 if last else "no log")
        queries = "; ".join(party.get("queries") or [])
        rows.append(f'<tr><td><a href="parties/{e(pid)}.html">{e(party.get("short") or pid)}</a></td>'
                    f'<td>{e(party.get("country"))}</td><td>{e(camp_label(party.get("camp")))}</td>'
                    f'<td>{site_html}</td><td>{e(party.get("lang") or "")}</td>'
                    f'<td>{e(", ".join(sorted(channels.get(pid) or {"web/news search"})))}</td>'
                    f'<td>{e(last.get("week") or "—")} · {e(state)}</td>'
                    f'<td class="meta">{e(queries)}</td></tr>')
    body = ('<h1>Source registry</h1><p class="lede">Every configured party source, '
            'discovery route, and latest archived collection state. A website link means '
            'the URL is configured—not that every page was reachable in every week.</p>'
            '<div class="matrix-wrap"><table class="matrix"><thead><tr><th>Party</th>'
            '<th>Country</th><th>Research family</th><th>Official site</th><th>Language</th>'
            '<th>Observed channels</th><th>Latest attempt</th><th>Discovery terms</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
            '<p class="table-note">Source health is historical and auditable on the '
            '<a href="health.html">Collection status</a> page.</p>')
    path = os.path.join(out_dir, "sources.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Source registry", body, subtitle=f"{len(parties)} party configurations"))
    return path


def inclusion_page(parties, research, representation, out_dir):
    body = ['<h1>Party-inclusion dossiers</h1>',
            '<p class="lede">The roster is a documented research decision, not a claim '
            'that every monitored party is equivalent or that its self-description matches '
            'the project’s operational family.</p><h2>Inclusion rules</h2><ol>']
    body.extend(f'<li>{e(rule)}</li>' for rule in (research or {}).get("inclusion_rules") or [])
    body.append('</ol><h2>Exclusion rules</h2><ol>')
    body.extend(f'<li>{e(rule)}</li>' for rule in (research or {}).get("exclusion_rules") or [])
    body.append('</ol><h2>Dossiers</h2>')
    notes = (research or {}).get("party_notes") or {}
    country_sources = (representation or {}).get("country_sources") or {}
    for party in sorted(parties, key=lambda p: (p.get("country", ""), p.get("short", ""))):
        note = notes.get(party["id"]) or {}
        sources = []
        if party.get("site"):
            sources.append(f'<a href="{e(party["site"])}" rel="noreferrer">official website</a>')
        else:
            sources.append('<strong>official website not verified; web/news search fallback</strong>')
        electoral = (country_sources.get(party.get("country")) or {}).get("elections") or {}
        if electoral.get("url"):
            sources.append(f'<a href="{e(electoral["url"])}" rel="noreferrer">{e(electoral.get("label") or "election authority")}</a>')
        refs = "".join(f'<li><a href="{e(ref.get("url"))}" rel="noreferrer">{e(ref.get("label"))}</a></li>'
                       for ref in note.get("references") or [])
        rationale = note.get("rationale") or (
            f'Monitored in the researcher-defined {camp_label(party.get("camp"))} comparison '
            'family under the published inclusion rules. This entry requires periodic review '
            'against electoral activity and official materials.')
        body.append(f'<details class="country-section"><summary><span>{e(party.get("short") or party["id"])} '
                    f'<span class="meta">{e(party.get("country"))}</span></span>'
                    f'<span class="summary-count">{e(camp_label(party.get("camp")))}</span></summary>'
                    f'<div class="country-content"><p><strong>Full name:</strong> {e(party.get("name"))}</p>'
                    f'<p><strong>Rationale:</strong> {e(rationale)}</p>'
                    f'<p><strong>Status:</strong> {e(note.get("status") or "Active monitoring configuration")}</p>'
                    f'<p><strong>Evidence routes:</strong> {" · ".join(sources)}</p>'
                    f'<p><strong>Discovery terms:</strong> {e("; ".join(party.get("queries") or []))}</p>'
                    + (f'<ul>{refs}</ul>' if refs else '') + '</div></details>')
    path = os.path.join(out_dir, "inclusion.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Party-inclusion dossiers", "".join(body), subtitle=f"{len(parties)} documented roster entries"))
    return path


def prompts_page(prompt_archive, prompt_versions, out_dir):
    represented = {(row.get("stage"), row.get("prompt_ver")): row for row in prompt_versions}
    body = ['<h1>Prompt archive</h1>',
            '<p class="lede">Versioned instructions used for AI-assisted stages. Dynamic '
            'source text is not republished here; the template shows which contextual fields '
            'were supplied. A prompt version documents procedure, not model determinism.</p>']
    for prompt in (prompt_archive or {}).get("prompts") or []:
        key = (prompt.get("stage"), prompt.get("version"))
        seen = represented.get(key) or {}
        body.append(f'<section class="box"><h2>{e(prompt.get("stage"))} · {e(prompt.get("version"))}</h2>'
                    f'<p>{e(prompt.get("purpose"))}</p><p class="meta">Records in database: '
                    f'{seen.get("n", 0)} · model: {e(seen.get("model") or "not represented")}</p>'
                    f'<h3>System instruction</h3><pre class="bib">{e(prompt.get("system_prompt"))}</pre>'
                    f'<h3>Input template</h3><pre class="bib">{e(prompt.get("input_template"))}</pre>'
                    f'<h3>Expected output</h3><p>{e(prompt.get("output_schema"))}</p></section>')
    body.append(f'<p class="meta">Archive configuration version: '
                f'{e((prompt_archive or {}).get("archive_version") or "not stated")}.</p>')
    path = os.path.join(out_dir, "prompts.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Prompt archive", "".join(body), subtitle="versioned AI instructions"))
    return path


def elections_page(parties, representation, out_dir):
    profiles = (representation or {}).get("parties") or {}
    verified = []
    for party in parties:
        rows = ((profiles.get(party["id"]) or {}).get("elections") or {}).get("national") or []
        for row in rows:
            if row.get("source") and row.get("date") and row.get("seats") is not None:
                verified.append((party, row))
    body = ['<h1>Verified election series</h1>',
            '<p class="lede">Election and seat figures appear only when each observation '
            'has an institutional source. Missing series remain visibly missing rather than '
            'being inferred from press reports or carried forward.</p>']
    if not verified:
        body.append('<div class="status-banner warn"><strong>No party election series has '
                    'yet passed the source gate.</strong><p>The party pages link to official '
                    'election authorities while verification is pending.</p></div>')
    else:
        body.append('<table class="rev"><thead><tr><th>Party</th><th>Election</th><th>Seats</th>'
                    '<th>Vote share</th><th>Source</th></tr></thead><tbody>')
        for party, row in verified:
            body.append(f'<tr><td><a href="parties/{e(party["id"])}.html">{e(party.get("short"))}</a></td>'
                        f'<td>{e(row.get("date"))}</td><td>{e(row.get("seats"))} / {e(row.get("total"))}</td>'
                        f'<td>{e(row.get("vote_share"))}%</td><td><a href="{e(row.get("source"))}" '
                        'rel="noreferrer">official result</a></td></tr>')
        body.append('</tbody></table>')
    body.append('<h2>Official result registries</h2><ul class="link-list">')
    for code, row in sorted(((representation or {}).get("country_sources") or {}).items()):
        source = row.get("elections") or {}
        if source.get("url"):
            body.append(f'<li><a class="link-title" href="{e(source["url"])}" rel="noreferrer">'
                        f'{e(code)} · {e(source.get("label") or "Election authority")}</a></li>')
    body.append('</ul>')
    path = os.path.join(out_dir, "elections.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Verified election series", "".join(body), subtitle=f"{len(verified)} sourced observations"))
    return path


def events_page(events, items, parties, out_dir):
    by_id = {party["id"]: party for party in parties}
    body = ['<h1>Cross-party event view</h1>',
            '<p class="lede">Researcher-configured political events beside retained party '
            'records from the surrounding fourteen-day window. Proximity is context, not '
            'proof that an event caused a party response.</p>']
    for event in sorted(events or [], key=lambda x: x.get("date") or "", reverse=True):
        try:
            event_date = datetime.fromisoformat(str(event.get("date"))[:10]).date()
        except ValueError:
            event_date = None
        related = []
        for row in items:
            try:
                row_date = datetime.fromisoformat(str(row.get("published") or "")[:10]).date()
            except ValueError:
                continue
            if event_date and abs((row_date - event_date).days) <= 7 and (
                    row.get("party_id") in (event.get("parties") or []) or
                    row.get("country") in (event.get("countries") or [])):
                related.append(row)
        sources = "".join(f'<li><a href="{e(src.get("url"))}" rel="noreferrer">{e(src.get("label"))}</a></li>'
                          for src in event.get("sources") or [])
        records = "".join(
            f'<li><a href="issues/{e(row.get("week"))}.html#item-{e(row.get("id"))}">'
            f'{e(row.get("party_name") or row.get("party_id"))}: {e(row.get("title") or (row.get("analysis") or {}).get("summary"))}</a>'
            f' <span class="meta">{e(str(row.get("published") or "")[:10])}</span></li>'
            for row in sorted(related, key=lambda x: x.get("published") or "", reverse=True)[:30])
        party_names = ", ".join((by_id.get(pid) or {}).get("short", pid) for pid in event.get("parties") or [])
        body.append(f'<article class="event-card"><h2>{e(event.get("title"))}</h2>'
                    f'<p class="meta">{e(event.get("date"))} · {e(", ".join(event.get("countries") or []))} '
                    f'· configured parties: {e(party_names)}</p><p>{e(event.get("description"))}</p>'
                    f'<h3>Event sources</h3><ul>{sources or "<li>No event source configured.</li>"}</ul>'
                    f'<h3>Retained records within ±7 days</h3><ul>{records or "<li>No matching retained record.</li>"}</ul></article>')
    if not events:
        body.append('<div class="box dashed">No event contexts are configured.</div>')
    path = os.path.join(out_dir, "events.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Cross-party events", "".join(body), subtitle=f"{len(events or [])} configured events"))
    return path


def tutorials_page(out_dir):
    body = '''<h1>Usage tutorials</h1>
<p class="lede">Short workflows for reading RAPPORT as evidence rather than as an
authoritative summary of everything a party did.</p>
<h2>Read one weekly report</h2><div class="tutorial">
<div class="tutorial-step"><strong>Begin with the Research Passport.</strong> Check how many parties
had an archived collection attempt and how many records were screened and retained.</div>
<div class="tutorial-step"><strong>Read “The week in one minute”.</strong> Follow each point to its
stable evidence record instead of citing the overview alone.</div>
<div class="tutorial-step"><strong>Open Collection coverage.</strong> Distinguish a checked zero from
an inaccessible source or a missing run.</div>
<div class="tutorial-step"><strong>Inspect provenance.</strong> Use the original URL, captured date,
source class, model/prompt version, translation status, and human-review label.</div></div>
<h2>Compare parties or periods</h2><div class="tutorial">
<div class="tutorial-step">Open <a href="compare.html">Compare</a>, choose a date range and
party, country, evidence, or document-type filters.</div>
<div class="tutorial-step">Treat chart counts as retained-document counts, not public support,
ideological intensity, or total political activity.</div>
<div class="tutorial-step">Download the figure and the exact filtered CSV/JSON used to make it.</div></div>
<h2>Reuse data in research or teaching</h2><div class="tutorial">
<div class="tutorial-step">Download annual corpus shards or weekly CSV files from the
<a href="dataset.html">dataset page</a>.</div>
<div class="tutorial-step">Start with the replication notebook and preserve the dataset version,
download date, filters, and stable record links.</div>
<div class="tutorial-step">Use the teaching sample only for exercises. Its AI summaries are not
independently human-validated unless the row explicitly says otherwise.</div></div>'''
    path = os.path.join(out_dir, "tutorials.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Usage tutorials", body, subtitle="how to use RAPPORT"))
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
            f'{camp_label(c.get("camp"))}</span></h4>'
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


def parties_page(parties, totals, country_names, out_dir, representation=None):
    """A single sortable directory; alphabetical by English name by default."""
    profiles = ((representation or {}).get("parties") or {})
    ordered = sorted(parties, key=lambda p: (party_display_name(p).casefold(), p["id"]))
    country_options = "".join(
        f'<option value="{e(code)}">{e(country_names.get(code, code))}</option>'
        for code in sorted({p.get("country") for p in parties if p.get("country")},
                           key=lambda code: country_names.get(code, code))
    )
    rows = []
    for party in ordered:
        country_code = party.get("country") or ""
        country = country_names.get(country_code, country_code)
        family = camp_label(party.get("camp"))
        current = (profiles.get(party["id"], {}).get("current") or {}).get("national") or {}
        verified = current.get("seats") is not None and bool(current.get("total"))
        seats = int(current.get("seats") or 0) if verified else -1
        total = int(current.get("total") or 0) if verified else 0
        status = "represented" if seats > 0 else ("unrepresented" if verified else "pending")
        power = (f'{seats} / {total} national seats' if verified
                 else 'national seat total pending')
        records = int(totals.get(party["id"], 0))
        rows.append(
            f'<article class="party-row {e(party.get("camp") or "right")}" '
            f'data-name="{e(party_display_name(party).casefold())}" '
            f'data-country="{e(country_code)}" data-country-name="{e(country.casefold())}" '
            f'data-family="{e(party.get("camp") or "right")}" data-status="{status}" '
            f'data-records="{records}" data-seats="{seats}">'
            '<span class="party-camp-mark" aria-hidden="true"></span>'
            '<div class="party-row-main">'
            f'<h2><a href="parties/{e(party["id"])}.html">{e(party_display_name(party))}</a></h2>'
            f'<div class="party-tags"><span class="party-tag">{e(country)}</span>'
            f'<span class="party-tag">{e(family)}</span>'
            f'<span class="party-tag power">{e(power)}</span></div></div>'
            f'<div class="party-row-records"><strong>{records}</strong>'
            f'<span>{"record" if records == 1 else "records"}</span></div></article>'
        )

    body = f'''<h1>Parties</h1><p class="lede">{len(parties)} parties across
{len({p.get("country") for p in parties if p.get("country")})} countries. Names follow
English / original language (acronym). Political-power figures are dated on each profile.</p>
<div class="party-directory-tools" role="search" aria-label="Filter and sort parties">
 <label>Find a party<input id="party-query" type="search" placeholder="Name or acronym" autocomplete="off"></label>
 <label>Country<select id="party-country"><option value="">All countries</option>{country_options}</select></label>
 <label>Party family<select id="party-family"><option value="">Both families</option>
  <option value="left">far-left</option><option value="right">far-right</option></select></label>
 <label>National parliament<select id="party-status"><option value="">Any status</option>
  <option value="represented">Represented</option><option value="unrepresented">No seats</option>
  <option value="pending">Verification pending</option></select></label>
 <label>Sort<select id="party-sort"><option value="name">Name A–Z</option>
  <option value="country">Country A–Z</option><option value="family">Party family</option>
  <option value="records">Most records</option><option value="seats">Most national seats</option></select></label>
 <div class="party-directory-status" id="party-count" aria-live="polite">{len(parties)} parties</div>
</div>
<div class="party-directory-list" id="party-grid">{''.join(rows)}</div>
<div class="party-directory-empty" id="party-empty" hidden>No parties match these filters.</div>
<script>
(() => {{
  const grid = document.getElementById('party-grid');
  const cards = [...grid.querySelectorAll('.party-row')];
  const query = document.getElementById('party-query');
  const country = document.getElementById('party-country');
  const family = document.getElementById('party-family');
  const status = document.getElementById('party-status');
  const sort = document.getElementById('party-sort');
  const count = document.getElementById('party-count');
  const empty = document.getElementById('party-empty');
  const text = value => (value || '').toLocaleLowerCase();
  function apply() {{
    const needle = text(query.value.trim());
    const visible = cards.filter(card => {{
      const matches = (!needle || text(card.textContent).includes(needle)) &&
        (!country.value || card.dataset.country === country.value) &&
        (!family.value || card.dataset.family === family.value) &&
        (!status.value || card.dataset.status === status.value);
      card.hidden = !matches;
      return matches;
    }});
    const compareText = (a, b, field) => a.dataset[field].localeCompare(
      b.dataset[field], undefined, {{sensitivity:'base'}});
    visible.sort((a, b) => {{
      if (sort.value === 'records') return Number(b.dataset.records) - Number(a.dataset.records) || compareText(a,b,'name');
      if (sort.value === 'seats') return Number(b.dataset.seats) - Number(a.dataset.seats) || compareText(a,b,'name');
      if (sort.value === 'country') return compareText(a,b,'countryName') || compareText(a,b,'name');
      if (sort.value === 'family') return compareText(a,b,'family') || compareText(a,b,'name');
      return compareText(a,b,'name');
    }});
    visible.forEach(card => grid.append(card));
    count.textContent = `${{visible.length}} ${{visible.length === 1 ? 'party' : 'parties'}}`;
    empty.hidden = visible.length !== 0;
  }}
  [query, country, family, status, sort].forEach(control => control.addEventListener(
    control === query ? 'input' : 'change', apply));
  apply();
}})();
</script>'''
    path = os.path.join(out_dir, "parties.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout("Parties", body, subtitle=f"{len(parties)} monitored"))
    return path


MAP_ISO3 = {
    "GR": ("GRC",), "DE": ("DEU",), "FR": ("FRA",), "AT": ("AUT",),
    "NL": ("NLD",), "BE": ("BEL",), "SE": ("SWE",), "FI": ("FIN",),
    "IT": ("ITA",), "ES": ("ESP",), "GB": ("GBR",), "IL": ("ISR",),
    # Natural Earth keeps the island's internationally recognised government
    # and the de-facto northern administration as separate geometries.  Both
    # shapes open the single Cyprus entry in this research roster.
    "CY": ("CYP", "CYN"),
    "PT": ("PRT",), "NO": ("NOR",), "DK": ("DNK",), "IE": ("IRL",),
    "LU": ("LUX",), "CH": ("CHE",), "IS": ("ISL",),
}

# Enlarged pointer targets for the two smallest/easternmost monitored shapes.
# The visible country outline remains the geographic source of truth.
MAP_MARKERS = {"CY": (33.1, 35.0), "IL": (35.0, 31.5), "MT": (14.4, 35.9)}


def _map_geometry():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        "config", "map_geometry.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"viewBox": "0 0 900 560", "extent": [-25, 28, 45, 72],
                "features": [], "source": "Natural Earth",
                "source_url": "https://www.naturalearthdata.com/"}


def _home_map(parties, country_names):
    """Build a no-dependency SVG map from the roster and bundled geometry."""
    by_country = {}
    for party in parties:
        code = party.get("country")
        if code:
            by_country.setdefault(code, []).append(party)
    for plist in by_country.values():
        plist.sort(key=lambda p: (p.get("camp") != "right",
                                  p.get("short") or p.get("name") or p["id"]))

    geometry = _map_geometry()
    features = {f.get("code"): f for f in geometry.get("features", [])}
    tracked_shapes = {iso3 for code in by_country for iso3 in MAP_ISO3.get(code, ())}
    background = "".join(
        f'<path class="map-country" d="{e(feature.get("d"))}">'
        f'<title>{e(feature.get("name"))}</title></path>'
        for code, feature in features.items() if code not in tracked_shapes)

    lon_min, lat_min, lon_max, lat_max = geometry.get("extent", [-25, 28, 45, 72])
    view = [float(x) for x in str(geometry.get("viewBox", "0 0 900 560")).split()]
    width, height = view[2], view[3]

    def project(lon, lat):
        return ((lon - lon_min) / (lon_max - lon_min) * width,
                (lat_max - lat) / (lat_max - lat_min) * height)

    records = {}
    watched = []
    directory = []
    for code in sorted(by_country, key=lambda c: country_names.get(c, c)):
        plist = by_country[code]
        name = country_names.get(code, code)
        party_records = [{"id": p["id"],
                          "name": party_display_name(p),
                          "camp": p.get("camp", "right"),
                          "label": camp_label(p.get("camp"))}
                         for p in plist]
        records[code] = {"name": name, "parties": party_records}
        label = f'{name}: ' + ", ".join(p["name"] for p in party_records)
        d = "".join(features.get(iso3, {}).get("d", "")
                    for iso3 in MAP_ISO3.get(code, ()))
        marker = ""
        if code in MAP_MARKERS:
            x, y = project(*MAP_MARKERS[code])
            marker = (f'<circle class="map-hit" cx="{x:.1f}" cy="{y:.1f}" r="14"/>'
                      f'<circle class="map-pin" cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>')
        if d or marker:
            watched.append(
                f'<a class="map-country-link" href="#map-detail" data-country="{e(code)}" '
                f'aria-label="{e(label)}"><path class="map-country" d="{e(d)}">'
                f'<title>{e(label)}</title></path>{marker}</a>')
        links = ", ".join(
            f'<a href="parties/{e(p["id"])}.html">{e(p["name"])}</a>'
            for p in party_records)
        directory.append(
            f'<div class="country-directory-item"><strong>{e(name)} · {len(plist)}</strong>'
            f'<span>{links}</span></div>')

    israel_inset = ""
    israel_path = features.get("ISR", {}).get("d", "")
    if "IL" in by_country and israel_path:
        label = "Israel: " + ", ".join(p["name"] for p in records["IL"]["parties"])
        israel_inset = (
            '<g class="map-inset"><rect class="map-inset-box" x="764" y="360" '
            'width="92" height="150" rx="3"/><text class="map-inset-label" '
            'x="810" y="380">Israel</text><text class="map-inset-note" x="810" '
            'y="494">enlarged</text><a class="map-country-link" href="#map-detail" '
            f'data-country="IL" aria-label="{e(label)}"><path class="map-country" '
            f'd="{e(israel_path)}" transform="translate(810 435) scale(2.35) '
            'translate(-772 -517)"><title>' + e(label) + '</title></path></a></g>')

    data = json.dumps(records, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    script = """<script>
(() => {
  const records = __MAP_DATA__;
  const map = document.getElementById('party-map');
  const tip = document.getElementById('map-tooltip');
  const tipCountry = document.getElementById('map-tooltip-country');
  const tipParties = document.getElementById('map-tooltip-parties');
  const detail = document.getElementById('map-detail');
  const detailCountry = document.getElementById('map-detail-country');
  const detailIntro = document.getElementById('map-detail-intro');
  const detailParties = document.getElementById('map-detail-parties');
  const targets = [...document.querySelectorAll('.map-country-link')];

  function showCountry(code) {
    const record = records[code];
    if (!record) return;
    detailCountry.textContent = record.name;
    detailIntro.textContent = `${record.parties.length} ${record.parties.length === 1 ? 'party' : 'parties'} monitored`;
    detailParties.replaceChildren();
    for (const party of record.parties) {
      const link = document.createElement('a');
      link.className = `map-party ${party.camp === 'left' ? 'left' : 'right'}`;
      link.href = `parties/${encodeURIComponent(party.id)}.html`;
      const dot = document.createElement('span');
      dot.className = 'camp-dot';
      dot.setAttribute('aria-hidden', 'true');
      const name = document.createElement('span');
      name.textContent = party.name;
      const label = document.createElement('small');
      label.textContent = party.label;
      link.append(dot, name, label);
      detailParties.append(link);
    }
    for (const target of targets) {
      const active = target.dataset.country === code;
      target.classList.toggle('selected', active);
      if (active) target.setAttribute('aria-current', 'true');
      else target.removeAttribute('aria-current');
    }
  }

  function positionTip(event) {
    const box = map.getBoundingClientRect();
    let left = event.clientX - box.left + 14;
    let top = event.clientY - box.top + 14;
    if (left + tip.offsetWidth > box.width - 8) left = Math.max(8, left - tip.offsetWidth - 28);
    if (top + tip.offsetHeight > box.height - 8) top = Math.max(8, top - tip.offsetHeight - 28);
    tip.style.left = `${left}px`;
    tip.style.top = `${top}px`;
  }

  for (const target of targets) {
    target.addEventListener('pointerenter', event => {
      const record = records[target.dataset.country];
      showCountry(target.dataset.country);
      tipCountry.textContent = record.name;
      tipParties.textContent = record.parties.map(party => party.name).join(' · ');
      tip.hidden = false;
      positionTip(event);
    });
    target.addEventListener('pointermove', positionTip);
    target.addEventListener('pointerleave', () => { tip.hidden = true; });
    target.addEventListener('focus', () => {
      tip.hidden = true;
      showCountry(target.dataset.country);
    });
    target.addEventListener('click', event => {
      event.preventDefault();
      showCountry(target.dataset.country);
      if (window.matchMedia('(max-width: 850px)').matches) {
        const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        detail.scrollIntoView({behavior: reduced ? 'auto' : 'smooth', block: 'nearest'});
      }
    });
  }
  const initialCountry = records.DE ? 'DE' : Object.keys(records)[0];
  if (initialCountry) showCountry(initialCountry);
})();
</script>""".replace("__MAP_DATA__", data)

    source = geometry.get("source") or "Natural Earth"
    source_url = geometry.get("source_url") or "https://www.naturalearthdata.com/"
    return f"""<section class="map-section" aria-labelledby="map-heading">
<div class="section-kicker">Explore the monitored field</div>
<div class="map-section-head"><div class="map-section-title">
<h2 id="map-heading">Parties, placed in context.</h2>
<p>Select a country to see its monitored parties. Every party name opens a stable research dossier.</p></div>
<div class="map-legend" aria-label="Map legend"><span><i class="watched"></i>Monitored</span>
<span><i></i>Other country</span></div></div>
<div class="map-shell">
<div class="map-visual" id="party-map">
<svg class="map-svg" viewBox="{e(geometry.get('viewBox', '0 0 900 560'))}" role="img"
 aria-labelledby="map-title map-description">
 <title id="map-title">Countries monitored by {SITE_NAME}</title>
 <desc id="map-description">A map focused on Europe and Israel. Highlighted countries
 show the monitored parties when selected or pointed to.</desc>
 <rect class="map-sea" width="100%" height="100%"/>
 <g aria-hidden="true">{background}</g>
 <g>{''.join(watched)}</g>{israel_inset}
</svg>
<div class="map-tooltip" id="map-tooltip" role="tooltip" hidden>
 <strong id="map-tooltip-country"></strong><span id="map-tooltip-parties"></span>
</div></div>
<aside class="map-detail" id="map-detail" aria-live="polite">
 <span class="eyebrow">Monitored country</span>
 <h3 id="map-detail-country">Explore the map</h3>
 <p id="map-detail-intro">Move over a highlighted country, or select it, to see the parties tracked there.</p>
 <div class="map-party-list" id="map-detail-parties"></div>
</aside></div>
<p class="map-credit">Map geometry: <a href="{e(source_url)}">{e(source)}</a>.</p>
<details class="country-directory"><summary>Browse all monitored countries and parties</summary>
<div class="country-directory-grid">{''.join(directory)}</div></details>
</section>{script}"""


def home_page(latest, index, parties, country_names, out_dir, research=None):
    country_count = len({p.get("country") for p in parties if p.get("country")})
    research = research or {}
    version = str(research.get("version") or "unversioned")
    release = str(research.get("release_date") or "")
    try:
        release_label = datetime.fromisoformat(release).strftime("%-d %b %Y")
    except (TypeError, ValueError):
        release_label = release
    release_html = (f'<div class="site-release">Website version {e(version)}'
                    f'{" · " + e(release_label) if release_label else ""}</div>')
    total_records = sum(int(row.get("items") or 0) for row in index)
    latest_label = e(latest.get("week")) if latest else "No issue yet"
    status = f"""<div class="home-status" aria-label="Publication status">
<span class="status-dot" aria-hidden="true"></span>
<span><strong>Latest issue:</strong> {latest_label}</span>
<span><strong>Dataset:</strong> version {e(version)}</span>
<span><strong>Release:</strong> {e(release_label or 'not dated')}</span>
<a href="citation.html">How to cite RAPPORT</a></div>"""
    hero = f"""<header class="home-hero">
<div class="home-kicker">Automated academic research infrastructure</div>
<h1 class="home-title">A clearer weekly record of party activity.</h1>
<p class="home-lede">{e(SITE_DESCRIPTION)}</p>{release_html}
<p class="research-note">RAPPORT is an automated AI system powered by the Claude API,
created by <strong>Dr. Neil Bar</strong> solely for academic research into contemporary
far-right and far-left parties. Project information:
<a class="email" href="https://www.neilbar.com" rel="me">www.neilbar.com</a>.
AI-generated material may contain errors; consult the cited primary sources.</p></header>
<section class="front-stats" aria-label="Monitoring overview">
 <div class="front-stat"><span class="v">{country_count}</span><span class="k">countries monitored</span></div>
 <div class="front-stat"><span class="v">{len(parties)}</span><span class="k">active parties tracked</span></div>
 <div class="front-stat"><span class="v">{total_records}</span><span class="k">retained records in published reports</span></div>
 <div class="front-stat"><span class="v">Weekly</span><span class="k">collection and publication cycle</span></div>
</section>"""
    map_html = _home_map(parties, country_names)
    research_spine = """<section class="research-spine" aria-labelledby="research-spine-heading">
<div class="research-spine-head"><h2 id="research-spine-heading">The research spine</h2>
<p>Transparent methods, reusable records and stable references.</p></div>
<div class="research-spine-links">
 <a href="methodology.html"><strong>Methodology →</strong><span>Scope, inclusion rules, source hierarchy and AI-assisted workflow.</span></a>
 <a href="dataset.html"><strong>Dataset &amp; exports →</strong><span>Weekly CSV, JSON and citation-manager formats.</span></a>
 <a href="citation.html"><strong>Suggested citation →</strong><span>Stable references for the platform, issues and records.</span></a>
 <a href="quality.html"><strong>Quality &amp; validation →</strong><span>Coverage, review status and validation limits.</span></a>
</div></section>"""
    if not latest:
        latest_html = """<section class="latest-section" id="latest">
<div class="latest-head"><div><div class="section-kicker">Latest report</div>
<h2>The week, distilled.</h2></div></div>
<div class="box dashed"><p>No issues yet.</p>
<p class="meta">Run <code>python run.py weekly</code> to build the first one.</p></div></section>"""
        recent_html = ""
    else:
        latest_html = f"""<section class="latest-section" id="latest" aria-labelledby="latest-heading">
<div class="latest-head"><div><div class="section-kicker">Latest report</div>
<h2 id="latest-heading">The week, distilled.</h2></div>
<p>Read the report, inspect every record, or export the issue.</p></div>
<div class="latest-panel"><div>
 <span class="latest-label">Issue</span><span class="latest-week">{e(latest['week'])}</span>
 <span class="latest-range">{e(latest.get('range'))}</span>
 <p class="latest-summary">{e(latest.get('headline'))}</p></div>
<div><span class="latest-label">At a glance</span><div class="latest-numbers">
 <div class="latest-number"><strong>{int(latest.get('items') or 0)}</strong><span>retained records</span></div>
 <div class="latest-number"><strong>{int(latest.get('parties') or 0)}</strong><span>parties represented</span></div>
 <div class="latest-number"><strong>Published</strong><span>issue status</span></div>
</div></div>
<div><span class="latest-label">Issue tools</span><div class="latest-tools">
 <a class="primary" href="issues/{e(latest['week'])}.html"><span>Read report</span><span>↗</span></a>
 <a href="data/{e(latest['week'])}.csv" download><span>Download dataset</span><span>CSV ↓</span></a>
 <a href="archive.html"><span>View all reports</span><span>{len(index)} ↗</span></a>
</div></div></div></section>"""
        recent = "".join(
            f'<div class="grow"><span><a href="issues/{e(r["week"])}.html">{e(r["week"])}</a> '
            f'<span class="meta">{e(r["range"])}</span></span>'
            f'<span class="meta">{r["items"]} records</span></div>' for r in index[1:9])
        recent_html = (f'<section class="recent-section"><h2>Previous reports</h2>'
                       f'<div class="grid">{recent}</div><p class="recent-more">'
                       f'<a href="archive.html">Browse all {len(index)} reports</a> · '
                       '<a href="parties.html">Explore party dossiers</a></p></section>') if recent else ""
    body = (f'<div class="home-page">{status}{hero}{map_html}{latest_html}'
            f'{research_spine}{recent_html}</div>')
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(layout(SITE_NAME, body,
                       subtitle=f"{len(index)} issues"))
    return path


def scholarly_exports(items, research, out_dir):
    """Citation-manager files, teaching sample, and a no-key replication notebook."""
    downloads = os.path.join(out_dir, "downloads")
    os.makedirs(downloads, exist_ok=True)
    retained = [row for row in items if (row.get("analysis") or {}).get("relevant")]

    bib_rows, ris_rows = [], []
    for row in retained:
        title = row.get("title") or (row.get("analysis") or {}).get("summary") or "RAPPORT evidence record"
        party = row.get("party_full") or row.get("party_name") or row.get("party_id")
        stable = f'{PUBLIC_URL}issues/{row.get("week")}.html#item-{row.get("id")}'
        year = str(row.get("published") or "")[:4]
        key = f'rapport_{row.get("id")}'
        bib_rows.append("@misc{" + key + ",\n"
                        f"  author = {{{party}}},\n  title = {{{title}}},\n"
                        f"  year = {{{year}}},\n  url = {{{row.get('archive_url') or row.get('url') or stable}}},\n"
                        f"  note = {{RAPPORT record {row.get('id')}; stable record {stable}}}\n}}")
        ris_rows.append("\n".join([
            "TY  - ELEC", f"AU  - {party}", f"TI  - {title}", f"PY  - {year}",
            f"UR  - {row.get('archive_url') or row.get('url') or stable}",
            f"N1  - RAPPORT record {row.get('id')}; {stable}", "ER  -",
        ]))
    with open(os.path.join(downloads, "rapport-records.bib"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(bib_rows))
    with open(os.path.join(downloads, "rapport-records.ris"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(ris_rows))

    version = str((research or {}).get("version") or "unversioned")
    release = str((research or {}).get("release_date") or datetime.now(timezone.utc).date())
    cff = f'''cff-version: 1.2.0
message: "If you use RAPPORT, please cite the platform and the exact evidence records."
title: "RAPPORT: Radicalism and Party Politics: Observation, Reporting and Tracking"
type: dataset
authors:
  - family-names: Bar
    given-names: Neil
version: "{version}"
date-released: "{release}"
url: "{PUBLIC_URL}"
'''
    with open(os.path.join(out_dir, "CITATION.cff"), "w", encoding="utf-8") as f:
        f.write(cff)

    # A diverse, deterministic sample: first a recent direct record per party,
    # then additional records until the pedagogically manageable cap is met.
    ordered = sorted(retained, key=lambda row: (row.get("published") or "", row.get("id") or ""),
                     reverse=True)
    sample, used = [], set()
    for row in sorted(ordered, key=lambda x: not is_party_document(x)):
        if row.get("party_id") not in used:
            sample.append(row)
            used.add(row.get("party_id"))
    for row in ordered:
        if row not in sample and len(sample) < 60:
            sample.append(row)
    fields = ["record_id", "week", "date", "country", "party_id", "party",
              "research_family", "evidence_class", "document_type", "action_type",
              "title", "summary", "source_url", "stable_record_url",
              "summary_authorship", "human_validation_status"]
    with open(os.path.join(downloads, "rapport-teaching-sample.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in sample[:60]:
            writer.writerow({
                "record_id": row.get("id"), "week": row.get("week"),
                "date": str(row.get("published") or "")[:10], "country": row.get("country"),
                "party_id": row.get("party_id"), "party": row.get("party_name"),
                "research_family": camp_label(row.get("camp")),
                "evidence_class": "direct/official" if is_party_document(row) else "outside reporting",
                "document_type": row.get("source_type"), "action_type": trend_utils.action_type(row),
                "title": row.get("title"), "summary": (row.get("analysis") or {}).get("summary"),
                "source_url": row.get("url"),
                "stable_record_url": f'{PUBLIC_URL}issues/{row.get("week")}.html#item-{row.get("id")}',
                "summary_authorship": "AI-assisted or deterministic fallback",
                "human_validation_status": ("researcher-coded" if row.get("code_detail")
                                            else "not independently human-validated"),
            })

    notebook = {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                      "name": "python3"},
                     "language_info": {"name": "python", "version": "3"}},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": [
                "# RAPPORT replication quickstart\n",
                "Downloads the public annual shards, reproduces a party-week count, and preserves stable record links. "
                "Counts are retained documents, not total party activity.\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "import json, urllib.request\n", "import pandas as pd\n", "import matplotlib.pyplot as plt\n",
                f"BASE = '{PUBLIC_URL}'\n",
                "index = json.load(urllib.request.urlopen(BASE + 'corpus/index.json'))\n",
                "records = []\n", "for year in index['years']:\n",
                "    records.extend(json.load(urllib.request.urlopen(BASE + f'corpus/{year}.json')))\n",
                "df = pd.DataFrame(records)\n", "df.shape\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "# Example: direct/official records per party and ISO week\n",
                "direct = df[df['di'] == True].copy()\n",
                "counts = direct.groupby(['w', 'pn']).size().rename('records').reset_index()\n",
                "counts.sort_values(['w', 'records'], ascending=[True, False]).head(20)\n"]},
            {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [
                "# Reproduce a longitudinal figure for one party\n",
                "party_id = sorted(df['p'].dropna().unique())[0]\n",
                "series = df[df['p'].eq(party_id)].groupby('w').size()\n",
                "ax = series.plot(kind='bar', figsize=(10, 4), title=f'{party_id}: retained records')\n",
                "ax.set_ylabel('Retained records'); plt.tight_layout()\n"]},
            {"cell_type": "markdown", "metadata": {}, "source": [
                f"Dataset release: **{version}** ({release}). Cite specific records using "
                "`issues/YYYY-Www.html#item-ID`; consult the Research Passport and coverage matrix before interpreting zeros.\n"]},
        ],
    }
    with open(os.path.join(downloads, "rapport-replication.ipynb"), "w", encoding="utf-8") as f:
        json.dump(notebook, f, ensure_ascii=False, indent=2)
    return {"teaching_rows": min(60, len(sample)), "citation_rows": len(retained)}


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
            "st": it.get("source_type"), "l": it.get("lang"),
            "ca": (it.get("collected_at") or "")[:10],
            "sh": it.get("snapshot_sha256"),
            "lc": (it.get("link_check") or {}).get("status"),
            "ac": a.get("actors") or [], "s": a.get("summary", ""),
            "at": trend_utils.action_type(it),
            "cf": a.get("confidence"),
            "rtl": bool(it.get("rtl")),
            "q": [{"o": q.get("original", ""), "t": q.get("translation", ""),
                   "sp": q.get("speaker", "")}
                  for q in (a.get("quotes") or []) if q.get("original")],
            "cd": it.get("coded"),
            "bt": [{"i": row.get("quote_index"), "f": bool(row.get("flagged")),
                    "sv": row.get("severity"), "n": row.get("note", "")}
                   for row in (it.get("backtranslation") or [])],
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
