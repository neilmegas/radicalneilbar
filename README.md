# Radical Party Watch

A Python program that collects public political-party material, stores a
longitudinal record in SQLite, and generates a plain static website suitable
for GitHub Pages.

For browser-only setup instructions, read **[GUIDE.md](GUIDE.md)**.

## Quick local test

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py demo
python -m http.server 8000 --directory site
```

Then open <http://localhost:8000>.

The demo uses invented fixture records and placeholder speakers. It does not
make network requests and does not need an API key.

## Repository layout

```text
.github/workflows/   GitHub Pages and scheduled jobs
config/              party roster and research settings
src/                 collection, analysis, storage, and site-generator modules
run.py               command-line entry point
site/                 generated website (created by a run)
data/items.db         longitudinal SQLite database (created by a run)
```

## Main commands

```text
python run.py demo        build the offline sample portal
python run.py discover    test party sites and find advertised feeds
python run.py collect     collect the current window
python run.py analyze     analyse unprocessed items
python run.py weekly      run the full weekly chain
python run.py site        rebuild the static portal from the database
python run.py export      export the current week to CSV
python run.py checklinks  re-check previously collected source pages
```

Run `python run.py --help` for the complete list.

## Configuration

- `config/sources.yaml`: the party roster, official sites, press-search terms,
  optional Telegram/YouTube sources, and watched programme pages.
- `config/countries.yaml`: country names, national-news searches, and dated
  occasions used for absence checks.
- `config/frameworks.yaml`: candidate interpretation frameworks.
- `config/coding.yaml`: starter human-coding categories. Replace these with
  your own instrument before coding.
- `config/reading.yaml`: secondary-reading feeds and search terms.
- `config/backtranslate.yaml`: languages excluded from round-trip checking.
- `config/baselines.yaml`: optional survey context displayed in issues.

The supplied source roster is a starting point. Run `discover` and manually
audit it before trusting coverage. The parliamentary adapter entry point is
present, but no unverified national adapters are enabled by default.

## Secrets and environment variables

| Name | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | optional for demo; recommended for live analysis | extraction, summaries, and interpretation |
| `ANTHROPIC_MODEL` | optional | override the default model alias |
| `YOUTUBE_API_KEY` | optional | YouTube Data API collection |
| `DIP_API_KEY` | reserved/optional | future Bundestag adapter |

Without an Anthropic key, live items receive a plainly marked low-confidence
fallback analysis so the pipeline does not silently discard them.

## Evidence and research safeguards

- Original text and generated analysis are stored separately.
- Quotes are included only when captured verbatim; the program is instructed
  never to reconstruct one.
- Interpretation is visually labelled as model inference and excluded from the
  coding export.
- Provenance is an evidence class, not a truth or confidence score.
- Near-duplicate items are clustered before trend counts.
- Every collection attempt is logged, including failures.
- The issue includes an audit table of retained and rejected material.

These controls support review; they do not replace it. Validate recall, source
coverage, translation quality, and coding agreement on a regular sample.

## Hosting

`.github/workflows/pages.yml` builds `site/` and publishes it with GitHub
Pages. If the repository has no database yet, it publishes the offline sample.
Once a real weekly run commits `data/items.db`, subsequent deployments rebuild
the website from that database.

GitHub Pages is public unless you have a separate enterprise access-control
arrangement. Do not publish material you are not prepared to make public.
