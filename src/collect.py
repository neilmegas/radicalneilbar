"""Network collectors for feeds, websites, Google News, Telegram, and YouTube."""

from __future__ import annotations

import calendar
import re
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


def _date(value) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = dateparser.parse(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _recent(value: str, since: datetime) -> bool:
    try:
        dt = dateparser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= since
    except Exception:
        return True


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


def from_feed(party: dict, feed_url: str, since: datetime) -> list[dict]:
    response = requests.get(feed_url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(str(getattr(parsed, "bozo_exception", "invalid feed")))
    out = []
    for entry in parsed.entries[:100]:
        published = entry.get("published") or entry.get("updated")
        published_iso = _date(published)
        if published and not _recent(published_iso, since):
            continue
        body = entry.get("content", [{}])[0].get("value") if entry.get("content") else ""
        body = body or entry.get("summary") or entry.get("description") or ""
        out.append(_item(
            party, "site_feed", entry.get("title") or "Untitled",
            entry.get("link") or feed_url, published_iso, _clean_html(body),
            urlparse(feed_url).netloc,
        ))
    return out


def from_google_news(party: dict, since: datetime, days: int = 7) -> list[dict]:
    terms = list(dict.fromkeys((party.get("queries") or []) + [party.get("name", "")]))
    out, seen = [], set()
    for term in [t for t in terms if t][:6]:
        query = quote_plus(f'"{term}" when:{max(1, int(days))}d')
        feed = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
        response = requests.get(feed, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        for entry in parsed.entries[:25]:
            link = entry.get("link") or ""
            key = (entry.get("title") or "").casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            pub = _date(entry.get("published") or entry.get("updated"))
            if not _recent(pub, since):
                continue
            source = entry.get("source", {})
            outlet = source.get("title") if isinstance(source, dict) else "Google News"
            out.append(_item(
                party, "press", entry.get("title"), link, pub,
                _clean_html(entry.get("summary") or ""), outlet or "Google News",
            ))
    return out[:80]


def _extract_page(url: str) -> tuple[str, str]:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "form", "aside"]):
        node.decompose()
    title = (soup.find("h1") or soup.find("title"))
    return (title.get_text(" ", strip=True) if title else url,
            re.sub(r"\s+", " ", soup.get_text(" ", strip=True)))


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


def from_telegram(party: dict, since: datetime) -> list[dict]:
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
        if not _recent(published, since):
            continue
        text_node = wrap.select_one(".tgme_widget_message_text")
        text = text_node.get_text(" ", strip=True) if text_node else ""
        link_node = wrap.select_one("a.tgme_widget_message_date")
        link = link_node.get("href") if link_node else url
        if text:
            out.append(_item(party, "telegram", text[:100], link, published, text, "Telegram"))
    return out


def from_youtube(party: dict, since: datetime, api_key: str | None) -> list[dict]:
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
