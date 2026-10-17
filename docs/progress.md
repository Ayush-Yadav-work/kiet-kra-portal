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
- Open: D-036 assumptions for college review. Committed by the project owner (73765ac); README review section added with KRAs 36–37.

## Phase 4 (bounded) — KRAs 36–37 FDP/STP family ✅ (pending review)
- [x] One family definition + template, two configurations (D-037); mappings idempotent (26 assignments, targets unchanged)
- [x] KRA 36 staff labels without faculty claims; KRA 37 FDP wording, I&E/IPR focus area, ≥ 30 hours enforced at submission only
- [x] Repeatable programmes (≤20) with participant (≤100) and module tables; separate drafts/evidence/achievements per KRA
- [x] Shared change: Prepared/Approved box moved to `_signoff_box.html` (KRA 11/23/1–3 output identical); optional `range_message` on numeric fields
- Open: D-037 assumptions for college review. Committed (39de3d8).

## Phase 4 (bounded) — KRAs 8, 9, 10 consolidated surveys ✅ (pending review)
- [x] One survey family (D-038), three configurations; mappings idempotent (39 assignments, targets unchanged); KRA 7 untouched
- [x] Exact source questions/order/scale; consolidated mapping of every personal field; KRA 9 with 9a, 9b or both in one submission
- [x] Shared engine: field/rule `when` (contains), family preparer hook — KRA 7/11/23/1–3 output verified identical
- Open: D-038 assumptions for college review; deselected KRA 9 fields stay visible in the form. Committed (331a234).

## Phase 4 (bounded) — KRA 19 Industrial Visits ✅ (pending review)
- [x] `kra19_v1` schema + template: full 19a per visit, multiple visits in one submission, LO→PO/PSO matrix, consolidated 19b (D-039)
- [x] Mapping idempotent (targets unchanged, incl. "NIL"); no mandatory evidence; existing review workflow
- Open: D-012 PSO1 duplicate still unresolved (labels kept); D-039 assumptions for college review. Committed (2fbd120).

## Phase 4 (bounded) — KRAs 18, 17, 13 industry collaboration ✅ (pending review)
- [x] KRA 18 `kra18_v1`: MoUs with nested activities, full source report per activity (D-040)
- [x] KRA 17 `kra17_v1`: one landscape table, split pagination repaired (D-041)
- [x] KRA 13 `kra13_v1`: memberships with contributions, meetings, impact, summary, sign-off (D-042)
- [x] Mappings idempotent, targets unchanged; no mandatory evidence; existing workflow; shared `_records` (D-043)
- Open: D-040–D-042 college questions. Committed (61840c6).

## Phase 4 (bounded) — KRAs 15, 22, 31, 38 table reports ✅ (pending review)
- [x] Shared one-table sheet template `records_sheet_v1.html` (D-044) for all four
- [x] KRA 15 entrepreneurs with faculty adaptation (D-044); KRA 22 career counselling (D-045); KRA 31 hackathons/ideathons (D-046); KRA 38 FDPs/MDPs attended, Letter portrait (D-047)
- [x] Mappings idempotent, targets unchanged; no mandatory evidence; no computed percentages/totals
- Open: D-044–D-047 college questions. Committed (92508f7).

## Phase 4 (bounded) — KRAs 4, 5, 6 and 24 ✅ (pending review)
- [x] KRAs 4–6: field-projects family, three separate configurations; programme components + per-programme student completions (D-048)
- [x] KRA 24: placement / higher-education records with conditional columns; values of the other category kept but excluded (`keep_inactive`, D-049)
- [x] Mappings idempotent, targets unchanged; no computed percentages; frontend rebuilt (type + form change)
- Open: D-048–D-049 college questions. Committed (6c9dd60).

## Phase 4 (bounded) — KRAs 12, 25, 26 awards ✅ (pending review)
- [x] KRA 12 `kra12_v1`: source header + structured award records inside the open details area (D-050)
- [x] KRAs 25/26: awards sheet family, separate datasets; team award = one record with all members (D-051)
- [x] Mappings idempotent, targets unchanged; no computed counts; frontend unchanged
- Open: D-050–D-051 college questions. Committed (11a519c).

## Phase 4 (bounded) — KRAs 27–30 events organized ✅ (pending review)
- [x] Portal event-organizing format (no supplied template): `event_schema` + `event_family_v1.html`, four configurations (D-052)
- [x] KRA-specific fields (sport, cultural activity, theme, club/forum + semester); multiple events per report; no totals
- [x] Mappings idempotent, targets unchanged (KRA 30 per-club/per-semester target shown as assigned); frontend unchanged
- Open: D-052 college questions. Committed (8ea5527).

## Phase 4 (bounded) — KRAs 43, 44, 45 ✅ (pending review)
- [x] KRA 43 project-created Scopus conference report with paper counts and explicit indexing status (D-053)
- [x] KRA 44 BOOT camp / peer learning report with source sections and editable phases (D-054)
- [x] KRA 45 flagship event report with SDGs, resource persons, neutral follow-up plan label; paste-in pages → evidence (D-055)
- [x] Mappings idempotent, targets unchanged; frontend unchanged
- Open: D-053–D-055 college questions. Committed (8ce4b52).

## Phase 4 (bounded) — KRAs 21 and 39 (adapted formats) ✅ (pending review)
- [x] KRA 21 training-conducted report; exam qualifiers optional supporting information only (D-056)
- [x] KRA 39 infrastructure-grant report; sanctioned / received / utilized INR kept distinct; lakhs ambiguity recorded (D-057)
- [x] Mappings idempotent, targets unchanged; frontend unchanged; browser tests hardened (wait before tab selection)
- Open: D-056–D-057 college questions. Committed (e4e934c).

## Bug fix — event-tab reset after workspace load ✅
- [x] Cause: `SubmissionLoader` remounted the editor (`key={state.n}`) on every completed load; React StrictMode runs the load effect twice in development, so the second response remounted the editor, resetting the selected event tab and discarding input typed in between (a late/stale load in any environment does the same).
- [x] Fix: loads are aborted when their effect is cleaned up (only the current load may update state); the loader is keyed by submission id so a KRA/period switch starts fresh; explicit reloads (after submit, conflict resolution, reopen request) still remount on purpose.
- [x] Browser regression test added. Committed (6b34e82).

## Phase 4 (bounded) — KRAs 14, 16, 34, 35 (project-created formats) ✅ (pending review)
- [x] KRA 14 Yukthi registrations with student teams (D-058); KRA 16 innovation ambassadors (D-059)
- [x] KRAs 34/35 faculty financial support: sanctioned vs paid INR, multiple payments, Rs. 5,000 condition printed without aggregation (D-060)
- [x] Mappings idempotent, targets unchanged; frontend unchanged; verification box kept with the report end (D-061)
- Open: D-058–D-061 institutional review. Committed (41885d4).

## Phase 4 (bounded) — KRAs 40, 41, 42 (project-created) ✅ (pending review)
- [x] KRA 40 gender audit: findings with linked follow-up actions (Planned/Ongoing/Completed), follow-up without a new audit (D-062)
- [x] KRAs 41/42 via the event family, KRA 27–30 output unchanged (D-063)
- [x] Coverage reconciled: 45/45 KRAs mapped, implemented and tested; browser smoke now covers all 45 (KRAs 11/23 added) (D-064)

## Phase 4 review gate — open
- Implemented and tested: 45/45. Institutionally accepted: 0/45 (all formats await college review; see **college** items in decisions.md).
- Exit criterion "no unreviewed report exports" is NOT met until that review happens. Phase 5 not started.
- Committed on phase2-kra33-pilot.

## Phase 5A — VC KRA management and next-year assignments ✅ (pending review)
- [x] KRA creation with an installed, confirmed report layout; KRA list (D-065)
- [x] Draft assignments per department/year with exact target text and template; edit/delete until finalized
- [x] Copy a year's finalized assignments into next-year drafts with explicit conflict reporting; repeat-safe
- [x] Review summary and transactional, double-click-safe finalization; finalized assignments read-only; past years readable
- [x] VC-only APIs and screens (Assignments, KRAs); audit events; API reference `docs/api.md`
- Not in 5A: progress PDF export, VC review filters/histories (5B). Phase 4 institutional-review gate still open. Committed on phase2-kra33-pilot.

## Not done / deferred
- C10 evidence ZIP (deferred by plan). Phase 5B: progress PDF export, VC review filters and histories.
- Institutional review of all 45 report formats (Phase 4 exit gate).
- OpenAPI document (a hand-written reference is in `docs/api.md`) and frontend component tests. Browser tests (`e2e/`) cover 22 flows.
- Cosmetic: required-field markers still show on fields that are NA for the selected KRA 32 contribution type; KRA 33 footer sits ~8 pt right of the source position.
- Deployment artefacts (Nginx/Gunicorn/Compose), backups, restore drill, malware scanning (Phases 6–7).
- Login throttling uses the in-process cache: switch to a shared cache before running >1 Gunicorn worker.
