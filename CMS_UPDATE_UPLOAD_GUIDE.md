# Upload RAPPORT website 1.5 in the GitHub browser

This update keeps GitHub Pages as the public website and adds a private editor
for human-written static pages.

## Upload the update

1. Download and unzip `RAPPORT-1.5-source-update.zip` on your computer.
2. Open the `radicalneilbar` repository on GitHub and select **Code**.
3. Choose **Add file → Upload files**.
4. Drag the unzipped files and folders into the upload area. This bundle has
   fewer than 100 files, so it stays below GitHub's browser-upload limit.
5. Enter `Install RAPPORT 1.5 content editor and responsive layout` as the
   commit message, then choose **Commit changes**.
6. Open **Actions → 0 · Publish website**. Wait for the green check mark, then
   refresh the public site once while holding Shift.

If your computer hides the `.github` folder, upload the visible folders first.
Then open `.github/workflows/pages.yml` in GitHub, select the pencil, replace
its contents with the copy from this bundle, and commit that one file.

## Start the private editor

Follow `ADMIN_GUIDE.md`. The simplest setup runs only on your computer at
`http://127.0.0.1:5050`; the public never sees it and cannot use your Claude
tokens. GitHub Pages continues to serve only static HTML, CSS, JSON, and CSV.

## Verify the release

The homepage should show **Website version 1.5 · 5 Oct 2026**, the title
**A clearer weekly record of radical party activity.**, and a **Menu** button
on phone-sized screens. Every report should show a citation with its own ISO
week report number and `issues/YYYY-Www.html` URL.
