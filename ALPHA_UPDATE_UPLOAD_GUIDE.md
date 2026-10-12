# Upload the RAPPORT 0.06-alpha update

This update contains 13 source and configuration files. GitHub will rebuild
the public `site/` automatically after the commit, so you do not need to upload
the hundreds of generated HTML pages.

## Upload the ordinary files

On the repository's **Code** tab, choose **Add file → Upload files**. Upload
these files while preserving their folders:

- `run.py`
- `GUIDE.md`
- `config/reading.yaml`
- `config/research.yaml`
- `config/revisions.yaml`
- `content/site.yaml`
- `src/collect.py`
- `src/digest.py`
- `src/portal.py`
- `src/sitecontent.py`
- `src/trends.py`

Commit them directly to `main` with the message:

`Install RAPPORT 0.06-alpha reliability update`

## Replace the two workflow files

GitHub's browser uploader may hide `.github`. Open each existing file inside
the repository and use its pencil icon to replace the contents with the copy
from this package:

- `.github/workflows/weekly.yml`
- `.github/workflows/pages.yml`

Commit those edits to `main`. The **0 · Publish website** workflow should then
start automatically.

## Check the result

1. Open **Actions → 0 · Publish website** and wait for a green check.
2. Open the public homepage in a private/incognito window. It should show
   **Website version 0.06-alpha · 11 Oct 2026**.
3. On the map, hovering over France should leave the selected country alone;
   clicking France should update the party panel.
4. On **Explore → Parties**, test a country filter and then press **Reset**.
5. Open **Actions → 2 · Weekly issue**. The schedule should say Monday at
   08:00 in `Asia/Jerusalem`. You can use **Run workflow** once to test it now;
   a successful run prints a `90/90` coverage-gate message before building the
   report.

