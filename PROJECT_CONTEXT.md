# Performance Dashboard: project context (shared by every chat and every helper)

Keep this file current. It is the single source of truth, so a new chat or another AI can pick up without the history. Never put passwords, tokens or keys in it.

## What it is
A standalone product (working name **Performance Dashboard**) for freight forwarders. First customer: **New Globe (NG, "NGL")** and **Neutral Consolidation Services (NCS)**. Product owner: Ashwin Mishra (no-code; does account and click steps only). It receives the ERP's Excel reports by email, keeps the history, and shows operations, finance, agent and sales reports to signed-in people, each seeing only what they may. A later AI chatbot is planned.

## Architecture
ERP -> Gmail (label `ERP-Reports`) -> Apps Script every 15 min (`gmail/ERP_Mail_Collector.gs`) -> `POST /api/ingest` -> queue -> importer (`app/processor.py`, `app/profit.py`) -> PostgreSQL (versioned history) -> `app/dataset.py` builds the dashboard data per person -> `app/web/dashboard.html` (all calculation in the browser) . Admin portal: `app/web/admin.html`. Sign-in: `app/auth.py`. Server: `app/server.py` (FastAPI). Hosting: Railway (app + PostgreSQL + volume at /data). Code: private GitHub repo `NG-Dashboard`.

## Data feeds
* 8 shipment registers (NG and NCS x Air Export, Air Import, Sea Export, Sea Import), emailed about every 8 hours; the file name never changes, so email arrival time is the report time. Key = Shipment No + Shipment Date (Shipment No alone repeats in the ERP; both rows count).
* Job profit report ("Charge wise Detail", billing-date basis), charge-line level, daily with the whole year, earlier years loaded once. A file replaces the lines for its own dates; other years are never touched.
* Organization master (agent details: country, network, conference, contact, email), about every two weeks, uploaded in the admin portal.
* The ERP date range must be changed every January; the admin portal warns when a report's range has run out.

## Business definitions decided with the owner
* **LOB** = the four registers (Air/Sea Export/Import) per company. A user can have several.
* **Roles:** admin, management (all pages, no admin), operations (no money), finance (money plus operations). Per person: companies, LOBs, and a separate "can see money" permission. Enforced on the server: hidden rows and even their names are never sent.
* **Free Hand** = Self Nomination. Tabs: Agent Nomination, Free Hand, Sub Agent.
* **Agent** = the register's *Booking Thru*; where that is "Self" the customer is the agent; names follow the Organization master.
* **Variation Report:** 12 months per agent (current month to date first) plus last-month change, 3-month average against the previous 3, months since last shipment, and a status (Lapsed after 2 months, Declining/Growing at 30%, New, Steady). Job Owner = owner of the latest shipment; Previous Job Owners = the 5 before that, each with the month of their latest shipment for the agent.
* **Sales Performance Report:** same layout as the ERP's sample (Air Export for both companies matches it); LOB tabs; company switch.
* **Billed** = either "Invoice No. & Date" or "Billing Details" shows a document (the first date found is the billing date).
* **Rates:** buy/sell rates exist for Air Export only, as free text; the first number is the per-kg rate (plain numbers and numbers read from text; foreign currency and lump sums above a limit are left out). Estimated freight margin = (sell - buy) x chargeable kg.
* A job short by less than 1 rupee is rounding, not a loss.
* Profit is overstated while costs are not booked (most jobs have none yet); the pages say so.
* Financial year defaults to April to March; a calendar-year switch exists.

## What is built (all tested)
Operations (overview, compare, customers, lanes, worklist, shipments, agent variation, sales performance, changes, data status), Finance (overview, variance, profitability by any angle, branch, customers, charges, jobs, quality, billing health, rate margin, data status), Owner's summary with a "what needs attention" list and a scorecard, "build your own visual" with saving per person, saved views, print, Excel (live formulas) and CSV downloads, admin portal (imports with approve/retry/undo, upload with preview, previous reports, organization master, users, settings, retention, activity log, setup checklist).

## Tests (run from the repo root with the sample ERP files)
`scripts/run_sample_test.py`, `run_robustness_test.py`, `run_year_test.py`, `run_profit_test.py` (report readers), `run_dataset_test.py` (data built from the database equals the verified data), `run_server_test.py` (sign-in, permissions, ingest, uploads, undo, users), `run_resilience_test.py` (every first-deployment failure), `frontend/tests/boot_test.js` and `portal_test.js` (the pages, opened as a browser would). The last two need a running server and `npm install jsdom`. `TEST_DATABASE_URL` points the Python tests at PostgreSQL. Not tested: pixel layout on real phones, and a deployment on Railway beyond the first live run.

## Where every setting lives
See `CONFIGURATION_REFERENCE.md` (admin portal settings, Railway variables, Gmail and Apps Script, dashboard Definitions, and the few things that live in code).

## Open items
* Waiting on the ERP/finance teams: what "Billing Details" holds; real sales persons instead of "Administrator" (71% of profit); trade lane filled in; buy/sell rates as numeric fields (and for sea/air import); 2025 registers and 2024/2025 profit reports; Organization master with Contact Name and Email columns; the ERP's sending address; one NCS email subject line; who changes the ERP date range each January.
* Later: targets/budget against actual, a daily or weekly email digest, AI chatbot, Office 365 sign-in, industry classification of shippers and consignees.

## How several chats or AIs work together
* **Code owner chat** (this project's main chat): all code, tests and dashboard changes; produces every new zip. Dashboard change requests go here.
* **Deployment helper** (any chat or AI): only Railway, GitHub and Google settings, following `DEPLOY_FROM_SCRATCH.md`. It never edits code. A failed deploy goes back to the code owner with the last 20 log lines.
* The deployment helper's brief is `HANDOVER_DEPLOYMENT_CHAT.md`.
* Start any new chat by pasting this file. When something changes, update this file and the change log below.

## Change log
* First production build: server, sign-in, admin portal, importer queue, dashboards, reports.
* Hardening after the first deployment: optional `BASE_URL`, volume permissions handled by the container, empty-system message, tolerant admin bootstrap, setup checklist, dataset warm-up.
