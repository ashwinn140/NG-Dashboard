# Configuration reference: what is set where, and where to change it

Nothing secret is written into the code. Logins, passwords, email addresses and the sender are all set in the places below. Rows are grouped by **who can change them**.

## Level 1: Admin portal (no code, no redeploy; an administrator does it)
| What | Current value | Where |
|---|---|---|
| People who may sign in, their role, companies, LOBs, "can see money", user ID, password | none until you add them (the first administrator comes from `ADMIN_EMAIL`) | Administration > Users |
| Years of history kept | 3 | Administration > Settings |
| Financial year starts in month | 4 (April) | Administration > Settings |
| Warn when a report is older than | 36 hours | Administration > Settings |
| Who is emailed when a report fails or is held | empty (falls back to the `ALERT_EMAIL` variable) | Administration > Settings |
| Agent details (country, network, conference, contact name, email) | whatever the last Organization master file held | Administration > Organization master (about every two weeks) |
| Earlier years of reports | none | Administration > Previous reports |
| A held report that should be loaded anyway | n/a | Administration > Imports > Approve (a reason is required) |

## Level 2: Railway variables (you, or the deployment helper; the app redeploys on change)
| Variable | Meaning | Required |
|---|---|---|
| `DATABASE_URL` | the PostgreSQL address (a reference to the Postgres service) | yes |
| `SECRET_KEY` | signs and hashes sign-in tokens and sessions; changing it signs everyone out | yes |
| `INGEST_SECRET` | the password the Gmail script uses when it posts reports | yes |
| `ADMIN_EMAIL` | the first administrator, created once on the first start when there are no users | yes |
| `ADMIN_NAME` | that administrator's display name (default "Administrator") | no |
| `ADMIN_PASSWORD` | the first administrator's first password (10+ characters, letters and a number); delete it once you can sign in | no |
| `PRODUCT_NAME` | the name on the pages and in emails (default "Performance Dashboard") | no |
| `MAIL_PROVIDER` | `resend` for HTTPS email; default `smtp` for older installations | for provider selection |
| `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Resend sending key (entered privately) and sender address; see RESEND_SETUP.md | for Resend email sign-in |
| `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | SMTP email transport; on Railway requires Pro or above | for SMTP only |
| `ALERT_EMAIL` | who is told when a report fails or is held | no |
| `UPLOAD_DIR` | where original files are kept (default `/data/uploads`, the volume) | no |
| `BASE_URL` | normally unnecessary: the app uses the address people open. Set it only for a custom domain. | no |
Set automatically by Railway (do not set): `PORT`, `RAILWAY_ENVIRONMENT`, `RAILWAY_PUBLIC_DOMAIN`.

## Level 3: Gmail and the Apps Script (you)
| What | Current value | Where |
|---|---|---|
| Which emails are taken | emails carrying the Gmail label `ERP-Reports` | the Gmail filter you create (for example `subject:("Shipment Register" OR "Job Profit") has:attachment filename:xlsx` > apply the label) |
| Allowed senders | set `*` to start (any sender, but only labelled emails) | Script property `ALLOWED_SENDERS` (comma-separated addresses, or `*`) |
| Extra subject check | empty | Script property `SUBJECT_CONTAINS` (optional) |
| Who is emailed if the script keeps failing | empty | Script property `ALERT_EMAIL` |
| The app's ingest address | empty until live | Script property `APP_URL` = `https://<address>/api/ingest` |
| The shared password | empty until live | Script property `INGEST_SECRET` (same value as in Railway) |
| How often it looks for new emails | every 15 minutes | `installTrigger` in the script |
| Label for emails that failed 5 times | `ERP-Reports-Failed` | `CONFIG` at the top of the script |
| Tries per email / emails per run / largest attachment / overlap | 5 / 40 / **20 MB** / 10 minutes | `CONFIG` at the top of the script |

**Note on the 20 MB limit:** a full-year charge-level profit file of about 112,000 lines is roughly 15 MB. It fits, but a bigger year would not. Raise `MAX_ATTACHMENT_MB` (Gmail's own limit is 25 MB) if the file grows.

The app itself never looks at the sender. The email subject is only a cross-check: if the subject says one company or report and the file says another, the file is held for review. A subject that cannot be read is not an error. The company and the report type are always taken from inside the file.

## Level 4: Dashboard "Definitions" (each person, saved to their login)
Top N, rows per table, age limits for open financials (90 days), age buckets (30, 60, 90, 180), comparison period, financial year start (4), week start, variance filters, low-margin limit (10%), cost-coverage warning (80%), money units, billing late after (30 days), customer-concentration warning (25%), unassigned-profit warning (20%), the sales-person names that mean "not assigned" (`Administrator`), agent lapsed after (2 months), declining/growing at (30%), which rates to use and the highest believable rate (5,000 per kg). All are under the **Definitions** button.

## Level 5: In the code (ask the code owner chat; needs a new zip)
| What | Where | Current value |
|---|---|---|
| Company names as printed in row 1 of each report, and their short codes | `app/config.py` `COMPANIES`, `COMPANY_LABELS` | "New Globe Logistik LLP" = NG, "Neutral Consolidation Services LLP" = NCS |
| Report types read from row 2 | `app/config.py` `REPORT_TYPES` | Air Export, Air Import, Sea Export, Sea Import |
| Columns a register must have, the key, the column names read | `app/config.py` `REQUIRED_COLUMNS`, `KEY_COLUMNS`, `SOURCE_COLUMNS` | Shipment No + Shipment Date is the key |
| Hold a report that has this much fewer rows | `app/config.py` `MAX_ROW_DROP` | 10% |
| Profit file columns required, and how far lines may differ from the report's own total | `app/config.py` `PROFIT_REQUIRED`, `PROFIT_TOLERANCE` | 1 rupee |
| Subject words recognised for the cross-check | `app/config.py` `SUBJECT_COMPANIES`, `SUBJECT_REPORTS` | NGL, NCS, Air/Ocean/Sea Export/Import |
| How a profit job's line of business becomes air, sea, road, customs clearance or freight forwarding | `app/profit.py` `_mode` | by words in the LOB: AIR, SEA, ROAD, CCL..., FFWD... |
| Sign-in rules | `app/auth.py` | link or code valid 15 min, 10 links per hour per address, 5 code tries, 12-hour sessions, 5 wrong passwords lock for 15 min, roles admin/management/operations/finance, companies NG/NCS, LOBs AE/AI/OE/OI |
| Request limits | `app/server.py` | 30 requests per minute per place (20 for password sign-in), uploads up to 80 MB, saved items up to 1 MB |
| Which report feeds which slot in the dashboard data, and the extra columns offered as filters (Sales Person, Trade Lane Name, countries, and so on) | `app/dataset.py` `REPS`, `EXTRAS` | the 8 registers in a fixed order |
| The agent rule (Booking Thru, or the customer where it says "Self"), which columns mean "billed", how buy/sell rates are read, currency words left out | `app/dataset.py` | see `PROJECT_CONTEXT.md` |
| Company, report and LOB names shown in the dashboard | `frontend/app.js.pre_merge` (`COMP`, `REPN`) | New Globe, Neutral Consolidation; Air/Sea Export/Import |
| Default Definitions listed in Level 4 | `frontend/app.js.pre_merge` (`DEFAULTS`) and `frontend/merge_build.py` | as listed |
| Container: Python version, port (8000), one worker, health check `/healthz` | `Dockerfile`, `entrypoint.sh`, `railway.json` | Python 3.12 |

## Logins, passwords and secrets
* **No password or login is hard-coded in the app.** The first administrator is created only from `ADMIN_EMAIL` (and optionally `ADMIN_PASSWORD`), once, when there are no users.
* Passwords are stored only as one-way hashes. Sign-in links and codes are stored only as hashes.
* Secrets live only in Railway variables and Apps Script properties, never in GitHub. `.env.example` has empty values.
* `scripts/seed_demo.py` contains **demo** users (`admin@demo.test` and so on) for trying the app on your own computer. **Never run it on the live system.**
* If `SECRET_KEY` is missing the app refuses to start on Railway. Elsewhere it would use a weak development value, and the setup checklist flags that.

## If the ERP changes: what to update
| ERP change | What to do |
|---|---|
| The company's printed name changes (for example "Pvt Ltd") | Reports are rejected with a clear message until `COMPANIES` in `app/config.py` is updated (code owner). |
| A new branch, customer, job owner, airline or port appears | Nothing: they appear by themselves. |
| New columns are added to a register or profit report | Nothing: extra columns are kept and become usable filters. Tell the code owner if one should become a standard field. |
| A required column is renamed or removed | The file is rejected naming the column; update `SOURCE_COLUMNS` (code owner). |
| The email subject wording changes | Update the Gmail filter; the app's cross-check only needs to know the company and report words. |
| The ERP's sending address changes | Update `ALLOWED_SENDERS` in the Apps Script properties (or leave `*`). |
| The ERP date range runs out (every January) | The admin overview warns; the ERP team changes the range. |
| A new LOB or line-of-business wording in the profit report | Update `_mode` in `app/profit.py` (code owner) if it should count as air, sea or customs clearance. |
| A second customer (another company) | Run a separate deployment with its own `config.py` and names. One deployment serves one customer's companies today. |

## Known limits to be aware of
* **Times in the admin portal** are shown in your computer's local time (fixed in this version; they were UTC). The database keeps UTC.
* One deployment serves one customer; company names are in code.
* Sign-in emails need a Google App Password; until then people use a user ID and password.
* Saved visuals, views and Definitions are per person, saved on the server.
