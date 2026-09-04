"""Re-check collected URLs for deletion and quiet revision.

Programme pages are watched deliberately. Ordinary items are not, and that is
a gap: if a party pulls a statement, nothing notices. A deleted statement is a
political act and frequently a more informative one than the statement was —
parties delete when a line has become a liability, which is exactly the moment
worth catching.

The local snapshot already preserves what was said, so a retraction gives you
both halves: the text, and the fact of its removal.

Deliberately conservative. A page that fails once is not gone; sites go down,
rate-limit, and serve interstitials. Only a repeated failure counts, and the
status is advisory rather than a claim.
"""

import re

import requests
from bs4 import BeautifulSoup

from evidence import jaccard, shingles

TIMEOUT = 25
UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}

# Below this, the page has changed enough that a quote taken from it may no
# longer be there. Above it, ordinary churn — ads, related links, counters.
CHANGED_BELOW = 0.55


def _extract(html):
    try:
        import trafilatura
        txt = trafilatura.extract(html, include_comments=False, favor_recall=True)
        if txt and len(txt) > 120:
            return txt
    except Exception:
        pass
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", soup.get_text("\n")).strip()


def check_item(item, snapshot_text):
    """Returns (status, http_code, similarity, detail)."""
    url = item.get("url")
    if not url:
        return "error", None, None, "no url recorded"
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, allow_redirects=True)
    except Exception as ex:
        return "error", None, None, str(ex)[:180]

    if r.status_code in (404, 410):
        return "gone", r.status_code, None, "page returns not found"
    if r.status_code >= 400:
        return "error", r.status_code, None, f"HTTP {r.status_code}"

    if not snapshot_text or len(snapshot_text) < 200:
        return "ok", r.status_code, None, "no usable snapshot to compare"

    now = _extract(r.text)
    sim = jaccard(shingles(snapshot_text[:8000]), shingles(now[:8000]))
    if sim < CHANGED_BELOW:
        return "changed", r.status_code, round(sim, 3), "content materially differs from capture"
    return "ok", r.status_code, round(sim, 3), ""


def quotes_still_present(item, page_text):
    """Whether the quoted sentences survive in the current page. This is the
    check that matters for citation: a page can change a great deal and still
    carry the sentence you quoted, or barely change and have dropped it."""
    a = item.get("analysis") or {}
    out = []
    hay = re.sub(r"\s+", " ", (page_text or "")).lower()
    for q in a.get("quotes") or []:
        needle = re.sub(r"\s+", " ", (q.get("original") or "")).strip().lower()
        if not needle:
            continue
        out.append({"quote": q.get("original"), "present": needle in hay})
    return out


def sweep(conn, store, items, snapshots_read, log=print, pause=1.0):
    """Check a batch. Anything already recorded gone stays gone — a page that
    404s and later returns is usually a site migration, not a reinstatement,
    and the earlier finding is the one worth keeping."""
    import time
    prior = store.latest_link_status(conn)
    results = {"ok": 0, "gone": 0, "changed": 0, "error": 0}
    flagged = []
    for it in items:
        if prior.get(it["id"], {}).get("status") == "gone":
            results["gone"] += 1
            continue
        snap = snapshots_read(it.get("snapshot_path"))
        status, http, sim, detail = check_item(it, snap)
        store.set_link_check(conn, it["id"], status, http, sim, detail)
        results[status] = results.get(status, 0) + 1
        if status in ("gone", "changed"):
            flagged.append({
                "id": it["id"], "party": it.get("party_name"),
                "country": it.get("country"), "date": (it.get("published") or "")[:10],
                "url": it.get("url"), "archive_url": it.get("archive_url"),
                "status": status, "similarity": sim,
                "summary": (it.get("analysis") or {}).get("summary", ""),
                "snapshot_path": it.get("snapshot_path"),
            })
            log(f"  {status.upper():<8} {it.get('party_name','?'):<14} {it.get('url','')[:70]}")
        time.sleep(pause)
    return results, flagged
