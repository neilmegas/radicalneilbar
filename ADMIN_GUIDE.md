# RAPPORT private content editor

The editor changes the YAML files under `content/`. The public HTML under
`site/` remains generated, so a weekly report cannot overwrite editorial copy.

## Run it on your computer

1. Open Terminal in the RAPPORT repository.
2. Create an environment and install the editor:

   ```bash
   python3 -m venv .admin-venv
   source .admin-venv/bin/activate
   pip install -r requirements-admin.txt
   ```

3. Choose a private password and start the editor:

   ```bash
   export RAPPORT_ADMIN_PASSWORD='choose-a-long-unique-password'
   export RAPPORT_ADMIN_SECRET='choose-another-long-random-string'
   python -m admin_app.app
   ```

4. Open <http://127.0.0.1:5050>.

Use **Rebuild preview** before publishing. The local preview opens inside the
same private editor. **Publish to GitHub** commits only `content/`, rebases onto
the current `main` branch, and pushes it. GitHub Pages then rebuilds the site.

The editor is for static, human-written pages. Weekly reports, party data,
representation figures, and collected records continue to come from the
research pipeline and cannot be silently changed in this interface.

## Hosted mode

The same application can be deployed as a private HTTPS web service. Set all
variables from `.env.example`, including a fine-grained GitHub token restricted
to `neilmegas/radicalneilbar` with **Contents: write**. In hosted mode, saving a
form creates a GitHub commit directly. The token remains a server-side secret
and is never included in the public site or browser JavaScript.

Also set `RAPPORT_ADMIN_SECURE_COOKIE=1` on an HTTPS deployment. Do not expose
the editor over plain HTTP, reuse your GitHub password, or place the token in a
tracked file.

GitHub Pages cannot host this private editor because Pages serves static files
only. You can either keep the editor on your own computer—the simplest and
safest option—or deploy `admin_app` as a separate private Python web service
and leave the public RAPPORT site on GitHub Pages.
