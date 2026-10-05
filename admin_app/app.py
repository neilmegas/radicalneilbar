"""Private, single-user editor for RAPPORT's static source content.

Run locally with ``python -m admin_app.app``.  When a server-side GitHub token
is configured, saves become commits on the configured branch and therefore
trigger the existing GitHub Pages build.  No token is ever sent to the browser.
"""

from __future__ import annotations

import base64
import hmac
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml
from flask import (Flask, abort, flash, redirect, render_template, request,
                   send_from_directory, session, url_for)


ROOT = Path(__file__).resolve().parent.parent
CONTENT_ROOT = ROOT / "content"
SITE_ROOT = ROOT / "site"

EDITABLE = {
    "site": {
        "label": "Website and homepage",
        "description": "Branding, homepage copy, institutional statement, contact and citation defaults.",
        "path": "content/site.yaml",
    },
    "navigation": {
        "label": "Navigation",
        "description": "Desktop and mobile menus. URLs are relative to the published website.",
        "path": "content/navigation.yaml",
    },
    "methodology": {
        "label": "Methodology",
        "description": "Explanatory copy surrounding the generated method, roster and revision tables.",
        "path": "content/pages/methodology.yaml",
    },
    "dataset": {
        "label": "Dataset",
        "description": "Dataset introduction, limitations and stable-link guidance.",
        "path": "content/pages/dataset.yaml",
    },
    "citation": {
        "label": "Citation",
        "description": "Citation-page headings and explanatory copy. Report citations remain generated and stable.",
        "path": "content/pages/citation.yaml",
    },
    "tutorials": {
        "label": "Tutorials",
        "description": "Step-by-step guidance for readers, researchers and teachers.",
        "path": "content/pages/tutorials.yaml",
    },
}


def _label(path):
    bits = path.split(".")
    key = bits[-1]
    if key.isdigit() and len(bits) > 1:
        return f"Item {int(key) + 1}"
    return key.replace("_", " ").strip().title()


def flatten(value, prefix=""):
    """Turn YAML leaves into stable form fields while retaining list order."""
    fields = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            fields.extend(flatten(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            fields.extend(flatten(child, path))
    else:
        text = "" if value is None else str(value)
        final_key = prefix.split(".")[-1]
        kind = "url" if final_key in {"url", "public_url", "contact_url", "creator_url"} else "text"
        if len(text) > 90 or final_key in {
            "description", "lede", "text", "system", "purpose", "disclaimer",
            "intro", "limitations", "stable_intro", "report_note", "coverage_text",
            "coverage_caution", "negative_intro", "ai_text", "roster_note",
        }:
            kind = "textarea"
        fields.append({"path": prefix, "label": _label(prefix), "value": text, "kind": kind})
    return fields


def set_path(document, dotted, value):
    parts = dotted.split(".")
    cursor = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    final = parts[-1]
    if isinstance(cursor, list):
        cursor[int(final)] = value
    else:
        cursor[final] = value


class ContentBackend:
    """Local filesystem by default; GitHub Contents API when configured."""

    def __init__(self):
        self.token = os.getenv("RAPPORT_GITHUB_TOKEN", "").strip()
        self.repository = os.getenv("RAPPORT_GITHUB_REPOSITORY", "neilmegas/radicalneilbar")
        self.branch = os.getenv("RAPPORT_GITHUB_BRANCH", "main")
        self.api = f"https://api.github.com/repos/{self.repository}"

    @property
    def remote(self):
        return bool(self.token)

    def _headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def read(self, relative, ref=None):
        if not self.remote:
            if ref:
                result = subprocess.run(
                    ["git", "show", f"{ref}:{relative}"], cwd=ROOT,
                    text=True, capture_output=True, check=True,
                )
                return result.stdout, None
            return (ROOT / relative).read_text(encoding="utf-8"), None
        response = requests.get(
            f"{self.api}/contents/{relative}", headers=self._headers(),
            params={"ref": ref or self.branch}, timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return base64.b64decode(payload["content"]).decode("utf-8"), payload.get("sha")

    def write(self, relative, content, message):
        if not self.remote:
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                             delete=False) as handle:
                handle.write(content)
                temporary = Path(handle.name)
            temporary.replace(target)
            return {"mode": "local", "path": str(target)}
        _current, sha = self.read(relative)
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": self.branch,
            "sha": sha,
        }
        response = requests.put(
            f"{self.api}/contents/{relative}", headers=self._headers(),
            json=payload, timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def history(self, relative):
        if not self.remote:
            result = subprocess.run(
                ["git", "log", "--format=%H%x09%ad%x09%s", "--date=iso-strict", "--", relative],
                cwd=ROOT, text=True, capture_output=True, check=True,
            )
            rows = []
            for line in result.stdout.splitlines():
                sha, date, message = (line.split("\t", 2) + ["", ""])[:3]
                rows.append({"sha": sha, "date": date, "message": message, "url": ""})
            return rows
        response = requests.get(
            f"{self.api}/commits", headers=self._headers(),
            params={"path": relative, "sha": self.branch, "per_page": 30}, timeout=30,
        )
        response.raise_for_status()
        return [
            {
                "sha": row["sha"],
                "date": row["commit"]["committer"]["date"],
                "message": row["commit"]["message"].splitlines()[0],
                "url": row["html_url"],
            }
            for row in response.json()
        ]


backend = ContentBackend()
app = Flask(__name__)
app.secret_key = os.getenv("RAPPORT_ADMIN_SECRET") or secrets.token_urlsafe(48)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("RAPPORT_ADMIN_SECURE_COOKIE", "0") == "1",
    MAX_CONTENT_LENGTH=512 * 1024,
)


def _csrf():
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


app.jinja_env.globals["csrf_token"] = _csrf


def _password_ok(candidate):
    expected = os.getenv("RAPPORT_ADMIN_PASSWORD", "")
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


@app.before_request
def protect():
    if request.endpoint in {"login", "static"}:
        return None
    if not session.get("authenticated"):
        return redirect(url_for("login", next=request.path))
    if request.method == "POST" and not hmac.compare_digest(
            request.form.get("csrf", ""), session.get("csrf", "")):
        abort(400, "Invalid form token")
    return None


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if _password_ok(request.form.get("password", "")):
            session.clear()
            session["authenticated"] = True
            _csrf()
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Incorrect password.", "error")
    missing = not bool(os.getenv("RAPPORT_ADMIN_PASSWORD", ""))
    return render_template("login.html", missing=missing)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def dashboard():
    return render_template(
        "dashboard.html", pages=EDITABLE, remote=backend.remote,
        public_site=os.getenv("RAPPORT_PUBLIC_SITE", "https://neilmegas.github.io/radicalneilbar/"),
    )


def _entry(slug):
    entry = EDITABLE.get(slug)
    if not entry:
        abort(404)
    return entry


@app.route("/edit/<slug>", methods=["GET", "POST"])
def edit(slug):
    entry = _entry(slug)
    try:
        raw, _sha = backend.read(entry["path"])
        document = yaml.safe_load(raw) or {}
    except Exception as exc:
        abort(502, f"Could not load {entry['path']}: {exc}")
    if request.method == "POST":
        for field in flatten(document):
            form_key = "field__" + field["path"]
            if form_key in request.form:
                set_path(document, field["path"], request.form[form_key].strip())
        rendered = yaml.safe_dump(document, allow_unicode=True, sort_keys=False,
                                  width=100, default_flow_style=False)
        try:
            backend.write(
                entry["path"], rendered,
                f"Edit {entry['label']} through RAPPORT Admin",
            )
            flash("Changes published to GitHub." if backend.remote else "Changes saved locally.", "success")
        except Exception as exc:
            flash(f"Save failed: {exc}", "error")
        return redirect(url_for("edit", slug=slug))
    return render_template("edit.html", slug=slug, entry=entry,
                           fields=flatten(document), remote=backend.remote)


@app.get("/history/<slug>")
def history(slug):
    entry = _entry(slug)
    try:
        rows = backend.history(entry["path"])
    except Exception as exc:
        rows = []
        flash(f"Could not load history: {exc}", "error")
    return render_template("history.html", slug=slug, entry=entry, rows=rows)


@app.post("/rollback/<slug>/<sha>")
def rollback(slug, sha):
    entry = _entry(slug)
    if len(sha) < 7 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
        abort(400)
    try:
        old_content, _old_sha = backend.read(entry["path"], ref=sha)
        yaml.safe_load(old_content)
        backend.write(entry["path"], old_content,
                      f"Restore {entry['label']} from {sha[:10]}")
        flash("The selected version was restored.", "success")
    except Exception as exc:
        flash(f"Restore failed: {exc}", "error")
    return redirect(url_for("history", slug=slug))


@app.post("/rebuild")
def rebuild():
    if backend.remote:
        flash("GitHub rebuilds the site automatically after a published edit.", "success")
        return redirect(url_for("dashboard"))
    try:
        result = subprocess.run(
            [sys.executable, "run.py", "site"], cwd=ROOT, text=True,
            capture_output=True, timeout=360, check=True,
        )
        flash("Preview rebuilt successfully.", "success")
        session["last_build"] = datetime.now(timezone.utc).isoformat()
    except subprocess.CalledProcessError as exc:
        flash(f"Build failed: {(exc.stderr or exc.stdout)[-1200:]}", "error")
    except Exception as exc:
        flash(f"Build failed: {exc}", "error")
    return redirect(url_for("preview_file", filename="index.html"))


@app.get("/preview/")
@app.get("/preview/<path:filename>")
def preview_file(filename="index.html"):
    return send_from_directory(SITE_ROOT, filename)


@app.post("/publish-local")
def publish_local():
    if backend.remote:
        abort(400)
    message = request.form.get("message", "Update RAPPORT website content").strip()
    if not message:
        message = "Update RAPPORT website content"
    try:
        subprocess.run(["git", "add", "content"], cwd=ROOT, check=True)
        changed = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=ROOT)
        if changed.returncode == 0:
            flash("There are no unpublished content changes.", "success")
            return redirect(url_for("dashboard"))
        subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True,
                       text=True, capture_output=True)
        # Preview builds legitimately leave generated site files modified. The
        # autostash keeps those files out of this content-only commit while
        # still allowing a safe rebase before the push.
        subprocess.run(
            ["git", "pull", "--rebase", "--autostash", "origin", backend.branch],
            cwd=ROOT, check=True, text=True, capture_output=True,
        )
        subprocess.run(["git", "push", "origin", backend.branch], cwd=ROOT,
                       check=True, text=True, capture_output=True)
        flash("Content committed and pushed. GitHub Pages will rebuild it.", "success")
    except subprocess.CalledProcessError as exc:
        flash(f"Publish failed: {(exc.stderr or exc.stdout or str(exc))[-1200:]}", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    if not os.getenv("RAPPORT_ADMIN_PASSWORD"):
        raise SystemExit("Set RAPPORT_ADMIN_PASSWORD before starting the editor.")
    app.run(host=os.getenv("RAPPORT_ADMIN_HOST", "127.0.0.1"),
            port=int(os.getenv("RAPPORT_ADMIN_PORT", "5050")), debug=False)
