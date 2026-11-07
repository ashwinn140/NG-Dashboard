# Dashboard production frontend

The deployed application is built from `app_prod.js` (calculations, pages and exports),
`production_shell.html` (layout, styles, authentication bootstrap and navigation),
and the local D3/fflate files in `vendor/`. No ERP data is embedded.

Run `sh frontend/build.sh` from the repository root after changing these sources.
Commit both the source and generated `app/web/dashboard.html`; Railway's Docker
build serves that generated file directly. The earlier review assembly files are
retained for reference and are not production build inputs.

## Audit checks

Run Python regressions with `python -m unittest discover -s tests -v`.
For an entirely synthetic source-to-visual audit, run
`python scripts/build_audit_fixture.py`, install the dependencies in
`frontend/tests`, then run `node frontend/tests/data_audit.js` from the root
(with NODE_PATH set to frontend/tests/node_modules if necessary).
The fixtures and JSON results go to /tmp and never connect to production.
DOM tests exercise report rendering and calculations, not pixel layout.
