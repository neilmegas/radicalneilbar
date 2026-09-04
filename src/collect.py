"""Network collectors for feeds, websites, Google News, Telegram, and YouTube."""

from __future__ import annotations

import calendar
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser


UA = "RadicalPartyWatch/1.0 (+research monitoring; contact via repository)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en,*;q=0.5"}
TIMEOUT = 25


def window_start(days: int = 7) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _as_datetime(value) -> datetime | None:
    """Parse a source date as UTC without silently replacing a bad value."""
    if not value:
        return None
    try:
        dt = dateparser.parse(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _date(value) -> str:
    dt = _as_datetime(value)
    return (dt or datetime.now(timezone.utc)).isoformat()


def _within(value: str, since: datetime, until: datetime | None = None) -> bool:
    """Whether value is in [since, until).  ``until`` is deliberately exclusive."""
    dt = _as_datetime(value)
    if not dt:
        return False
    return dt >= since and (until is None or dt < until)


def _recent(value: str, since: datetime) -> bool:
    return _within(value, since)


def _clean_html(value: str) -> str:
    soup = BeautifulSoup(value or "", "html.parser")
    for node in soup(["script", "style", "nav", "footer", "form"]):
        node.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _item(party: dict, source_type: str, title: str, url: str, published, body: str,
          outlet: str = "") -> dict:
    return {
        "party_id": party["id"],
        "source_type": source_type,
        "url": url,
        "title": re.sub(r"\s+", " ", title or "").strip()[:500],
        "published": _date(published),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "lang": party.get("lang"),
        "body": (body or "")[:50000],
        "outlet": outlet or urlparse(url or "").netloc,
    }


def discover_feeds(site: str | None) -> dict:
    result = {"reachable": False, "feeds": [], "error": ""}
    if not site:
        result["error"] = "no site configured"
        return result
    try:
        response = requests.get(site, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        result["reachable"] = True
        soup = BeautifulSoup(response.text, "html.parser")
        feeds = []
        for link in soup.select('link[rel="alternate"]'):
            typ = (link.get("type") or "").casefold()
            href = link.get("href")
            if href and ("rss" in typ or "atom" in typ or "xml" in typ):
                feeds.append(urljoin(response.url, href))
        result["feeds"] = list(dict.fromkeys(feeds))
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def from_feed(party: dict, feed_url: str, since: datetime,
              until: datetime | None = None) -> list[dict]:
    response = requests.get(feed_url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(str(getattr(parsed, "bozo_exception", "invalid feed")))
    out = []
    for entry in parsed.entries[:100]:
        published = entry.get("published") or entry.get("updated")
        published_iso = _date(published)
        if published and not _within(published_iso, since, until):
            continue
        body = entry.get("content", [{}])[0].get("value") if entry.get("content") else ""
        body = body or entry.get("summary") or entry.get("description") or ""
        out.append(_item(
            party, "site_feed", entry.get("title") or "Untitled",
            entry.get("link") or feed_url, published_iso, _clean_html(body),
            urlparse(feed_url).netloc,
        ))
    return out


def from_google_news(party: dict, since: datetime, days: int = 7,
                     until: datetime | None = None) -> list[dict]:
    terms = list(dict.fromkeys((party.get("queries") or []) + [party.get("name", "")]))
    out, seen = [], set()
    for term in [t for t in terms if t][:6]:
        if until:
            # Google treats ``after`` and ``before`` as boundaries.  Move the
            # first one back a day so the user's first date is included; our
            # own filter below remains the authority for the exact window.
            after = (since.date() - timedelta(days=1)).isoformat()
            before = until.date().isoformat()
            search = f'"{term}" after:{after} before:{before}'
        else:
            search = f'"{term}" when:{max(1, int(days))}d'
        query = quote_plus(search)
        feed = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
        response = requests.get(feed, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        for entry in parsed.entries[:100]:
            link = entry.get("link") or ""
            key = (entry.get("title") or "").casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            pub = _date(entry.get("published") or entry.get("updated"))
            if not _within(pub, since, until):
                continue
            source = entry.get("source", {})
            outlet = source.get("title") if isinstance(source, dict) else "Google News"
            out.append(_item(
                party, "press", entry.get("title"), link, pub,
                _clean_html(entry.get("summary") or ""), outlet or "Google News",
            ))
    return out[:240 if until else 80]


def _extract_page(url: str) -> tuple[str, str]:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "form", "aside"]):
        node.decompose()
    title = (soup.find("h1") or soup.find("title"))
    return (title.get_text(" ", strip=True) if title else url,
            re.sub(r"\s+", " ", soup.get_text(" ", strip=True)))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _url_date_hint(url: str) -> datetime | None:
    """Conservative date hints used only when a sitemap omits ``lastmod``."""
    match = re.search(r"/(20\d{2})[/-](0[1-9]|1[0-2])[/-]([0-2]\d|3[01])(?:/|[-_.]|$)", url)
    if not match:
        return None
    return _as_datetime("-".join(match.groups()))


def _sitemap_seeds(site: str) -> list[str]:
    base = f"{urlparse(site).scheme or 'https'}://{urlparse(site).netloc}"
    seeds = []
    try:
        response = requests.get(urljoin(base, "/robots.txt"), headers=HEADERS,
                                timeout=TIMEOUT)
        if response.ok:
            for line in response.text.splitlines():
                if line.casefold().startswith("sitemap:"):
                    seeds.append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    seeds += [urljoin(base, path) for path in
              ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")]
    return list(dict.fromkeys(u for u in seeds if u.startswith("http")))


def _page_date(soup: BeautifulSoup) -> datetime | None:
    selectors = [
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="date"]', "content"),
        ('meta[name="pubdate"]', "content"),
        ('time[datetime]', "datetime"),
    ]
    for selector, attr in selectors:
        node = soup.select_one(selector)
        parsed = _as_datetime(node.get(attr) if node else None)
        if parsed:
            return parsed
    return None


def _historical_page(party: dict, url: str, url_date: datetime | None,
                     since: datetime, until: datetime) -> dict | None:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # Sitemap ``lastmod`` is an edit date, not a publication date.  It may
    # select a page for inspection but is never presented as the item date.
    published = _page_date(soup) or url_date
    if not published or not _within(published.isoformat(), since, until):
        return None
    for node in soup(["script", "style", "nav", "footer", "form", "aside"]):
        node.decompose()
    title_node = soup.find("h1") or soup.find("title")
    title = title_node.get_text(" ", strip=True) if title_node else url
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    if len(body) < 80:
        return None
    return _item(party, "party_archive", title, response.url,
                 published.isoformat(), body, urlparse(response.url).netloc)


def from_sitemaps(party: dict, since: datetime, until: datetime,
                  max_pages: int = 120, max_sitemaps: int = 30) -> list[dict]:
    """Collect dated pages retained in a party site's sitemap.

    A sitemap is not guaranteed to be a complete archive.  This collector
    therefore complements, rather than replaces, the dated news search.  It
    only fetches URLs with an explicit ``lastmod`` or a date in the URL and
    then checks page-level publication metadata when present.
    """
    site = party.get("site")
    if not site:
        return []
    queue = _sitemap_seeds(site)
    seen_maps, candidates = set(), []
    while queue and len(seen_maps) < max_sitemaps and len(candidates) < max_pages * 4:
        sitemap = queue.pop(0)
        if sitemap in seen_maps:
            continue
        seen_maps.add(sitemap)
        try:
            response = requests.get(sitemap, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception:
            continue
        kind = _local_name(root.tag)
        for child in root:
            fields = {_local_name(node.tag): (node.text or "").strip() for node in child}
            loc = fields.get("loc")
            if not loc:
                continue
            if kind == "sitemapindex":
                if loc not in seen_maps and len(queue) + len(seen_maps) < max_sitemaps * 2:
                    queue.append(loc)
                continue
            modified = _as_datetime(fields.get("lastmod"))
            url_date = _url_date_hint(loc)
            selector_date = url_date or modified
            if selector_date and _within(selector_date.isoformat(), since, until):
                candidates.append((loc, selector_date, url_date))
    candidates.sort(key=lambda row: row[1])
    out = []
    for url, _, url_date in candidates[:max_pages]:
        try:
            item = _historical_page(party, url, url_date, since, until)
            if item:
                out.append(item)
        except Exception:
            continue
    return out


def from_site_scrape(party: dict, since: datetime) -> list[dict]:
    """Conservative fallback: collect article-looking links from the homepage."""
    site = party.get("site")
    if not site:
        return []
    response = requests.get(site, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    candidates = []
    for article in soup.select("article")[:30]:
        link = article.find("a", href=True)
        if link:
            candidates.append((link.get_text(" ", strip=True), urljoin(response.url, link["href"])))
    if not candidates:
        for link in soup.select("main a[href], .content a[href], #content a[href]")[:80]:
            text = link.get_text(" ", strip=True)
            href = urljoin(response.url, link.get("href"))
            if len(text) >= 20 and urlparse(href).netloc == urlparse(response.url).netloc:
                candidates.append((text, href))
    out, seen = [], set()
    for title, url in candidates[:25]:
        if url in seen:
            continue
        seen.add(url)
        try:
            page_title, body = _extract_page(url)
            out.append(_item(party, "site_scrape", page_title or title, url,
                             datetime.now(timezone.utc), body))
        except Exception:
            continue
    return out


def from_telegram(party: dict, since: datetime,
                  until: datetime | None = None) -> list[dict]:
    channel = str(party.get("telegram") or "").strip().lstrip("@")
    if not channel:
        return []
    url = f"https://t.me/s/{channel}"
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    out = []
    for wrap in soup.select(".tgme_widget_message_wrap")[-80:]:
        time_node = wrap.select_one("time[datetime]")
        published = _date(time_node.get("datetime") if time_node else None)
        if not _within(published, since, until):
            continue
        text_node = wrap.select_one(".tgme_widget_message_text")
        text = text_node.get_text(" ", strip=True) if text_node else ""
        link_node = wrap.select_one("a.tgme_widget_message_date")
        link = link_node.get("href") if link_node else url
        if text:
            out.append(_item(party, "telegram", text[:100], link, published, text, "Telegram"))
    return out


def from_youtube(party: dict, since: datetime, api_key: str | None,
                 until: datetime | None = None) -> list[dict]:
    channel = party.get("youtube_channel")
    if not channel:
        return []
    if not api_key:
        raise RuntimeError("YOUTUBE_API_KEY is not set")
    params = {
        "part": "snippet", "channelId": channel, "order": "date", "type": "video",
        "maxResults": 25, "publishedAfter": since.isoformat().replace("+00:00", "Z"),
        "key": api_key,
    }
    if until:
        params["publishedBefore"] = until.isoformat().replace("+00:00", "Z")
    response = requests.get("https://www.googleapis.com/youtube/v3/search",
                            params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    out = []
    for row in response.json().get("items", []):
        snippet = row.get("snippet") or {}
        video = (row.get("id") or {}).get("videoId")
        if not video:
            continue
        out.append(_item(
            party, "youtube", snippet.get("title") or "Video",
            f"https://www.youtube.com/watch?v={video}", snippet.get("publishedAt"),
            snippet.get("description") or "", "YouTube",
        ))
    return out
