"""Best-effort Internet Archive submission."""

from __future__ import annotations

import time

import requests

from collect import HEADERS


def archive_one(url: str) -> str | None:
    if not url:
        return None
    try:
        response = requests.get(
            "https://web.archive.org/save/" + url,
            headers=HEADERS,
            timeout=90,
            allow_redirects=False,
        )
        location = response.headers.get("content-location") or response.headers.get("location")
        if location:
            return location if location.startswith("http") else "https://web.archive.org" + location
        if response.ok:
            return "https://web.archive.org/web/" + url
    except Exception:
        return None
    return None


def archive_all(urls: list[str], pause: float = 1.0) -> dict[str, str | None]:
    results = {}
    for index, url in enumerate(dict.fromkeys(urls)):
        results[url] = archive_one(url)
        if index + 1 < len(urls):
            time.sleep(pause)
    return results
