# Upload this update to GitHub

This update already contains the rebuilt information for the two latest
reports. You do not need to run Python on your computer.

## 1. Unzip the download

Double-click the downloaded Neil's Parties Report update ZIP.

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
7. In the commit box, type `Update Neil's Parties Report`.
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

## What changed

- The name is now **Neil's Parties Report**.
- Direct party documents and records are the full, central entries.
- Other reporting is shown as a linked title, publication/date, and short
  description.
- Highlights, This week in the world, and Worth reading sit side by side and
  contain at least two entries when verified sources are available.
- Countries, parties, and Everything reviewed are collapsible.
- The former topic tags/filters and survey-baseline blocks are gone.
- דע״ם / Da'am is included as the 27th monitored party.
- A blocked official site now triggers official-domain web search and then a
  wider web/news-search fallback. Source health still records failed attempts;
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
- The new **Method** page explains the evidence hierarchy, limitations, prompt
  versions, and every report-design revision.
