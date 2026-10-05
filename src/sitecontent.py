"""Load editor-managed RAPPORT website copy.

Generated research data stays in Python/SQLite.  Human-editable headings,
descriptions, navigation labels, and explanatory prose live under ``content``
so a website rebuild cannot silently overwrite editorial changes.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"


DEFAULT_SITE = {
    "name": "RAPPORT",
    "expansion": "Radicalism and Party Politics: Observation, Reporting and Tracking",
    "description": (
        "A weekly record of what monitored European and Israeli far-left and "
        "far-right parties did and said."
    ),
    "public_url": "https://neilmegas.github.io/radicalneilbar/",
    "homepage": {
        "kicker": "Automated academic research infrastructure",
        "title": "A clearer weekly record of radical party activity.",
        "lede": (
            "A weekly record of what monitored European and Israeli far-left "
            "and far-right parties did and said."
        ),
        "map_title": "Where RAPPORT looks",
        "map_intro": "Select a monitored country to see the parties tracked there.",
        "latest_kicker": "Latest report",
        "latest_title": "The week, distilled.",
        "latest_intro": "Read the report, inspect every record, or export the issue.",
        "research_title": "The research spine",
        "research_intro": "Transparent methods, reusable records and stable references.",
    },
    "research_notice": {
        "system": "RAPPORT is an automated, AI-assisted research system powered by the Claude API.",
        "creator": "Neil Bar",
        "institution": "the School of Political Science at the University of Haifa",
        "mentor": "Ayelet Banai",
        "purpose": (
            "It is intended solely for academic research on contemporary "
            "far-right and far-left parties."
        ),
        "contact_intro": "For project information and enquiries, visit",
        "contact_label": "www.neilbar.com",
        "contact_url": "https://www.neilbar.com/",
        "disclaimer": (
            "AI-generated material may contain errors; verify analytical claims "
            "against the cited primary sources."
        ),
    },
    "footer": {
        "description": "Automated academic research monitoring powered by the Claude API.",
        "disclaimer": "AI-generated material may contain errors; consult the cited primary sources.",
        "creator_label": "Neil Bar",
        "creator_url": "https://www.neilbar.com/",
    },
    "citation": {
        "author": "Bar, N.",
        "report_title": "Neil’s Parties Report",
        "publisher": "RAPPORT",
    },
}


DEFAULT_NAVIGATION = {
    "menus": [
        {
            "label": "Reports",
            "items": [
                {"label": "Latest weekly report", "url": "index.html#latest"},
                {"label": "Report archive", "url": "archive.html"},
                {"label": "Build custom report", "url": "report.html"},
            ],
        },
        {
            "label": "Explore",
            "items": [
                {"label": "Countries and parties", "url": "parties.html"},
                {"label": "Compare parties and periods", "url": "compare.html"},
                {"label": "Quotation explorer", "url": "quotes.html"},
                {"label": "Cross-party events", "url": "events.html"},
                {"label": "Speakers", "url": "speakers.html"},
                {"label": "Party network", "url": "network.html"},
            ],
        },
        {
            "label": "Research",
            "columns": [
                {
                    "label": "Method and audit",
                    "items": [
                        {"label": "Methodology", "url": "methodology.html"},
                        {"label": "Quality and validation", "url": "quality.html"},
                        {"label": "Source registry", "url": "sources.html"},
                        {"label": "Party-inclusion dossiers", "url": "inclusion.html"},
                        {"label": "Prompt archive", "url": "prompts.html"},
                        {"label": "Collection status", "url": "health.html"},
                    ],
                },
                {
                    "label": "Data and reuse",
                    "items": [
                        {"label": "Verified election series", "url": "elections.html"},
                        {"label": "Dataset and exports", "url": "dataset.html"},
                        {"label": "Usage tutorials", "url": "tutorials.html"},
                        {"label": "Suggested citation", "url": "citation.html"},
                    ],
                },
            ],
        },
    ],
    "links": [{"label": "Search", "url": "search.html"}],
}


def _merge(default, incoming):
    """Recursively merge mappings while keeping safe defaults for old repos."""
    if not isinstance(default, dict) or not isinstance(incoming, dict):
        return deepcopy(incoming)
    result = deepcopy(default)
    for key, value in incoming.items():
        result[key] = _merge(result[key], value) if key in result else deepcopy(value)
    return result


def load_yaml(relative_path: str, default=None):
    path = CONTENT_DIR / relative_path
    if not path.exists():
        return deepcopy(default) if default is not None else {}
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle) or {}
    if default is None:
        return value
    return _merge(default, value)


def site_content():
    return load_yaml("site.yaml", DEFAULT_SITE)


def navigation_content():
    return load_yaml("navigation.yaml", DEFAULT_NAVIGATION)


def page_content(name: str, default=None):
    return load_yaml(f"pages/{name}.yaml", default or {})

