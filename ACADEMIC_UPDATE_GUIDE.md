# Upload the RAPPORT academic-tools update

This update contains fewer than 100 files and can be installed entirely in a
web browser. Do not upload the ZIP itself—unzip it first.

## Easiest method: GitHub's browser editor

1. Unzip `RAPPORT-academic-tools-update.zip` on your computer.
2. Open your `radicalneilbar` repository on GitHub.
3. Press the full-stop key (`.`). GitHub opens the repository in its browser
   editor at `github.dev`.
4. In the left file panel, drag everything **inside** the unzipped folder onto
   the repository's top-level file list. Keep the `config` and `src` folders as
   folders; choose **Replace** if the browser asks about existing files.
5. Click the Source Control icon on the left (the branching-lines symbol).
6. Enter `Add RAPPORT academic research tools` in the message box.
7. Click **Commit & Push** and confirm.

## Ordinary GitHub upload method

You can instead use **Code → Add file → Upload files**, then drag everything
inside the unzipped folder into the upload area and commit the change. There
are fewer than 100 files, so GitHub's browser-upload limit is not a problem.

## Publish and check

The commit should start **0 · Publish website** automatically. Wait for its
green tick under **Actions**, then refresh the public site. Check:

- the homepage says **69 parties**;
- Greece includes **Συμμαχία Ελλήνων**;
- **Explore** contains Compare, Quotations, and Cross-party events;
- **Research** contains Quality and validation, Source registry, Inclusion
  dossiers, Prompt archive, Verified elections, Tutorials, and Corrections;
- a weekly report contains a collapsible **Research Passport** and each full
  evidence record contains **Record provenance and confidence**.

The new Greek party's official website is configured as `https://symmaxia.net/`.
RAPPORT watches its founding declaration, programme, parliamentary-work, and
press-office pages directly, while retaining web/news search as a fallback.
