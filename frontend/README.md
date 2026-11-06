# Dashboard front end

The dashboard page is built from these pieces (plain JavaScript, no build tools):

| File | What it holds |
|---|---|
| `app.js.pre_merge` | the operations dashboard (overview, compare, customers, lanes, worklist, shipments, changes, data status) |
| `pr_*.js` | the finance pages and their data setup (profit, branches, charges, jobs, quality) |
| `s_pages.js` | the owner's summary and the scorecard |
| `f_pages.js` | variance, billing health, who needs to book costs |
| `v_pages.js` | rate margin, the visual builder and My dashboard |
| `a_pages.js` | the agent variation report and the sales performance report |
| `template.html.pre_merge`, `style.css` | the page and its styles (including the phone layout) |
| `merge_build.py` | joins the pieces; `build_prod.py` makes `../app/web/dashboard.html` |

After changing any piece run `sh build.sh`. The page never contains data: it asks the server for the person's data when it opens.

## Checking the page against a running server
`cd frontend/tests && npm install && node boot_test.js http://127.0.0.1:8000` opens the production page as an administrator, an operations user and a stranger (use the demo users from `scripts/seed_demo.py`) and checks that every page renders, money is hidden from people without access, and saved visuals reach the server.
