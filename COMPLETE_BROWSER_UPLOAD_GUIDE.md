# Complete RAPPORT browser repair

The four numbered folders in this package are upload groups, not folders that
belong in the repository. Upload the **contents** of each group into the GitHub
location shown below.

Each commit may start a publishing run. Red runs between the four uploads are
expected because the repository is temporarily incomplete. Judge only the run
started after the fourth and final upload.

## 1. Root files

1. Open the repository's **Code** page.
2. Stay at the top level, where `run.py` is visible.
3. Select **Add file → Upload files**.
4. Upload every file inside `1-root-files`.
5. Commit the changes.

## 2. Configuration

1. On the repository's **Code** page, open the existing `config` folder.
2. Select **Add file → Upload files**.
3. Upload every file inside `2-config-files`.
4. Commit the changes.

This is the group that changes the roster from 65 to 69 parties.

## 3. Program files

1. Return to **Code** and open the existing `src` folder.
2. Select **Add file → Upload files**.
3. Upload every file inside `3-src-files`.
4. Commit the changes.

This group builds the new homepage, map, reports, research pages, party pages,
exports, and browser tools.

## 4. GitHub workflows

1. Return to **Code** and open `.github`, then `workflows`.
2. Select **Add file → Upload files**.
3. Upload every file inside `4-workflow-files`.
4. Commit the changes.

The publishing workflow now checks that all 69 parties and the matching report
generator are present before building. It will give a clear "Incomplete config
upload" or "Incomplete src upload" message if versions are mixed again.

## Final check

Wait for **0 · Publish website** to turn green. Then refresh the public homepage
with `Ctrl+F5`. It must display:

- **20 countries tracked**;
- **69 parties tracked**;
- the RAPPORT title and new navigation;
- a working Europe-and-Israel monitoring map;
- Greece with `Συμμαχία Ελλήνων`;
- Italy with Forza Nuova, Potere al Popolo, and Rifondazione Comunista.

Under **Research**, confirm that Methodology, Quality and validation, Source
registry, Inclusion dossiers, Prompt archive, Verified elections, Dataset and
exports, Tutorials, Citation, Collection status, and Corrections are present.
