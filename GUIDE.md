# Get your website online — beginner guide

You do **not** need to install Python, use Terminal, or understand the code.
Everything below happens in your web browser.

## What you are about to do

1. Upload this complete folder to GitHub.
2. Tell GitHub to use **GitHub Actions** for Pages.
3. Run the included publisher.
4. Open your public URL.

The first publication is a clearly labelled sample website. That proves the
hosting works before you add API keys or collect live material.

---

## Step 1 — unzip the download

Double-click the downloaded update ZIP on your computer.

Open the new project folder. You should see at least:

```text
.github
config
src
GUIDE.md
README.md
requirements.txt
run.py
```

If `.github` is invisible on a Mac, press **Command + Shift + .** to show
hidden files. The dot at the beginning is intentional.

Do not upload the ZIP itself. GitHub will store a ZIP but will not unpack it.

---

## Step 2 — make your GitHub repository public

GitHub Pages is simplest and free when the repository is public.

1. Open your repository on GitHub.
2. Click **Settings**.
3. Click **General** in the left sidebar.
4. Scroll to **Danger Zone**.
5. Next to **Change repository visibility**, click **Change visibility**.
6. Choose **Public** and confirm.

“Public repository” means everyone can see both the website and its files.
Never put an API key in a file or paste one into normal GitHub code.

---

## Step 3 — upload the complete project

You can use the repository you already created. The old loose Python files at
its top level will not stop this project from working.

1. Go to the repository's main **Code** page.
2. Click **Add file → Upload files**.
3. On your computer, open the unzipped RAPPORT update folder.
4. Select **everything inside it**, including `.github`, `config`, and `src`.
5. Drag the selection into GitHub's upload box.
6. Wait until every file is listed.
7. Under **Commit changes**, enter `Install complete website`.
8. Click **Commit changes**.

Important: upload the *contents* of the folder, not the enclosing folder. On
GitHub you should see `run.py`, `config`, and `src` immediately at the top level.

### Check the hidden workflow folder

On GitHub, open `.github`, then `workflows`. You should see:

- `pages.yml`
- `weekly.yml`
- `backfill.yml`

If `.github` did not upload, repeat the upload just for that folder after
showing hidden files on your computer.

---

## Step 4 — switch on GitHub Pages

1. In the repository, click **Settings**.
2. In the left sidebar, click **Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.

That is the only Pages setting you need.

---

## Step 5 — publish the first website

1. Click the repository's **Actions** tab.
2. If GitHub asks whether to enable workflows, click the green enable button.
3. In the left sidebar, click **0 · Publish website**.
4. Click **Run workflow** on the right.
5. Click the green **Run workflow** button.
6. Wait a few minutes and refresh the page.

A green tick means it worked. Click that run, then click the website address
shown under **deploy**.

Your address will normally be:

```text
https://YOUR-GITHUB-NAME.github.io/YOUR-REPOSITORY-NAME/
```

For example, for the repository shown in this project, the likely URL is:

```text
https://neilmegas.github.io/radicalneilbar/
```

You can always find the exact link again under **Settings → Pages**.

Use the top menu after publication:

- **Reports** opens the latest report, archive, and custom report builder.
- **Explore** opens countries and parties, comparisons, quotations, cross-party
  events, speakers, and the party network.
- **Research** opens Methodology, Quality and validation, the source registry,
  inclusion dossiers, prompt archive, verified elections, datasets, tutorials,
  citations, collection status, and the correction form.
- **Search** searches titles, summaries, actors, quotations, parties, and
  action labels across the archive.

The custom report builder is safe to leave public. It only filters the
already-published dataset in the visitor's browser; it cannot call Claude,
read the GitHub secret, or spend API tokens.

If the action has a red cross, click it, open the failed step, and read the
last red message. The most common cause is that **Settings → Pages → Source**
was not changed to **GitHub Actions**.

---

## Step 6 — check the project configuration

The starter list contains 69 parties. Websites and leader names change, so do
not assume every address is correct.

1. Go to **Actions**.
2. Click **1 · Check configuration**.
3. Click **Run workflow**.
4. Wait for the green tick.
5. Open the run and download the `configuration-check` file at the bottom.

That report shows which party sites responded. Correct mistakes in
`config/sources.yaml` by clicking the pencil icon on GitHub.

The sample website is safe demonstration data. It is not a real research
finding and all sample quotes use placeholder speakers.

---

## Step 7 — optional: add AI analysis for live runs

The website and sample do not need an API key. Live weekly analysis works best
with an Anthropic API key, which is billed separately from a Claude subscription.

1. Create a key in the Anthropic Console.
2. On GitHub open **Settings → Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Name it exactly `ANTHROPIC_API_KEY`.
5. Paste the key and click **Add secret**.

Do not paste the key into `README.md`, a Python file, or a GitHub issue.

Then allow the scheduled job to save its database:

1. Open **Settings → Actions → General**.
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

You may now run **2 · Weekly issue** from the Actions tab. It collects current
material, analyses it, saves the database, rebuilds the website, and triggers
a fresh Pages publication. Review the sources and the “Everything reviewed”
table before treating the result as research data.

---

## What runs automatically

| Workflow | When | Purpose |
|---|---|---|
| Publish website | after repository changes | rebuilds and publishes the URL |
| Weekly issue | Monday at 05:00 UTC | collects and builds a full issue |
| Historical collection | only when you manually run it | adds a date range in manageable chunks |

To stop any schedule: open **Actions**, choose the workflow, click the `…`
menu, and choose **Disable workflow**.

## Two important warnings

- A public repository and GitHub Pages site are visible to everyone. The
  generated corpus can also be downloaded by anyone.
- This is a functioning starter system, not a validated research instrument.
  Verify source coverage, translations, model output, and coding categories.
