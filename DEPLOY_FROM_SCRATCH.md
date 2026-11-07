# Deploy from scratch (about 30 minutes, no coding)

Use this when starting a new Railway project, or when everything should be rebuilt cleanly. Follow the steps in order. The *Troubleshooting* table at the end lists every problem met on the first deployment and its fix.

**Rules for whoever (or whichever AI) helps with this:** change only Railway, GitHub and Google settings, never the code. If a deploy fails, copy the last 20 lines of *Deploy Logs* and take them to the person who owns the code. Never paste passwords or tokens into any chat: type them into the fields yourself.

## 0. Before you start
* A GitHub account and a Railway account, both signed in.
* A Gmail account that will send the sign-in emails (and receive the ERP reports).
* A password manager, or PowerShell, to make two long random secrets (see step 5).
* Railway's free trial credit is small: plan to switch to the Hobby plan (about $5 a month plus usage) on day one.

## 1. GitHub
1. New repository, **Private**, name for example `NG-Dashboard`. Leave *Add README*, *.gitignore* and *licence* switched **off**.
2. Put every file of this folder in it, with `Dockerfile` and `README.md` at the top level. Browsers often cannot upload folders: use **GitHub Desktop** (File > Clone repository, copy everything into the cloned folder with Ctrl+A / Ctrl+V, Commit to main, Push origin).
3. Check on github.com that you see the folders `app`, `frontend`, `gmail`, `scripts` and the files `Dockerfile`, `railway.json`, `requirements.txt`, `.env.example`.

## 2. Railway project
1. railway.com/new > **Deploy from GitHub repo** > the repository (allow access to that one repository only).
2. In the same project: **+ Create > Database > Add PostgreSQL**.
3. **Volume:** + Create > Volume, attach to the app service, mount path `/data`.
4. The first build may fail until the variables exist. That is normal.

## 3. Variables (app service > Variables)
Add them **one at a time** with *New Variable*. Do not use *Import* from `.env.example`: it can shift values by one row.

| Name | Value | Required |
|---|---|---|
| `DATABASE_URL` | type `${{` and pick Postgres > DATABASE_URL | yes |
| `SECRET_KEY` | a long random text (40+ characters) | yes |
| `INGEST_SECRET` | another long random text; the Gmail script needs the same value | yes |
| `ADMIN_EMAIL` | your email address | yes |
| `ADMIN_PASSWORD` | a first password, 10+ characters, letters and a number | recommended until email works |
| `PRODUCT_NAME` | Performance Dashboard | optional |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `MAIL_FROM` | smtp.gmail.com / 587 / the Gmail address / the Gmail address | for emailed sign-in links |
| `SMTP_PASSWORD` | the 16-character Google App Password | for emailed sign-in links |

Not needed any more: `BASE_URL` (the app uses the address people open), `UPLOAD_DIR` (defaults to `/data/uploads`), `RAILWAY_RUN_UID` (the container fixes the volume's permissions itself).

Two secrets in PowerShell: `$b = New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); [Convert]::ToBase64String($b)` (run it twice). Keep `INGEST_SECRET` somewhere safe.

## 4. Web address
Service > Settings > Networking > **Generate Domain**. If it asks for a port, use the port the app reports in *Deploy Logs* (a line like `Uvicorn running on http://0.0.0.0:8080`). Railway chooses it and gives it to the app as `PORT`, so it is usually **8080**, not 8000. Open `https://<address>/healthz`: it should show `{"ok":true}`. Then open the address itself: the sign-in page appears.

## 5. First sign-in and the first data
1. Sign in with `ADMIN_EMAIL` and `ADMIN_PASSWORD` (tab *User ID and password*).
2. Open **Administration** (link at the top; or add `/admin` to the address). The **Setup checklist** on the first page tells you what is still to do and how.
3. **Upload a report:** select the 8 shipment registers and the 2 job profit reports, *Check the files*, *Load*. About a minute.
4. **Previous reports:** earlier years, many files at once, loaded oldest first.
5. **Organization master:** one file per company.
6. **Users:** add people with a role, companies, LOBs and the money permission.
7. Open the dashboard. The first person may wait a few seconds; later loads are instant.

## 6. Email: sign-in links and the Gmail script
1. Google Account > Security > 2-Step Verification on > **App passwords** > create one called "dashboard". Put it into `SMTP_PASSWORD`. Sign-in links now work.
2. In Gmail make the label `ERP-Reports` and a filter for the ERP's report emails (for example `subject:("Shipment Register" OR "Job Profit") has:attachment filename:xlsx`) that applies the label.
3. In Google Apps Script paste `gmail/ERP_Mail_Collector.gs`. Script properties: `ALLOWED_SENDERS` (the ERP's address, or `*` to start), `ALERT_EMAIL`, `APP_URL` = `https://<address>/api/ingest`, `INGEST_SECRET` (same as in Railway). Run `testSetup`, then `installTrigger`.

## 7. Go-live checklist
* Railway plan upgraded and a usage alert set (about $20); a second person invited to the Railway project and to GitHub.
* `ADMIN_PASSWORD` variable deleted once email sign-in works.
* The Setup checklist in the admin portal shows every item as done.
* A phone check: open the dashboard on a phone and look at the filters, tabs and a table.

## 8. Updating the app later
Change files in the GitHub repository (copy new files into the cloned folder, Commit, Push). Railway rebuilds and redeploys by itself. The data stays in PostgreSQL and the volume.

## Troubleshooting (each of these happened on the first deployment)
| What you see | Cause | Fix |
|---|---|---|
| Deploy log ends with `ValueError: Use at least 10 characters` | `ADMIN_PASSWORD` too short | Fixed in the code (the app now starts anyway). Set a longer password or delete the variable. |
| `PermissionError: [Errno 13] ... '/data/...'` | Railway mounts volumes as root | Fixed in the Dockerfile/entrypoint. (Older versions: add `RAILWAY_RUN_UID=0`.) |
| Sign-in says "Request from another site was refused" | The app was compared with a wrong `BASE_URL` | Fixed: remove `BASE_URL`, or set it to exactly the address in the browser. |
| "The dashboard could not load its data" | Empty database (older versions) | Fixed: it now says nothing is loaded and links to Administration. Load reports. |
| Variables look shifted by one row after *Import* | `.env.example` was auto-imported | Add variables one at a time (the file no longer has inline comments). |
| `SECRET_KEY is not set` in the log | Missing variable | Add `SECRET_KEY` and redeploy. |
| Sign-in page has no *Email link* tab | SMTP not configured | Add the `SMTP_*` variables (Google App Password). |
| A report stays "needs review" | It has far fewer rows than what is held, or its subject disagrees with its content | Admin portal > Imports > *Approve* with a reason, or upload the right file. |
| `/healthz` does not answer although the deploy is green | The domain's target port is not the port in the log (often 8080) | Networking > edit the domain's port to the number in `Uvicorn running on http://0.0.0.0:XXXX`. |
| Log line "could not prepare the dashboard data" at start | Older version: warm-up ran on an empty database | Harmless; fixed. Load reports and it disappears. |
| Banner "x days left" in Railway | Trial credit | Upgrade to the Hobby plan. |
