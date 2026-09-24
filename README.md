# RAPPORT

**Radicalism and Party Politics: Observation, Reporting and Tracking**

A Python program that collects public political-party material, stores a
longitudinal record in SQLite, and generates a plain static website suitable
for GitHub Pages.

The generated site includes an interactive monitoring map, concise weekly
summaries, evidence-linked changes from the preceding week, action-type labels,
collection coverage, follow-up watchpoints, party timelines, archive search,
interactive party/country and longitudinal comparison, four-week report timelines,
representation panels, a quotation explorer, event context, provenance cards,
validation and language-quality dashboards, dataset and citation-manager exports,
a replication notebook, a teaching sample, stable citations, and original-language controls. The map
counts and party lists come directly from the source roster, while the
methodology and revision log are generated from the archive metadata.

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
- `config/revisions.yaml`: the public methodology revision log.
- `config/research.yaml`: unit of analysis, inclusion/exclusion and negative-
  evidence rules, confidence dimensions, event contexts, and documented roster notes.
- `config/prompts.yaml`: public, versioned archive of the current AI instructions.
- `config/representation.yaml`: official institutional links and verified seat
  and election-history records. Unverified figures are deliberately left blank.
- `config/map_geometry.json`: bundled Natural Earth country outlines used by
  the no-dependency front-page map.

The supplied source roster is a starting point. Every weekly run tries each
party's direct channels, then searches the official domain when a website
blocks crawling, and finally uses ordinary web and news search as fallbacks.
Run `discover` and audit Collection status before trusting coverage. No automated
collector can guarantee access to private, logged-in, or non-indexed material.
The public site consistently uses only the two requested roster labels,
`far-left` and `far-right`. They are operational monitoring buckets, not a
claim of academic consensus or party self-identification.

## Secrets and environment variables

| Name | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | optional for demo; recommended for live analysis | extraction, summaries, and interpretation |
| `ANTHROPIC_MODEL` | optional | override the default model alias |
| `YOUTUBE_API_KEY` | optional | YouTube Data API collection |
| `DIP_API_KEY` | reserved/optional | future Bundestag adapter |

Without an Anthropic key, live items receive a plainly marked low-confidence
fallback analysis so the pipeline does not silently discard them.

### Public access and API-cost safety

Publishing `site/` through GitHub Pages does **not** expose or spend the
Anthropic key. The report builder, search, comparisons, quotation explorer,
map, charts, and downloads are static browser tools: they read only the JSON,
HTML, and CSV files already published with the site. A restrictive Content
Security Policy also limits browser data connections to the RAPPORT site
itself, so public pages cannot call the Anthropic API.

Claude is called only by the private Python pipeline in GitHub Actions. Public
visitors cannot run those workflows and cannot read repository secrets.
Preserve that boundary by keeping the repository private, limiting write or
Actions access to trusted collaborators, requiring two-factor authentication,
never putting an API key in `site/` or JavaScript, and never adding a public
server endpoint that forwards arbitrary visitor prompts to Claude. Set an
Anthropic workspace spending limit and usage alert as a final cost backstop.

## Evidence and research safeguards

- Original text and generated analysis are stored separately.
- Every full record carries a provenance card with retrieval, snapshot, source,
  link-check, prompt/model, translation, confidence, and human-review fields.
- Quotes are included only when captured verbatim; the program is instructed
  never to reconstruct one.
- Interpretation is visually labelled as model inference and excluded from the
  coding export.
- Provenance is an evidence class, not a truth or confidence score.
- Near-duplicate items are clustered before trend counts.
- Every collection attempt is logged, including failures.
- The issue includes an audit table of retained and rejected material.
- Coverage language distinguishes a checked quiet source from an inaccessible
  source or a week with no archived collection log.
- Action labels describe what form an act took, not an ideological topic.
- Every report includes a Research Passport; the Quality page publishes the
  collection funnel, missing-data warnings, coverage matrix, language audit,
  and the current (possibly incomplete) validation state.

These controls support review; they do not replace it. Validate recall, source
coverage, translation quality, and coding agreement on a regular sample.

## Hosting

`.github/workflows/pages.yml` builds `site/` and publishes it with GitHub
Pages. If the repository has no database yet, it publishes the offline sample.
Once a real weekly run commits `data/items.db`, subsequent deployments rebuild
the website from that database.

GitHub Pages is public unless you have a separate enterprise access-control
arrangement. Do not publish material you are not prepared to make public.
The public report builder cannot call Claude or read repository secrets: it
only filters already-published JSON in the visitor's browser.
