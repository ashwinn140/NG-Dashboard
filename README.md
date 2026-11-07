# Performance Dashboard
Shipments, profit, billing and agent reports for New Globe and Neutral Consolidation in one place. The product name shown on the pages is the `PRODUCT_NAME` setting (default: Performance Dashboard).

One web app: it receives the ERP's Excel reports by email, keeps the history in a database, and shows the dashboards, reports and admin portal to signed-in people.

```
ERP -> Gmail -> Apps Script (every 15 min) -> /api/ingest -> queue -> database -> dashboard (per person) 
                                                         \-> admin portal: manual upload, previous years, organization master, users
```

## What is in the box
* **Sign-in:** one-time email link (with a 6-digit code as backup), and user ID + password. 12-hour sessions, 5 wrong passwords lock an account for 15 minutes, 10 link requests per hour per address.
* **Roles:** admin, management, operations, finance. Each person can be limited to companies and LOBs (Air Export, Air Import, Sea Export, Sea Import). Money (profit, billing, rates) goes only to people with the money permission. **The limits are enforced on the server:** what a person may not see is never sent to their browser, not even the names.
* **Import queue:** files from Gmail or the admin portal are loaded one at a time in the background, with duplicate, older-file, damaged-file and suspiciously-smaller-file checks. Held files can be approved (with a reason), failed ones retried, and the latest load of a report undone.
* **Previous years:** the admin portal's "Previous reports" page loads any number of earlier files, oldest first. A year already loaded is never touched by loading another.
* **Organization master:** upload the ERP export about every two weeks. Contact name and email show up in the Variation Report once the export has those columns.
* **Dashboards:** owner's summary, operations, finance, agent variation report, sales performance report, "build your own visual" with saving per person.

## Put it live
Follow **`DEPLOY_FROM_SCRATCH.md`** step by step (GitHub, Railway, variables, first sign-in, loading data, Gmail script, go-live checklist, and a troubleshooting table). Project background and the decisions behind the reports are in **`PROJECT_CONTEXT.md`**.

## Cost and backups
Railway Hobby (about $5 a month plus usage; expect roughly $10 to $15 all in). The database holds history for every report; a full file arrives every day, so the data can always be rebuilt, and the original files are kept on the volume.

## Try it on your own computer
```
pip install -r requirements-dev.txt
DATABASE_URL=sqlite:///data/demo.db python scripts/seed_demo.py <folder with the sample Excel files>
DATABASE_URL=sqlite:///data/demo.db ADMIN_EMAIL=admin@demo.test uvicorn app.server:app_factory --factory --port 8000
```
Demo users after seeding: `admin@demo.test` / `Demo-admin-1234`, `ops@demo.test` / `Demo-ops-12345` (New Globe Air Export only), `fin@demo.test` / `Demo-fin-12345`.

## Tests (all pass; the last two also on PostgreSQL 16)
`scripts/run_sample_test.py`, `run_robustness_test.py`, `run_year_test.py`, `run_profit_test.py` (the report readers), `run_dataset_test.py` (the data built from the database equals the verified data), `run_server_test.py` (sign-in, permissions, ingest, uploads of previous years, undo, users). Run with `python scripts/<name>.py <folder with the sample files>`; set `TEST_DATABASE_URL` to use PostgreSQL.

## Changing the dashboard
The page is built from the pieces in `frontend/` (see `frontend/README.md`); run `sh frontend/build.sh` after a change.

---

# How the ERP reports are read (rules)

# New Globe and Neutral Consolidation dashboard: report processor (Step 4)

Reads the ERP's Excel shipment registers, checks them, and keeps every version.
The dashboard (later steps) reads from the database this fills.

## What it does with each file
1. Identifies company and report (Air/Sea, Export/Import) from the title rows inside the file, not the file name.
2. Same file twice: ignored ("duplicate").
3. Older than the current report: logged, never replaces newer data ("stale").
4. Missing key columns, blank or repeated shipment keys, unreadable dates: rejected ("failed"). Current data stays.
5. More than 10% fewer rows than the current report: held ("needs_review"). Current data stays until an admin approves with a reason.
6. Otherwise "promoted": new, changed and no-longer-present shipments are applied in one step.
   A shipment missing from a report is "not present", never "completed".

The email subject (for example "Shipment Register - Ocean Export - NGL") is read as a cross-check only: if it names a different company or
report than the file contains, the file is held for review. A subject that cannot be read is not an error.

## History across years
Each report states the dates and branches it covers in its title rows (for example "Date Range : 01-Jan-2026 To 31-Dec-2026, Branch : ...").
A shipment can only be marked "not present" if it falls inside the dates AND branches the report covers. So loading this year's register never
touches last year's shipments, and a report covering fewer branches never makes the other branches disappear.
Last year is loaded once by uploading its eight full-year reports in the admin portal (the one-time backfill). It stays until you remove it.
If a file's title rows cannot be read, the earliest and latest shipment dates in the file are used, and the import log says so.

## Job profit analysis (Charge wise Detail)
`app/profit.py` reads the ERP's job profit report: every income or expense line of a job, with Total and Job Total rows that are used only as a check.
- The lines must add up to the report's own grand total, otherwise the file is rejected and both numbers are shown.
- Columns are read by name (any order; extra columns are kept). The two "Organization" columns are read as the job's customer (first) and the party on the line (second).
- `ingest_file` finds out by itself whether a file is a shipment register or a profit report.
- Same rules as the registers (duplicate, older, bad, suspiciously smaller). The report arrives daily as a full-year snapshot; earlier years are loaded once. A file covers the dates in its title: lines loaded for those dates and missing from the new file are "not present"; lines for other dates (earlier years) are never touched.
- Size: a full-year file of about 112,000 charge lines (15 MB) loads in about 80 seconds and needs about 650 MB of memory while it runs.
- Test: `python scripts/run_profit_test.py <folder with the Excel files>`

## Years that move (a product, not a one-off)
- `year_slots` / `history_window(today, years, fy_start_month)`: the years kept and compared are relative to today (this year plus the years before). `fy_start_month=1` is the calendar year; `4` is India's April-March accounting year. The window moves by itself when the year changes.
- `coverage(engine, today, years, fy_start_month)`: for every company and report, how many shipments are held for each year in the window, and whether the loaded imports together cover the whole year (an April-March year needs two calendar-year ERP files).
- `health(engine, today, now)`: what the admin portal shows and emails about: the ERP report's date range has run out (the new year has started
  but the ERP still sends last year's range), or a report has stopped arriving.
- `retention_preview` / `apply_retention(engine, approved_by, reason, today, years)`: limit history to the window. Needs an admin and a reason, and is logged in `admin_log`.

A shipment is identified by Shipment No + Shipment Date together (Shipment No alone repeats in the ERP; both shipments are counted).

## Survives changes to the ERP export (tested)
- Column ORDER never matters. Columns are read by name. Repeated headers (Unit, Unit.1 ...) are stored but ignored when deciding if a shipment changed.
- EXTRA columns never matter. They are stored; adding or removing a column is never counted as a change; the import log notes which columns appeared or vanished.
- Header case and spacing are tolerated ("job  owner" = "Job Owner").
- Blank columns, blank rows and "Total" footer rows are ignored. Dates may be real Excel dates or text (05/11/2026, day first).
- Still rejected, with the reason named: a missing key column (Shipment No, Shipment Date) or a missing needed column (Branch, Customer, Status, Job Owner).

## Admin actions (the admin portal screens call these)
- `preview_file(engine, path)`: what loading a file WOULD do (company, report, rows, dates, columns added/removed, new/changed/gone counts, verdict), writing nothing.
- `ingest_file(..., source="manual", uploaded_by=...)`: load a manually uploaded file through the same rules as email.
- `list_imports(engine, status)`: the import log, with who uploaded, who approved and why.
- `approve_import(engine, import_id, approved_by, reason)`: release a report held for review.
- `retry_import(engine, import_id)`: run a failed import again from the archived original.

## Run the checks on your sample files
    pip install -r requirements.txt
    python scripts/run_sample_test.py <folder with the Excel files>
    python scripts/run_robustness_test.py <folder with the Excel files>

## Settings
`app/config.py`: company names, report names, key columns, required columns and the 10% row-drop limit.
Database: SQLite locally; on Railway set DATABASE_URL to the Postgres address. No code change.
