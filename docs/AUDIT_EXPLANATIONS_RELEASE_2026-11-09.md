# Visual explanation release — 9 November 2026

Scope: release completed work from audit/source-to-visual-2026-11-09, originally d41f2f8, following the user's instruction to deploy completed tasks. NG-Dashboard only; no importer, database, schedule, data promotion, Customer360 or My Visuals feature expansion.

Implemented: collapsible What this means / How it is calculated sections on shared card/KPI renderers and several manually rendered cards; exact-label descriptions for selected metrics; separate dashboard reporting-period context; conservative unverified-calculation disclosure for unmapped visuals. Descriptions must not be treated as universal visual certification. Release review corrected distinct-job wording, non-positive-income margin handling, and the expected-cost benchmark scope. Generated production dashboard rebuilt and included, since the production Docker image copies app/ rather than frontend/.

Read-only audit utilities: static visual inventory; source-versus-database CSV reconciliation with duplicate-key, non-finite amount, row math and empty-input guards; historical JPR workbook inspection with per-year totals and validation flags. These utilities being tested does not mean the actual archived workbooks have been reconciled or historical imports approved.

Validation: 113 Python tests passed; JavaScript syntax; canonical production build; 139 existing frontend checks; Customer360, metric contract, drawer and custom visual source-membership suites. Test dependencies restored locally. Audit workflow now installs development test dependencies.

Pending: verified explanation and date/filter/comparison coverage for every visual (including dynamic and legacy charts); independent archived shipment/JPR workbook-to-database reconciliation; investigation of 2024 held profitability imports; complete browser visual audit. Exact ERP names remain identity fallback where customer codes are absent. AI chatbot and further Customer360/My Visuals enhancements are outside this release.

Deployment verification and resulting commit/deployment identifiers will be recorded on PR #16 after rollout. Rollback target before this release: main de3f41d54094e6d036e783388e9c9b7d4634fede, Railway deployment f71acaee-1a9b-4a04-9f69-f9a8a4248ceb. No schema rollback required.
