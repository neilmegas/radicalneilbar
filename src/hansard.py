"""Parliamentary adapter entry point.

The starter configuration deliberately contains no unverified parliament API
adapters. A party may opt into the generic RSS adapter with:

parliament: {adapter: rss, url: "https://...", query: "optional text"}
"""

from __future__ import annotations

from collect import from_feed


def collect(party: dict, since):
    spec = party.get("parliament") or {}
    if not spec:
        return [], None
    adapter = spec.get("adapter")
    if adapter == "rss" and spec.get("url"):
        proxy = dict(party)
        try:
            items = from_feed(proxy, spec["url"], since)
            query = (spec.get("query") or "").casefold()
            if query:
                items = [i for i in items if query in
                         f"{i.get('title','')} {i.get('body','')}".casefold()]
            for item in items:
                item["source_type"] = "parliament"
            return items, None
        except Exception as exc:
            return [], f"{type(exc).__name__}: {exc}"
    return [], f"unsupported parliament adapter: {adapter or '(missing)'}"
