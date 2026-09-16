# Upload this update to GitHub

This update already contains the rebuilt information for the two latest
reports. You do not need to run Python on your computer.

## 1. Unzip the download

Double-click the downloaded RAPPORT update ZIP.

Do **not** upload the ZIP itself: GitHub stores ZIP files but does not unpack
them.

## 2. Upload the replacement files

1. Open `neilmegas/radicalneilbar` on GitHub.
2. Open the **Code** tab.
3. Click **Add file → Upload files**.
4. Open the unzipped update folder on your computer.
5. Drag **everything inside the folder** into GitHub's upload box. Upload the
   contents, not the enclosing update folder.
6. Wait until GitHub lists the files.
7. In the commit box, type `Update RAPPORT`.
8. Click **Commit changes**.

The important folders are `src`, `config`, and `data`, plus `run.py`. The
`.github` folder contains two small reliability fixes for scheduled jobs. On a
Mac, press **Command + Shift + .** if that folder is hidden. The report redesign
will still work if the existing `.github` folder is not replaced.

## 3. Publish

Committing the files should automatically start **0 · Publish website** under
the **Actions** tab. Wait for its green tick.

If it does not start:

1. Open **Actions**.
2. Select **0 · Publish website** on the left.
3. Click **Run workflow**, then the green **Run workflow** button.

When the run is green, refresh your existing public website. Open weeks
`2026-W38` and `2026-W37` to see the revised reports.

The new party pages appear immediately after publishing. They correctly show
zero archived items at first. The next **2 · Weekly issue** run will start
collecting them automatically; old material is only added if you run
**5 · Historical collection** for the dates you want.

## What changed

- The front page now opens with live totals for **20 countries** and **65
  parties**, followed by an interactive map focused on Europe and Israel.
- Point to, tab to, or select a highlighted country to see every party tracked
  there. A collapsible text directory provides the same information without
  relying on the map.
- The introduction now identifies the Claude-powered automated system, states
  its academic-research purpose, credits **Dr. Neil Bar**, and links to
  **www.neilbar.com**.
- The name is now **RAPPORT** (Radicalism and Party Politics: Observation,
  Reporting and Tracking).
- Direct party documents and records are the full, central entries.
- Other reporting is shown as a linked title, publication/date, and short
  description.
- Highlights, This week in the world, and Worth reading sit side by side and
  contain at least two entries when verified sources are available.
- Countries, parties, and Everything reviewed are collapsible.
- The former topic tags/filters and survey-baseline blocks are gone.
- The watch list now contains **65 parties**. Requested and suggested parties were
  added; Greek Solution and Podemos were already present and were not duplicated.
- Every party is displayed using only **far-left** or **far-right**. These are
  the report's two monitoring buckets, not a claim that every external source
  classifies every party identically.
- A blocked official site now triggers official-domain web search and then a
  wider web/news-search fallback. Collection status still records failed attempts;
  a private or non-indexed page cannot be recovered automatically.
- Each issue now opens with **The week in one minute**, then shows what changed
  since the previous archived week, collection coverage, and evidence-linked
  points to watch next week.
- Every retained item has an observable action label, such as Parliamentary
  intervention, Legal action, or Mobilisation or protest.
- Party pages are now searchable week-by-week timelines.
- The new **Search** page searches the complete report archive, while the
  report builder can compare any two archived weeks.
- Original quotations can be shown with English, in English only, or in their
  original language only.
- The new **Research** menu contains Methodology, Dataset and exports,
  Suggested citation, and Collection status.
- Party pages include official and institutional links plus source-gated
  representation and election-comparison panels. Empty panels mean the figure
  still needs verification; RAPPORT does not invent or carry stale seat totals.
- Every weekly report now has representation changes, a four-week timeline,
  compact citation, stable-link copy, CSV, and print/PDF controls.
- The public custom-report builder only filters the published archive in the
  visitor's browser. It cannot call Claude or spend your API tokens.
