# Progress

Last updated: 2026-10-17. Current gate: **KRA 23 (bounded Phase 4 task) complete — waiting for review with KRAs 11, 20, 7 and 32.**
No other Phase 4 KRAs started. Phase 0–2 committed on branch `phase2-kra33-pilot` (3f4748a); Phase 3 committed (f9ebf88); KRA 11 committed (713e092); KRA 23 changes are uncommitted.

## Phase 0 — Source audit and seed preparation ✅
- [x] Inventory of 30 PDFs + workbook with SHA-256, page sizes, visual review → `docs/template-inventory.md`
- [x] Source audit (coverage, mismatches, broken exports, open questions) → `docs/source-audit.md`
- [x] 45 KRAs + 585 department targets extracted from XLSX, cross-checked against the Markdown (0 mismatches) → `seed/catalogue_2026-27.json` via `scripts/extract_seed.py`
- [x] Department codes recorded; KSOM/MBA and full names flagged for the college (D-003)
- [x] KRA 33 schema + evidence rules; coverage matrix for all 45 KRAs (inventory)
- [x] Decisions/assumptions → `docs/decisions.md`
- Extracted text/inventory retained in git-ignored `.work/extract/` (no need to re-read PDFs).

## Phase 1 — Foundation and access control ✅
- [x] Django 5.2 LTS + DRF on PostgreSQL 16 (local via `scripts/devdb.py`), pinned requirements, `.gitignore`
- [x] Models + migrations: users (one active VC, one active Dean/department constraints), departments, years, periods, KRAs, template versions, fixed-target assignments, submissions, revisions, reviews, reopen requests/grants, evidence, generated documents, audit events
- [x] Idempotent `seed_catalogue` (never overwrites targets), `provision_user` (one-time passwords, reset ends sessions), DEBUG-only `seed_demo`
- [x] Separate `/dean/login` and `/vc/login` pages + role-fixed endpoints, rate limiting, CSRF (incl. login CSRF), password change gate, logout broadcast across tabs
- [x] Scoped querysets (404 outside department), dashboards with year/period filters
- [ ] CI pipeline and lint/format config — not set up (no remote/CI target known); `tsc -b` + Django tests run locally
- **Exit evidence:** isolation + seed tests pass (see `docs/validation.md`).

## Phase 2 — KRA 33 pilot ✅ (pending acceptance)
- [x] Draft persistence with optimistic `edit_version`, repeatable events (≤20) and engagement rows (≤100), schema-driven form
- [x] Live HTML preview (750 ms debounce, stale requests aborted, scroll kept, fit-width zoom) in sandboxed iframe
- [x] PDF export via internal renderer (pool 2, bounded queue, busy → 503 "try again"), content-hash cache, historical revision export
- [x] Evidence: files (magic-byte check) + Drive links, active 100 MB / history 500 MB quotas, protected downloads, soft removal
- [x] Achievement tab (six periods, text as entered, no totals), Nil mode with reason + Nil report
- [x] Submit / reject / resubmit / approve / return; immutable revisions with snapshots; verification labels
- [x] Reopen request (incl. no prior row, C2), VC decision → 72 h grant, reject/return grant option (C1), Dean banner with server countdown (C9)
- [x] Shared save queue with flush on tab switch and 409 handling (C3)
- [x] Visual comparison of generated PDFs with the source (single event, 3 events × 40 rows long text, empty, Nil, real pilot flow)
- [x] Team acceptance of template fidelity/usability — accepted by project owner 2026-10-17

## Phase 3 — Prove remaining template families ✅ (pending review)
- [x] Outstanding pilot checks: C7 preview scroll preservation (50 rows) and C3 upload-during-autosave now automated browser tests (`e2e/test_browser.py`)
- [x] Engine generalised without KRA-specific app logic: measured page styles (report/survey/sheet), landscape pages, auto/conditional table columns, card editor for wide tables, ratings grid, exact-decimal fields, row/field rules, single-record templates
- [x] KRA 20 — wide repeatable table repaired onto A4 landscape (schema `kra20_v1`, template `kra20_v1.html`, shared `_records_table.html`)
- [x] KRA 7 — consolidated faculty survey with Dean-entered decimal averages (survey header style, `kra7_v1`)
- [x] KRA 32 — alumni contributions with conditional financial/non-financial fields (`kra32_v1`)
- [x] Each: draft save/reload, live preview, evidence minimum, PDF export, achievements, Nil, reject-after-close with 72 h grant, resubmit, approve (shared workflow test mixin)
- [x] Synthetic normal/long/empty/Nil sample PDFs rendered and inspected for all four piloted KRAs
- [x] Concurrent exports still bounded by the renderer pool (existing C4 test passes)
- Fixed during Phase 3: Latin-Extended glyphs (₹, Ł, Ś) fell back to system Times → Tinos Latin-Ext embedded; bold header caption synthesised as Type3 → bold face embedded; stale save errors stayed on screen; cross-field/range errors blocked draft saves (now submit-only).
- Open for the college: D-029, D-030, D-031 (evidence minima, KRA 7 consolidated layout, KRA 32 extra type/column), D-012/D-013 from Phase 2.

## Phase 4 (bounded) — KRA 11 Bridge Courses ✅ (pending review)
- [x] Schema `kra11_v1` + template `kra11_v1.html` on the existing engine (report style); catalogue mapping added idempotently — 13 assignments now point to it, targets unchanged
- [x] Department/year autofill, coordinators, HoD, fixed source intro/objectives (+ optional extra objectives), repeatable courses (≤20) with syllabus modules, outcomes, assessment, impact indicators, feedback score, suggestions, sign-off box, supporting-documents checklist
- [x] Draft save/reload, live preview, PDF export with existing approval labels; evidence/achievement/Nil/review via shared workflow tests
- [x] Shared code touched only minimally: summary count label now uses the template's activity label ("Courses in this report"; KRA 33 unchanged), KRA 11 CSS classes
- Open: D-034 assumptions (no evidence minimum; optional feedback score/checklist) for college review. No other Phase 4 KRAs started.

## Phase 4 (bounded) — KRA 23 Skill Development & Employability Training ✅ (pending review)
- [x] Schema `kra23_v1` + template `kra23_v1.html` (report style) following the KRA 23 source's own title, header rows, objectives and column wording; mapping added idempotently (13 assignments, targets unchanged)
- [x] Repeatable programmes (≤20) each with repeatable "Detail of Program" rows (≤50) — one submission per period
- [x] Shared support only: page-2 block and supporting-documents list moved to partials reused by KRA 11 (output verified identical); KRA 23 CSS
- [x] Draft save/reload, live preview, PDF export, evidence/achievement/Nil/review via shared workflow tests; browser check done
- Open: D-035 assumptions for college review. No other Phase 4 KRAs started.

## Phase 4 (bounded) — KRAs 1–3 course family ✅ (pending review)
- [x] One family definition + template, three KRA configurations (D-036); mappings idempotent (39 assignments, targets unchanged)
- [x] Separate drafts, evidence, achievements and submissions per KRA (tested); full workflow via shared mixin; browser smoke for all three
- Open: D-036 assumptions for college review. Uncommitted.

## Not done / deferred
- C10 evidence ZIP (deferred by plan). Progress PDF export and VC KRA/next-year assignment admin (Phase 5).
- Templates for the other 36 KRAs (Phase 4); their assignments show "Template pending (Phase 4)".
- OpenAPI document and frontend component tests. Browser tests (`e2e/`) cover 6 critical flows, not the full workflow.
- Cosmetic: required-field markers still show on fields that are NA for the selected KRA 32 contribution type; KRA 33 footer sits ~8 pt right of the source position.
- Deployment artefacts (Nginx/Gunicorn/Compose), backups, restore drill, malware scanning (Phases 6–7).
- Login throttling uses the in-process cache: switch to a shared cache before running >1 Gunicorn worker.
