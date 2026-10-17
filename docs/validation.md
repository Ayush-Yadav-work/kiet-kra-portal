# Validation log

## Current summary (2026-10-17)

| Check | Recorded result | When |
|---|---|---|
| `python backend/manage.py test tests` (renderer running) | **506 tests, OK**, 0 skipped | Phase 6B baseline (`71d326c`); not rerun in 6C (no backend change) |
| `python e2e/run_isolated.py` (isolated browser suite) | 24 OK at 6B; **25 tests, OK (first full run: 23 OK + 2 failures where existing tests asserted pre-6C behaviour — the unticked KRA 9b input still visible, and the finalize panel as a dialog; both tests updated, the KRA 9 test now also proves the kept value returns when 9b is ticked again)** at 6C | run in Phase 6C |
| `npm --prefix frontend run build` (`tsc -b` + Vite) | OK | run in Phase 6C |
| `python e2e/run_perf.py` | local Windows dev-server figures only; not production capacity | Phase 6B |

Only the 6C rows marked "run in Phase 6C" were executed for Phase 6C; the others are recorded results. Browser tests must be run
through `e2e/run_isolated.py`; historical entries below that show `python e2e/test_browser.py` record how tests were run at the time.

## Historical log (results as recorded at the time; counts and commands may be superseded)

The earliest results below were run on 2026-10-16 on the development machine (Windows 11, Python 3.11, PostgreSQL 16.2
via `scripts/devdb.py`, Chromium 156 via Playwright 1.64), when the project was a local pilot without server, load or recovery testing.

## Automated tests

`python backend/manage.py test tests` (renderer running) → **Ran 45 tests, OK**.
Without the renderer the 3 `PdfExportTests` are skipped, not passed.
`npm --prefix frontend run build` (`tsc -b` + Vite) → **OK**.

| Matrix area (plan 12) | Covered by | Result |
|---|---|---|
| Login portals | `LoginPortalTests`: correct role, opposite role rejected without session, generic errors, other-portal session not switched (409), cross-role API 403, inactive denied, rate limit 429, must-change-password gate, logout, CSRF on login | Pass |
| Permissions | `DepartmentIsolationTests`: 13 read/write/export/evidence/reopen endpoints on another department → 404; list scoping; VC sees all; malformed IDs 404; VC cannot edit | Pass |
| Calendar | `CalendarTests`: IST midnight ↔ UTC, exact open (inside) / exact close (outside), leap-day 29 Feb 2028, no draft before open/after close | Pass |
| State | incomplete draft saves; structural validation; status not client-writable; invalid submit lists field errors; submitted locked; double submit no duplicate revision; immutable revision; Nil reason | Pass |
| Concurrency | two-tab 409 conflict; stale VC revision rejected; double approve rejected | Pass |
| Targets | exact strings ("NA", "3", long KRA 43 text, 1050119); 585 assignments; no auto future-year targets; target lock; reseed keeps stored value; snapshot unaffected by catalogue edit | Pass |
| Evidence | signatures (HTML/SVG/EXE rejected), Drive-only links, protected download headers, removed file retained, other department 404 | Pass |
| Nil | reason required, no evidence, normal review/approval | Pass |
| Report | XSS escaped, no remote resources, server-derived label (client `verification_label` ignored), multi-event + Nil preview, label through approve → return → historical revision | Pass |
| C1 | >72 h left: no option, no grant; <72 h: exactly one grant = decision + 72 h; after close unchecked: none; grant enables editing and expires; DB rejects grant without matching FK | Pass |
| C2/C11 | request with no row → one Draft row (edit_version 0) + one request; duplicate rejected; Not submitted while pending/denied (Dean list + VC progress); Draft after first evidence upload | Pass |
| C3 | evidence upload leaves edit_version unchanged; concurrent draft save succeeds | Pass |
| C4 | 8 concurrent renders: peak ≤ pool (2), excess → busy, renderer health answers < 2 s under load | Pass |
| C5 | Drive link has null file fields; FILE row without checksum rejected by DB | Pass |
| C6 | removed file not counted toward active quota; history cap enforced | Pass |
| C9 | banner endpoint lists active grants only, empty at expiry, other department never sees them | Pass |
| C12 | renderer made zero requests to a local HTTP server for CSS/img/background/file:// references; exported PDF embeds only Tinos fonts and the inline logo | Pass |

Not yet covered: C7 scroll preservation while editing a 50-row table (implemented, **not tested**), browser-level
Playwright workflow tests, renderer crash/restart, disk-full upload, DB outage, restore drill.

## Browser walkthrough (built-in browser against Vite :5173 + Django :8000 + renderer)
Performed with synthetic demo accounts:
1. VC login page rejected Dean credentials with the generic message; Dean login reached `/dean/dashboard` (CSE only, P2 open).
2. KRA 33 workspace: status "Not submitted" until first save (C11); typing autosaved ("Saved hh:mm"), live preview updated; checkbox list and table rows reflected in preview. **Bug found and fixed:** unanswered Yes/No radios were sent as `null` and rejected — validator now treats `null` as unanswered.
3. Saved a newer version through the API behind the page, then typed → conflict banner kept typed values; "Load the saved copy" reloaded server data (C3/409).
4. Submit without evidence → blocked, switched to Evidence tab with message. Added Drive link via form; uploaded PDF + PNG; disguised HTML ".pdf" rejected; edit_version unchanged.
5. Submitted → read-only. VC dashboard counts (585 assigned / 1 submitted), status filter, review page. **Bug found and fixed:** current revision preview was labelled "Historical revision 1"; label rules rewritten and regression-tested.
6. Reject with reason (16 days left → no grant option shown). Dean dashboard listed the reason.
7. Dean requested reopening for closed P1 with no report → row shown Not submitted + "request pending" (C2/C11); VC approved in the queue; Dean dashboard banner "Reopened KRAs — Action Required … Expires in 71h 59m" (C9).
8. Dean resubmitted P2 (revision 2) and a Nil report for P1 inside the grant; VC review of closed P1 showed "Grant 72 hours to resubmit" checked by default (C1); approved both; exported PDF reads "Verified by VC - Demo Vice-Chancellor" in body and footer.
9. ECE Dean visiting a VC URL was redirected to the Dean dashboard; API returned 404 for the CSE submission.
10. Mobile (375 px): Form/Preview toggle works. **Bug found and fixed:** wide table overflowed the page; grid columns now `min-w-0` (page width = viewport).

## PDF visual comparison (KRA 33)
Method: `render_sample` + `scripts/compare_pdf.py` side-by-side PNGs, plus PyMuPDF geometry measurement.
- Page: Letter portrait, as source. Header logo at 9.0–82.5 pt (source 8.6–82.1), rule at 94.5 pt (source 94.1), footer "Page N | M" at 719.5 pt (source 719.4).
- Section order/titles, Particular/Details table, engagement table columns, participation table, 13-item checklist and sign-off match the source. Fonts: Tinos (Times-metric) only.
- Intentional differences (D-011): period summary block at top; source boilerplate not pre-filled; page-4 signature overflow merged; verification label in footer and closing box; each additional event starts on a new page.
- Long data: 3 events × 40 rows + long text → 21 pages, table headers repeat, no clipped cells, headings kept with their content (fixed an orphaned "9. Documentary Evidence" heading).
- Empty draft and Nil report render with clear placeholders and "Pending approval".
- Not verified: Devanagari/non-Latin scripts (fall back to system fonts on the server — install Noto fonts in deployment).

---

# Phase 3 validation (2026-10-17)

Same machine/stack as above. All results below were actually run.

## Automated
- `python backend/manage.py test tests` (renderer running) → **Ran 72 tests, OK** (45 Phase 0–2 + 27 Phase 3).
- `python e2e/test_browser.py` (Vite + Django + renderer running, `seed_demo` accounts) → **Ran 6 tests, OK**.
- `npm --prefix frontend run build` → OK.

| Area | Test | Result |
|---|---|---|
| Pilot check C7 | 50-row KRA 33 table: preview scrolled to 1500 px, row edited → preview re-rendered, scroll within 5 px | Pass (browser) |
| Pilot check C3 | evidence upload while autosave pending → no conflict, later save succeeds with typed value | Pass (browser) |
| Portals | VC page rejects Dean; typed VC URL redirects Dean | Pass (browser) |
| Shared workflow ×3 (KRA 20, 7, 32) | template assigned/schema served; draft save + exact reload; preview content; strict validation lists fields, achievement, evidence; submit → reject after close with grant (exactly one grant) → edit inside grant → resubmit rev 2 → approve; rev 1 payload unchanged; achievement appears in period entries; Nil needs reason only; PDF export Tinos-only on every page, "Pending approval" | Pass |
| KRA 20 | end-before-start rejected at submit but draft saves; auto Department column cannot be entered; required vs optional columns; mode options; 101 rows rejected; landscape page | Pass |
| KRA 7 | "4.255" saved as typed in draft, rejected at submit with "not rounded" message; >5 / <1 / >10 rejected; non-numeric blocks save; all 10 statements required; respondents ≤ surveyed; 11 ratings rejected; "3.80"/"4.10" preserved exactly in HTML and PDF | Pass |
| KRA 32 | financial rows require amount/mode/receipt/transaction; non-financial rows require item details and reject stale payment values; amount precision and minimum; NA cells rendered; no totals | Pass |
| KRA 32 UI | switching type to Equipment/Asset shows payment fields as NA and clears a typed amount; item details saved and previewed | Pass (browser) |
| KRA 7 UI | "3.80" and "7.50" survive autosave + reload; preview shows "7.50 / 10" | Pass (browser) |
| KRA 20 UI | card editor adds two records; bad date order still saves draft; Validate reports it | Pass (browser) |
| Seed | template in use is never rewritten by `seed_catalogue` (reports conflict) | Pass |
| Regression | all Phase 0–2 tests incl. C1/C2/C4/C9/C11/C12 and isolation | Pass |

## Visual review of synthetic sample PDFs
Generated with `python backend/manage.py render_sample` into `.work/renders/kra{33,20,7,32}/` (`normal`, `long`, `empty`, `nil` + `.html` previews). Compared with the sources using `scripts/compare_pdf.py` / `scripts/pdf_overview.py` and PyMuPDF measurements.

| KRA | Pages (normal / long / empty / Nil) | Findings |
|---|---|---|
| 20 | 1 / 51 (100 records, long text) / 1 / 1 | Source split over 3 portrait pages → one landscape table with all 15 source columns in order; header row repeats on every page; headers wrap at "/" not mid-word; no clipped cells; Unicode names render. |
| 7 | 3 / 4 / 3 / 1 | Survey header matches source (logo 212.2/36.8 pt vs 212.2/36.9; caption and 3 pt maroon rule); details table, 10 statements with Poor…Excellent columns, 1–10 row and Suggestions box follow the source; added average column and analysis sections per D-030. |
| 32 | 1 / 51 / 1 / 1 | Source split over 2 portrait pages → one landscape table; NA cells for non-applicable fields; ₹ heading renders in Tinos after the Latin-Ext fix; no totals. |
| 33 (regression) | 3 / 21 / 3 / 1 | Header geometry unchanged (logo 8.2 pt vs 8.6; rule 93.8 vs 94.1; footer 718.9 vs 719.4 pt vertically, ~8 pt right of source horizontally). |

Font audit across all 16 sample PDFs (every page): only Tinos embedded.

Not covered: real college data volumes, Devanagari names, printing on physical paper, institutional sign-off of the D-029–D-031 adaptations.

---

# KRA 11 validation (2026-10-17)

- `python backend/manage.py test tests.test_kra11` → **Ran 10 tests, OK**: mapping idempotent (13 assignments → `kra11`, targets unchanged after re-seed); exact draft round trip; preview content incl. Unicode names; strict validation lists all required fields and does **not** require evidence or optional fields; completed ≤ enrolled; 1-decimal hours ("30.25" rejected at submit, not rounded); module table min 1 row; non-numeric hours block save; 20 courses accepted, 21 rejected; source wording present and "VAC/Add-on" absent; shared workflow (submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only on all pages).
- Full regression (shared rendering touched): `python backend/manage.py test tests` → **Ran 82 tests, OK**.
- Frontend unchanged → no rebuild needed. Browser check (built-in browser, ECE demo): KRA 11 opens with course tabs and "+ Add course"; typed values autosaved ("Saved"), survived reload and appeared in the live preview.
- Samples (`python backend/manage.py render_sample --kra 11`) in `.work/renders/kra11/`: normal (2 courses × 4 modules) 8 pages; long (6 courses × 40 modules, long text) 55 pages; empty 4 pages; Nil 1 page. Visual review against the source: header/footer geometry identical to KRA 33 style; header table, fixed intro/objectives, course row, syllabus, outcomes, assessment, impact, feedback, signature box and supporting-documents page follow the source order; syllabus header repeats across pages; no split or clipped rows. Fixed during review: the narrow "Mode Offline/Online/Hybrid" column broke words letter-by-letter → explicit column widths.
- Regression samples for KRAs 33/20/7/32 re-rendered: page counts unchanged (3/21/3/1, 1/51/1/1, 3/4/3/1, 1/51/1/1); all 20 sample PDFs embed only Tinos.
- Not verified: real course data, printing.

---

# KRA 23 validation (2026-10-17)

- `python backend/manage.py test tests.test_kra23 tests.test_kra11` → **Ran 20 tests, OK**. KRA 23: mapping idempotent with targets unchanged; exact draft round trip; incomplete draft (title only) saves; strict validation lists required fields, no evidence required, optional fields not required; per-row completed ≤ enrolled, required columns, 1-decimal hours and mode options (draft still saves as typed); 2–3 programmes × 50 rows in one submission, 51 rows rejected; un-ticked objectives/indicators are not printed as achieved; "VAC/Add-on" absent; shared workflow (submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only).
- Shared partials refactor: KRA 11 sample HTML (normal/long/empty/Nil) compared before/after with normalised whitespace → identical.
- Full regression: `python backend/manage.py test tests` → **Ran 92 tests, OK**.
- Frontend unchanged → no rebuild. Browser check (ECE demo): programme title + one record entered via the card editor, *Save draft* → "Saved", reload kept title/name/mode, live preview showed the record and "Pending approval", `/export/?inline=1` returned `application/pdf` (238 KB).
- Samples `.work/renders/kra23/`: normal (1 programme, 2 rows, 4 modules) 4 pages; long (3 programmes × 30 rows × 30 modules, long text) 66 pages; empty 3; Nil 1. Visual review: title/header rows and font sizes match the source page 1; program and syllabus table headers repeat across pages; no clipped cells; only Tinos embedded; approval label in summary, footer and closing box. Note: in the normal sample the Prepared/Approved box moves to its own page because it is kept unsplit (source fits it on page 2).

---

# KRAs 1–3 validation (2026-10-17)

- `python backend/manage.py test tests` → **Ran 117 tests, OK** (25 new in `tests/test_kra1_3.py`: mappings + stored schema = family definition, idempotent re-seed, three separate submissions with independent payload/achievement/evidence/status, KRA-specific fields (KRA 3 field rejected on KRA 2; KRA 1 enrolment optional; completed ≤ enrolled), objectives only when ticked, shared workflow per KRA incl. reject-after-close grant, Nil, PDF Tinos-only). KRA 11 sample HTML bodies identical before/after.
- `python e2e/test_browser.py` → **Ran 7 tests, OK** (new: KRAs 1, 2, 3 save → reload → preview heading → PDF export, values not shared). Browser tests were made rerunnable (unique values per run).
- Samples `.work/renders/kra1|kra2|kra3/`: normal 7 pages each (2 courses); KRA 2 long (6 courses × 40 modules) 48 pages; empty 4; Nil 1. Visual: KRA 2 page 1 matches the source; KRA 1/3 detail rows show Course Code / Platform columns; fixed mid-word header wrap in the detail table; syllabus header repeats; approval labels present; only Tinos embedded.
- Frontend unchanged → no rebuild.

---

# KRAs 36–37 validation (2026-10-17)

- Pre-check: KRAs 1–3 committed by the project owner (73765ac); their recorded results (117 backend, 7 browser) re-confirmed below by the full runs.
- `python backend/manage.py test tests.test_kra36_37` → **Ran 21 tests, OK**: both mappings + stored schema = family definition, idempotent re-seed (26 assignments, targets unchanged), separate submissions/achievements/evidence, KRA 37-only field rejected on KRA 36; KRA 37 hours 29.9 rejected at submit with the workbook message, 30 / 30.0 / 45.5 accepted, 12 saved as draft exactly but submit refused, Nil submit accepted with 5 hours in the draft; KRA 36 accepts 2 and 29.5 hours and has no focus area/faculty labels; incomplete drafts save; required vs optional fields; claims not printed unless ticked; shared workflow per KRA (submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only).
- Full regression: `python backend/manage.py test tests` → **Ran 138 tests, OK**. Shared sign-off partial: 18 KRA 11/23/1–3 sample HTML bodies identical before/after.
- `python e2e/test_browser.py` → **Ran 8 tests, OK**, run twice (rerunnable). New: KRAs 36 and 37 save → reload → preview (Staff/Faculty Participation) → PDF export; KRA 37 submitted with the UI button, approved by the VC on the review page, exported PDF shows "Verified by VC - Demo Vice-Chancellor".
- Frontend unchanged → no rebuild.
- Samples `.work/renders/kra36/` and `kra37/`: normal (2 programmes × 4 participants × 4 modules) 7 pages each; KRA 37 long (3 programmes × 60 participants × 30 modules, long text) 34 pages; empty 3; Nil 1. Visual review against the source: same title block, particulars rows, introduction/objectives cells, participation and syllabus tables, outcomes, assessment table, "The programme included", sign-off box and documentary-evidence page; participant table header repeats; no split/clipped rows; only Tinos; "Pending approval" in summary, footer and closing box.

---

# KRAs 8–10 validation (2026-10-17)

- Pre-check: KRAs 36–37 committed (39de3d8), working tree clean before starting.
- `python backend/manage.py test tests.test_kra8_10` → **Ran 29 tests, OK**: question text found verbatim in each source PDF's text, counts 12/12/10/10, source order, scale labels and 2-decimal handling; KRA 10 relationship options (Academic Expert first) found in the source; decimals 1, 5, 1.00, 5.00, 3.5 accepted; 0.99, 5.01 rejected and 4.255 rejected "not rounded" at submission while the draft keeps them (4.255 reloads exactly); "abc" blocks save; respondents ≤ surveyed; KRA 9: 9a only and 9b only submit without the other variant's ratings and with its invalid counts ignored, both requires both, none selected rejected; deselecting 9b keeps its data in the draft, preview/submission PDF omit it; each variant's own averages shown, none combined; mappings idempotent, KRA 7 still on `kra7`; separate submissions, achievements and evidence; shared workflow per KRA (submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only).
- Full regression: `python backend/manage.py test tests` → **Ran 167 tests, OK**. KRA 7 sample HTML bodies identical to the earlier render; KRA 11/23/1–3 bodies identical (18 files).
- `python e2e/test_browser.py` → new survey test passes (KRAs 8/10 save → reload with "4.50" → preview → export; KRA 9 tick 9a + 9b, enter averages, untick 9b → data kept after reload, preview shows only 9a, export OK). Five consecutive full-suite runs after hardening: 4 OK, 1 run with an error in the existing KRA 32 test during a slow run (79 s vs ~48 s); not reproduced in the next two runs — treat as timing-sensitive under load. Hardening: helpers wait for network idle before typing; the wrong-portal test also accepts the real rate-limit message (5 failures / 15 min) and asserts no session.
- Frontend unchanged → no rebuild.
- Samples: `.work/renders/kra8/` normal 3, long 5, empty 3, Nil 1; `kra10/` normal 3, empty 3, Nil 1; `kra9/` normal (9a+9b) 6, only9a 3, only9b 3, long 8, empty 1, Nil 1. Visual review: survey header/branding as KRA 7; details tables show consolidated/NA rows; rating grids keep the five source columns plus the average column; suggestions box kept together; Feedback Analysis and sign-off follow; "Pending approval" in summary, footer and closing box; only Tinos embedded.

# KRA 19 validation (2026-10-17)

- Pre-check: KRAs 8–10 committed (331a234) with their scoped checks recorded above.
- `python backend/manage.py test tests.test_kra19` → **Ran 12 tests, OK**: required fields (18) vs optional (9), no evidence required; mapping idempotent, targets unchanged; matrix exact round trip with empty cells, exactly two `<th>PSO1</th>` and no PSO2, 14 cells per row, empty cells blank; matrix cell >6 chars and missing outcome rejected; participated ≤ class size and feedback forms ≤ participated (checked one at a time), blank class size skips the rule; 3 visits in one submission kept separate (per-visit matrix edits), achievement as entered; 19b without averages prints no empty grid and no student names/roll numbers; shared workflow (submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only).
- Full regression: `python backend/manage.py test tests` → **Ran 179 tests, OK**. No shared engine/frontend code changed (only `base.html` CSS additions under new `.iv-*` classes and a seed mapping line).
- `python e2e/test_browser.py` → new KRA 19 test (2 visits: API draft → edit industry name in UI → Save → reload → preview shows it and "Visit 2 of 2" → export PDF → UI Submit → VC approves on the review page → export carries "Verified by VC" and the edited name). Run 1: 9 OK, 1 error in the existing KRA 32 test (timing, `select_option` timeout — the same flake recorded for KRAs 8–10); run 2 (exercising the KRA 19 reset path): **10/10 OK**.
- Frontend unchanged → no rebuild.
- Samples (`.work/renders/kra19/`): normal 4 pages (sparse matrix), multi (3 visits) 12, long (2 visits, 20 matrix rows, long text) 18, empty 3, Nil 1. Visual review: header table and nested experts table widths fixed; department cards break between rows without gaps; matrix header "Program Outcomes (POs)" over 1–12, PSO1, PSO1 with the no-scale note; long matrix repeats its header across pages; 19b block kept together; verification label in summary, footer and closing box; only Tinos embedded.

# KRAs 18, 17, 13 validation (2026-10-17)

- Pre-check: KRA 19 committed (2fbd120); KRA 18 was not implemented before this batch (built new).
- Focused: `test_kra18` **11 OK** (required MoU/activity fields, MoU without activities saves but fails submission, "Other" type conditional incl. leftover text rejected, mapping idempotent, 2 MoUs × 2 activities exact round trip and each activity printed with its own MoU, source examples not prefilled, unanswered evidence prints —); `test_kra17` **9 OK** (required vs optional MoU columns, mapping, one table with all 15 source headings, auto academic year, source sample text rejected as a type); `test_kra13` **10 OK** (25 required / 12 optional fields, "Other" type, tenure order, continuing tenure, meeting row cells, optional meetings, mapping, memberships keep their own contributions/meetings, unticked objectives and unadded contribution rows not printed). Each also runs the shared workflow (submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only).
- Full regression: first run **209 tests, 2 failures + 10 errors** in `test_kra1_3` — the new `kra13_payload` fixture had replaced the KRA 1–3 fixture of the same name; renamed to `kra13iab_payload`; rerun **Ran 209 tests, OK**.
- Shared-change check: all other KRAs' samples re-rendered; 57/59 HTML bodies identical; the 2 KRA 10 files differed only by CSS additions and a `keep` class from the already-committed KRA 8–10 template (the old sample predated that commit) — no output change from this batch.
- `python e2e/test_browser.py` → **11/11 OK**, incl. the new test: KRAs 18/17/13 complete draft via API → field edited in the form (MoU partner, centre name in a card row, committee name) → Save → reload → preview shows the value and a multi-record marker → export PDF 200.
- Frontend unchanged → no rebuild.
- Samples: `.work/renders/kra18/` normal 3, multi (2 MoUs × 2) 9, long (3 × 4, long text) 36, empty 2, Nil 1; `kra17/` normal 1, long (25 rows) 25, empty 1, Nil 1; `kra13/` normal 3, multi (3 members) 9, long (2 members × 20 contributions/meetings, long text) 67, empty 3, Nil 1. Visual review: KIET header on every page, source section order and headings, Particular/Details tables, MoU/membership tags, sign-off box kept together, "Pending approval" in summary/footer/closing box, only Tinos fonts. Fixed during review: KRA 18 page-1 gap (details table no longer forced together); KRA 13 orphaned "5. Meetings Attended" heading (headings kept with the next block; no page ends on a numbered heading); KRA 17 widths rebalanced toward the long-text columns. Known: long rows break only at row boundaries (KRA 17 stress rows 1 per page, as KRA 20).

# KRAs 15, 22, 31, 38 validation (2026-10-17)

- Pre-check: KRAs 18, 17, 13 committed (61840c6), working tree clean.
- Focused (each also runs the shared workflow: submit → reject after close with 72 h grant → resubmit → approve; Nil; PDF Tinos-only): `test_kra15` **9 OK** (required/optional columns, registration not required, faculty rows: programme/batch not applicable and leftover values rejected, alumni batch required, mapping + shared renderer, one table with all source headings, NA cells, no percentages); `test_kra22` **9 OK** (required columns, malformed count blocks draft, range at submission, free-text type, mapping, one table, round trip, dates formatted, no totals); `test_kra31` **9 OK** (required vs optional, teams ≤ participants at submission only, level/type limited to the source/workbook values, mapping, one table, example IDs absent); `test_kra38` **9 OK** (required columns, end ≥ start and duration 1–365 at submission only, duration not derived from dates, mapping, KRA 37 still on `kra37`, portrait table, no added year column).
- Full regression: `python backend/manage.py test tests` → **Ran 245 tests, OK**. Shared code unchanged (only a new template file `records_sheet_v1.html`); frontend unchanged → no rebuild.
- `python e2e/test_browser.py` → **12/12 OK**, incl. the new table-batch test (each KRA: complete draft via API → card cell of row 2 edited in the form → Save → reload → preview shows the value, the title and exactly one table → export PDF 200).
- Samples (`.work/renders/kraNN/`): KRA 15 normal 1 p, long (100 rows, long text) 18 p, empty 1, Nil 1; KRA 22 normal 1, long 34, empty 1, Nil 1; KRA 31 normal 1, long 34, empty 1, Nil 1; KRA 38 normal 1 (Letter portrait), long (100 rows) 11, empty 1, Nil 1. All Tinos-only, "Pending approval" present; table header repeats on every table page (checked per page). Visual fixes during review: KRA 15 "Year of Establishment" header overflow (column widened); KRA 22 and KRA 31 widths moved to the Outcome column (long samples 51 → 34 pages); KRA 31 "Academic/Participants/Institutions" header overflow fixed. Known: KRA 15 long sample's last page holds only the closing verification box because the table exactly filled page 17 (shared page-break behaviour, not changed in this batch); long rows break only at row boundaries.

# KRAs 4, 5, 6 and 24 validation (2026-10-17)

- Pre-check: KRAs 15, 22, 31, 38 committed (92508f7), working tree clean.
- Focused: `test_kra4_6` **28 OK** (per KRA: required programme/component/completion fields, component fields and student rows kept but ignored when "No" and re-validated when switched back, completion ≥ start, mapping idempotent with the family template, all 7 source headings, NA for a "No" programme, completion tables per programme, no percentages; plus the shared workflow; separation: three submissions, targets and achievements kept apart, nothing copied). `test_kra24` **10 OK** (placement vs higher-education required fields, category switch keeps values in storage but excludes them from validation and preview, invalid inactive package ignored and re-validated when active, packages stored exactly, mapping, no percentages; shared workflow).
- Full regression: `python backend/manage.py test tests` → **Ran 283 tests, OK** (shared change: `keep_inactive` opt-in in `schema.py`).
- Frontend: `types.ts` + `ConditionalCell` change (opt-in only); `npm run build` (tsc + vite) OK.
- `python e2e/test_browser.py` → **13/13 OK**, incl. the new test (KRAs 4–6: programme name edited → Save → reload → preview shows it and the KRA's component → export; KRA 24: category switched to Higher Education in the form → field shows "NA (entered value kept, not used)" → institution/programme typed → Save → reload → stored employer unchanged, preview shows the institution and not the employer → switching back shows the employer again → export). The existing KRA 32 test still confirms its payment fields are cleared (default behaviour unchanged).
- Samples (`.work/renders/kraN/`): KRAs 4/5/6 normal 1 p, long (4 programmes, one "No", 60 students each, long text) 14 p, empty 1, Nil 1; KRA 24 normal 1, long (100 records) 9, empty 1, Nil 1. Tinos-only, "Pending approval" on every page; completion/placement table headers repeat on every table page. Visual fixes: per-programme headings kept with their table; KRA 24 first column widened (normal sample had spilled the closing verification box to page 2).

# KRAs 12, 25, 26 validation (2026-10-17)

- Pre-check: KRAs 4–6 and 24 committed (6c9dd60), working tree clean.
- Focused: `test_kra12` **10 OK** (required award fields, optional coordinator/date/level, ≥1 award, shared award = one record with all recipients, blank level prints "Not applicable", signature labels stay blank with the server verification label, category limited to the workbook recipients, mapping; shared workflow). `test_kra25_26` **19 OK** (per KRA: required columns, team award one row with 4 names and the event once, achievement as entered, all 7 source headings, level wording incl. "University (inter-university)", unknown level rejected, mapping with the shared template; shared workflow; separation: two submissions, records/achievements kept apart, targets 9 vs 10).
- Full regression: `python backend/manage.py test tests` → **Ran 312 tests, OK**. Shared change: CSS only (`.awd-*`); frontend unchanged → no rebuild.
- `python e2e/test_browser.py` → **14/14 OK**, incl. the new awards test (KRA 12 award title edited in its card; KRAs 25/26 a team award's member list replaced with two names — saved, reloaded, preview shows the member and still exactly 2 table rows, export PDF 200).
- Samples (`.work/renders/kraN/`): KRA 12 normal (3 awards) 2 p, long (12 awards, long text) 13 p, empty 1, Nil 1; KRAs 25/26 normal (6 awards) 1 p, long (60 awards, 11-member teams) 16 p, empty 1, Nil 1. Tinos-only; "Pending approval" on every page; headers repeat on every table page. Visual fixes: award headings bold/left; sign-off lines shortened to fit four columns.

# KRAs 27–30 validation (2026-10-17)

- Pre-check: KRAs 12, 25, 26 committed (11a519c), working tree clean.
- Focused: `test_kra27_30` **42 OK** (per KRA: 16 common + KRA-specific required fields, 7 optional; date order and negative counts only at submission; category outside the workbook pair rejected; another KRA's specific field rejected as unknown; 3 events in one submission round-trip; empty event prints "Not entered" with no prefilled claims; mapping with the family template; shared workflow; KRA 30 target text shown as assigned; separation of the four submissions, achievements and targets).
- Full regression: `python backend/manage.py test tests` → **Ran 354 tests, OK**. Shared change: CSS selector extended (`.evt .k11-label`); frontend unchanged → no rebuild.
- `python e2e/test_browser.py` → **15/15 OK**, incl. the new events test (for each KRA: two events stored, the second event's KRA-specific field edited in the Event 2 tab → Save → reload → preview shows the value and "Event 2 of 2" → export PDF 200).
- Samples (`.work/renders/kraN/`, each KRA): normal 2 p, multi (3 events) 6 p, long (4 events, long text) 9 p, empty 2 p, Nil 1 p. Tinos-only; "Pending approval" on every page; no page ends on a numbered heading; each event starts a new page with "Event k of n"; "Portal report format" line under each title.

# KRAs 43, 44, 45 validation (2026-10-17)

- Pre-check: KRAs 27–30 committed (8ea5527), working tree clean.
- Focused: `test_kra43` **9 OK** (required/optional fields; published ≤ accepted and KIET ≤ totals only at submission; 10% KIET share accepted — no 20% rule enforced; Verified requires a reference, Claimed prints as entered and "Verified in Scopus" never appears unless chosen; no percentage; mapping incl. the "20% papers" target text; shared workflow). `test_kra44` **9 OK** (required/optional fields; participated ≤ registered, sessions ≥ 1, date order; source introduction/phase/objective text never printed unless entered, blank phases "Not described"; 3 activities round trip; mapping; shared workflow). `test_kra45` **10 OK** (required fields incl. resource-person name/institution; regional level accepted, unknown SDG rejected, date order; no "MBU", neutral follow-up label, no embedded images, enclosure rows listed; 3 events with their own resource persons; mapping; checklist-key safety across all templates; shared workflow).
- Full regression: `python backend/manage.py test tests` → **Ran 382 tests, OK**. Shared change: CSS only (`.evt .phase`, `.rp-table`); frontend unchanged → no rebuild.
- `python e2e/test_browser.py`: first full run 14/16 — KRA 32 `select_option` timeout (known timing flake, passed when rerun) and the new KRA 43–45 test, which exposed a real bug: KRA 45's draft save returned 400 because the checklist item "Participant's" (ASCII apostrophe) is altered by the form library's field-path parsing. Fixed with the source's typographic apostrophe + a schema-wide test; the dev demo's only KRA 45 draft (synthetic, created by that test run) was deleted so the corrected v1 could be seeded — the seed had correctly refused to change an in-use version. Rerun: **16/16 OK** (new test: event 2's conference name / theme / event name edited → Save → reload → preview → export; KRA 43 switched to "Verified in Scopus" → validate requires the reference).
- Samples (`.work/renders/kraN/`): KRA 43 normal 2 p, multi (3) 6, long (4, long text) 8, empty 2, Nil 1; KRA 44 normal 3 (as source), multi 9, long 16, empty 3, Nil 1; KRA 45 normal 2, multi 6, long (12 resource persons, long text) 9, empty 2, Nil 1. Tinos-only; "Pending approval" on every page; no page ends on a section heading; resource-person header repeats. Visual fixes: KRA 45 resource-person headers split mid-word (columns rebalanced, 9.5 pt), closing verification box alone on page 3 (note shortened, sign lines tightened); KRA 44 phase headings kept with their text.

# KRAs 21 and 39 validation (2026-10-17)

- Pre-check: KRAs 43–45 committed (8ce4b52) with their scoped checks recorded above; working tree clean.
- Focused: `test_kra21` **9 OK** (required/optional fields; attended ≤ enrolled and date order only at submission; a 2-hour programme is accepted — no minimum; qualifier table omitted when empty, rows complete when present, labelled supporting information, achievement as entered; mapping; shared workflow). `test_kra39` **9 OK** (required/optional fields incl. receipt rows; sanctioned/receipt/utilized amounts stored exactly ("1500000.00", "500000.50", "250000", "320000.75"); receipts never totalled; no lakh conversion; 3 decimals rejected only at submission; "15 lakh" rejected as malformed; grant without receipts allowed and printed as such; target text unchanged and shown; mapping; shared workflow).
- Full regression: `python backend/manage.py test tests` → **Ran 400 tests, OK**. No shared code/CSS change; frontend unchanged → no rebuild.
- `python e2e/test_browser.py` → new KRA 21/39 test passes (programme title edited; qualifier table shown as supporting information; receipt amount edited and stored exactly as typed; exports 200). The full run exposed intermittent failures in the KRA 43–45 test, reproduced with a probe at the test viewport: after a reload the workspace re-renders when evidence/preview finish loading and resets the selected event tab, so a tab clicked too early is lost. The tests now wait for network idle after reload before selecting a tab (also applied to the KRA 27–30 test); 3/3 isolated reruns OK, full suite **17/17 OK**. The reset itself is existing workspace behaviour (noted, not changed in this batch).
- Samples (`.work/renders/kraN/`): KRA 21 normal 2 p, multi (3 programmes, 4 qualifiers each) 6, long (3, long lists, 40 qualifiers) 12, empty 2, Nil 1; KRA 39 normal 2, multi (3 grants) 4, long (4 grants, 20 receipts, long text) 8, empty 2, Nil 1. Tinos-only; "Pending approval" on every page; no page holding only the closing box; "Adapted report format" line under each title; KRA 39 unit note under the summary.

# Bug fix: event-tab reset after workspace load (2026-10-17)

- Reproduced before editing: a probe counted the requests on reload (`GET /submissions/<id>/` ×2, template ×2, evidence ×4 — the StrictMode double effect plus a remount); with the duplicate detail request delayed by 1.5 s in the page, selecting Event 2 and typing before it resolved ended with Event 1 selected and the typed value gone. The new browser test failed on the old code ("Event 2" `aria-selected` was `false`).
- Cause: `SubmissionLoader` (`frontend/src/features/report-builder/Workspace.tsx`) increments `n` on every completed load and renders `<div key={state.n}>`, so each load remounts the editor (new `useForm` defaults from the server copy, `open` tab back to 0). The double-run load effect produced a second, unrequested remount after the user had started working. React Hook Form resets and autosave responses were not involved (autosave updates the SaveQueue only).
- Fix: `SubmissionLoader` and `WorkspaceRoute` abort their requests in the effect cleanup and ignore aborted results; `SubmissionLoader` is keyed by submission id. Explicit `reload()` keeps its intended remount. `SchemaForm` unchanged: removing the selected event still selects Event 1 (removal is only offered when more than one event exists).
- Results: new test `test_workspace_keeps_event_selection_and_input_across_loads` (delayed duplicate load → Event 2 stays selected and typed value kept; autosave "Saved" → still selected, value stored on the server; remove Event 2 → Event 1 selected with its data; in-app switch to KRA 28 → KRA 28 fields only, no KRA 27 value) passes 3/3 isolated; `tsc -b` + `npm run build` OK; full `python e2e/test_browser.py` **18/18 OK**; `python backend/manage.py test tests` **400 OK** (no backend change).

# KRAs 14, 16, 34, 35 validation (2026-10-17)

- Pre-check: tab-reset fix already committed (6b34e82); working tree clean.
- Focused: `test_kra14` **8 OK** (required/optional fields incl. team rows; ≥1 student at submission, draft without students saves; 3 registrations round trip with their own teams; mapping, target shown; shared workflow). `test_kra16` **8 OK** (required/optional fields incl. contribution rows; optional certificate/training date/contributions; category limited; 3 ambassadors round trip; mapping; shared workflow). `test_kra34_35` **18 OK** (per KRA: required fields, payments optional but complete per row; amounts stored exactly ("3000.50", "2000", "1499.99"), each below Rs. 5,000 and accepted, never totalled; 3 decimals rejected only at submission; "Rs 500" rejected as malformed; mapping with the family template; shared workflow; 34 end ≥ start; 35 life membership without end date, valid-to ≥ valid-from).
- Full regression: `python backend/manage.py test tests` → **Ran 434 tests, OK** (shared change: `.verify` CSS only; frontend unchanged → no rebuild).
- `python e2e/test_browser.py` → **19/19 OK**, incl. the new test (14 team member name, 16 training, 34/35 payment amount edited → Save → reload → preview → stored exactly → export 200).
- Samples (`.work/renders/kraN/`): KRA 14 normal 2 p, multi (3) 4, long (4 × 20 students) 8, empty 1, Nil 1; KRA 16 normal 2, multi 4, long (3 × 20 contributions) 12, empty 2, Nil 1; KRA 34 normal 2, multi 5, long (4 × 15 payments) 8, empty 2, Nil 1; KRA 35 normal 2, multi 4, long 8, empty 2, Nil 1. Tinos-only; "Pending approval" on every page; "Project-created report format" line under each title. All 182 samples re-rendered after D-061: no page-count change; verification-only pages 2 → 1 (KRA 15 long remains).

# KRAs 40, 41, 42 validation and Phase 4 coverage (2026-10-17)

- Pre-check: KRAs 14/16/34/35 committed (41885d4), working tree clean.
- Focused: `test_kra40` **9 OK** (required/optional fields incl. findings ≥1 and action rows; action Ref must match a finding of the same audit — unmatched ref saved in draft, refused at submission; actions printed under their finding; follow-up of an earlier audit allowed without equity activities; status limited to Planned/Ongoing/Completed; empty report contains no "compliant/successfully/achieved"; mapping; shared workflow). `test_kra41_42` **16 OK** (per KRA: common + specific required fields, no category; options limited to workbook dimensions, ≥1 required; 4 activities round trip, one submission; mapping with the family template, target unchanged; shared workflow). `test_kra27_30` **42 OK** re-run after the family change; KRA 27–30 schemas byte-identical, sample HTML identical except one blank line in KRA 30.
- Full regression: `python backend/manage.py test tests` → **Ran 459 tests, OK** (shared changes: `ref_in` rule in `schema.py`, event family/template extension). Frontend unchanged → no rebuild.
- `python e2e/test_browser.py` → **21/21 OK**, incl. the new KRA 40/41/42 test (action progress and event details edited → Save → reload → preview → export; KRA 40 finding Ref changed to an unknown value → saved, validate refuses) and a new KRA 11/23 test (previously checked manually only).
- Samples (`.work/renders/kraN/`): KRA 40 normal 2 p, multi (2 audits × 3 findings) 4, long (2 × 12 findings, long text) 27, empty 2, Nil 1; KRAs 41/42 normal 2, multi 6, long 9, empty 2, Nil 1. Tinos-only; "Pending approval" on every page; project-created/portal-format line under each title; KRA 40 long: each long finding block kept whole (one per page).
- **Coverage reconciliation** (dev catalogue, script over all assignments): 45 KRAs; 45 template versions kra1…kra45, no duplicate keys; 585/585 assignments mapped (0 without a template, 13 per KRA); renderer loads for all 45; empty draft validates for all 45; normal + Nil samples exist for all 45; KRA-specific automated test class for 44 KRAs + KRA 33 pilot suite (`test_workflow.py`, 27 tests); automated browser smoke for all 45.
- **Phase 4 exit checks** (plan §Phase 4): families/new templates added ✅; every mapping and evidence checklist verified ✅; every output validated independently ✅; a synthetic sample PDF per KRA with visual results recorded per batch ✅, never seeded into production ✅ (`.work/` git-ignored, seed loads no fixtures); "45 working template mappings, no placeholder forms" ✅; "no unreviewed report exports" ❌ — not met: no format has institutional acceptance yet. Skipped: none of the automated checks; manual institutional review is outstanding.

# Phase 5A validation (2026-10-17)

- Pre-check: Phase 4 committed (d14b72e); 45/45 KRA mappings verified in D-064, no failing integration checks; the institutional-review gate remains open (not claimed).
- `python backend/manage.py test tests.test_phase5a` → **7 OK**: (1) Dean and anonymous refused on all 10 admin method/paths, nothing changed; (2) copy 2026-27 → 2027-28 creates 585 drafts with identical target text/template and source link (percentages and "NIL" kept as text), a repeat creates 0 with 585 conflicts, 2026-27 source rows unchanged, copying into the running year (409) or from a later year (400) refused; (3) draft target edited to an arbitrary string and returned exactly, blank refused, stale finalize (584 ≠ 585) refused with nothing created, finalize creates 585 unique assignments with the edited text, a second finalize returns `nothing_pending`, PATCH/DELETE of a finalized draft → 409, model refuses a changed target, new draft for a finalized pair → 409, audit events present; (4) a pre-existing assignment aborts finalization and rolls back every row; (5) KRA creation refuses an unknown template, a missing confirmation and a broken template (missing layout), creates KRA 46 with "KRA 46:" text and default template, refuses a duplicate number, a draft for KRA 46 inherits the template, `admin/templates/` flags the broken one; (6) Deans see no 2027-28 assignments until finalization, then exactly their 45; the VC reads all 585 2026-27 rows; (7) an existing 2026-27 submission workflow opens unchanged after 2027-28 finalization.
- Full regression: `python backend/manage.py test tests` → **Ran 466 tests, OK** (migration `catalogue.0002_phase5a_drafts`).
- Frontend: new VC screens (Assignments, KRAs) and nav links; `tsc -b` + `npm run build` OK.
- `python e2e/test_browser.py` → **22/22 OK**, incl. the new Phase 5A test (Dean gets 403 from the admin API and is redirected away from `/vc/assignments`; VC copies 2026-27 into 2027-28 drafts in the UI, edits an ECE target, which survives reload exactly; a repeat copy creates 0; VC adds an ECE draft for 2028-29, opens the review summary, confirms finalization; the finalized row becomes read-only, PATCH returns 409 `finalized`; the Dean then sees the new 2028-29 assignment with the exact target). Run twice in a row: the second run exposed a UI race (the new-draft KRA list was offered before that year's drafts/finalized rows loaded, so an already-finalized KRA could be chosen and the add was refused) — fixed by showing the form only after both lists load; two further consecutive runs OK.
- Dev data note: each browser-test run finalizes one more ECE KRA for 2028-29 and the dev 2027-28 year now holds 585 drafts (synthetic dev database only).

# Phase 5A follow-up validation (2026-10-17)

- Locking (`tests.test_phase5a`, now **11 OK**): a newly created KRA's draft for 2026-27 (current year) finalizes, the CSE Dean sees it at once and ECE does not; a draft for an existing 2026-27 pair → 409 and the existing target is unchanged; the new assignment cannot start a report in closed P1 (409 `window_closed`, no submission created; Dean is offered the normal reopening path) while open P2 works; with the clock at 1 Sep 2027 the ended 2026-27 refuses drafts/finalize (409 `year_locked`) and 2027-28 drafts stay editable, at 1 Sep 2028 they are refused; next-year copy from the current year still creates drafts. Earlier 5A tests updated for the corrected rule (copy into the running year from itself → 400 "earlier year").
- Cleanup (`tests.test_cleanup_e2e`, **4 OK**) on an isolated fixture built through the API (demo VC copy batch, a marked edit, a marked finalized assignment; look-alikes by a real VC with and without the marker, a real-VC edit of a copied draft, an unmarked demo draft): dry run reports removable 2 / unconfirmed batch 583 / ambiguous 3 and changes nothing; `--execute` removes exactly the 2 drafts + 1 assignment, keeps every look-alike, KRAs, users, 2026-27 assignments, submissions and audit history, records `cleanup.e2e`; a second execution removes nothing; `--copy-event` removes the confirmed batch but keeps the real-VC edit and a finalized assignment that has a report; refused without DEBUG.
- Working database: `cleanup_e2e_data` dry run only (no `--execute`): removable 5 (1 marked 2027-28 draft, 4 marked 2028-29 ECE drafts with their 4 finalized assignments, no reports), unconfirmed copy batch 584 drafts (audit event 2089), ambiguous 0. Nothing deleted.
- Full regression: `python backend/manage.py test tests` → **Ran 474 tests, OK**. Frontend (year labels/notes) `npm run build` OK.
- Browser: `python e2e/test_browser.py` now refuses to run directly. First isolated run: 1 failure + 21 errors (CSRF: the isolated Django trusted only :5173) — fixed by setting the runner's trusted origin; second run 21/22, the Phase 5A test selected the year before the Assignments page had replaced the dashboard (hidden in the old dev database where 2027-28 was already the default) — the test now waits for the page heading; then `python e2e/run_isolated.py` → **22/22 OK**. Working-database fingerprint (md5 of every row of all 24 tables) before vs after the isolated run: identical for all 24 tables across four isolated runs; afterwards no `_e2e` database, no `.work/e2e` and nothing listening on 8001/5174.

# Phase 5B validation (2026-10-17)

- `python backend/manage.py test tests.test_phase5b` → **9 OK** (fixture through the API at 1 Oct 2026: KRA 33 CSE Submitted, ECE untouched draft, IT Draft with HTML-like text, ME Nil + Approved, EEE Rejected then edited, all other assignments without submissions): statuses for all 13 KRA 33 rows (untouched draft and missing → Not submitted); IT achievement exact and flagged draft; ME Nil with Approved status; EEE shows the reviewed revision text, revision 1 and "changed since submission"; target text exact. Counts over 585 assignments sum correctly and do not change with the status filter; 24 pages of 25 Not-submitted rows give 581 distinct rows; combined department+KRA+status filter; ordering sorted. Filter validation (period of another year, unknown year/status/department, non-numeric KRA/period → 400). A VC draft for a new KRA 46 never appears; after finalization the new current-year assignment appears as Not submitted with its exact target. Review detail returns the revision's achievement and 3-item evidence manifest while the live draft differs; history keeps revision 1 with its REJECT decision. Export: anonymous and Dean refused (Dean also refused the progress API); 581 rows in the PDF HTML (beyond page one), counts and "rows in this report" present, A4 landscape, `private, no-store`, attachment; HTML-like text escaped exactly; submissions unchanged by export; renderer failure → 503 `pdf_unavailable`; > limit → 400 `too_many_rows`; real renderer: 54-page PDF for 585 rows with the table header on every page.
- First version used `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` for the export snapshot; PostgreSQL rejects it after the first query of a transaction (tests, and any request-wide transaction), so the dataset was rewritten as one SQL statement, which is snapshot-consistent by itself.
- Full regression: `python backend/manage.py test tests` → **Ran 483 tests, OK**.
- Frontend: progress page (achievement source labels, Export PDF with busy/error state, review links keeping filters), review page (revision-based achievement/evidence, back link); `tsc -b` + `npm run build` OK.
- Browser (isolated runner only): new Phase 5B test — Dean saves an ECE draft achievement; Dean gets 403 from progress and export; VC filters ECE + Draft, sees "Unsubmitted draft", opens View & history (achievement tab says unreviewed draft), "← Progress" returns to the identical filtered URL; clearing the status filter shows 45 rows; Export PDF downloads `KRA_progress_2026-27_P…pdf` containing the draft text, "rows in this report: 45" and the draft marker. It exposed a pre-existing bug (choosing "All …" did not clear a progress filter) — fixed. `python e2e/run_isolated.py` → **23/23 OK**.
- Visual check: `.work/renders/progress/sample.pdf` (synthetic test data, 54 pages) — KIET header and table header on every page, filters/counts block on page 1, wrapped KRA text, footer with generation time and page N | M; only Tinos fonts.

# Phase 6A validation (2026-10-17) — permissions and workflow integrity

Coverage checklist (existing tests reused; new ones in `backend/tests/test_phase6a.py`):

| Area | Existing coverage | Added in 6A |
|---|---|---|
| Login roles, CSRF, inactive users, throttling, password change | `test_auth_and_isolation` | — |
| Cross-department IDs (submission, draft, preview, export, submit, evidence list/add/delete/download, history, reopen, assignment) | `test_auth_and_isolation` | foreign revision via own submission (preview, export), period of another year, foreign assignment reopen request, reopen-request lists |
| Anonymous / role on every route | partial (per feature) | sweep over every route in `config/urls.py` (39 route-method pairs anonymous; all 11 VC-only routes for a Dean; 9 Dean-only actions for the VC) |
| Private evidence exposure | download headers (`test_workflow`) | no URL other than the guarded download serves a stored key (`/`, `/media/`, `/static/`, `/private/`, `/.work/private/`); storage key never in API output |
| Calendar (IST) | period edges, leap year, draft creation edges, C1 grant 71/72 h | submit at exact close / 1 µs before; request grant exactly 72 h from decision; grant scope (other period, other KRA, other department) |
| Transitions | reject reason, stale revision, return keeps history, C1/C2 | full matrix incl. double approve, approve after return, blank reason |
| Locked content / stale tabs | version conflict, submit lock | save, submit, evidence add/remove refused after submission and after approval; revision unchanged |
| Historical PDFs | label logic | rejected rev 1 PDF says "Historical revision 1: not approved" with rev-1 text after rev 2 is approved |
| Concurrency | none with real parallel requests | `ConcurrencyTests` (TransactionTestCase): each request in its own thread and DB connection; the test holds the contended row lock until all requests are waiting (`pg_stat_activity`), then releases |

Confirmed defects and fixes (D-069):
1. A reopening request for a period that had not started was accepted (201) and created a Submission row; approval would have granted 72 h of editing before the period opened. Fixed in `services.request_reopen` (`now < closes_at` → 409 `period_open`, row creation rolled back). Regression: `test_reopen_request_refused_for_a_period_that_has_not_started`.
2. `GET submissions/<id>/export/` had no `Cache-Control`; now `private, no-store`. Regression: `test_report_export_is_not_cacheable`.
3. VC progress page (and Dean dashboard/period list) had no stale-response guard: the isolated browser run failed deterministically in the Phase 5B test — after "← Progress", React's development double effect sent two `status=DRAFT` requests; the test then chose "All statuses", and the second Draft response arrived after the 45-row response and overwrote it (traced with request/stack logging; the URL had cleared correctly). Real-user effect: quick filter/period changes could show the previous filter's rows. Fixed with a cancel-on-cleanup guard in `VCDashboard.tsx` and `DeanDashboard.tsx` (`usePeriods`, assignments). Regression: the existing browser test (now passes).
4. Backend tests stored uploaded evidence and generated PDFs in the working `.work/private`. `PortalTestCase` (and the concurrency tests) now use a temporary folder removed at exit. Existing residue was **not** cleaned.

Concurrency results (no defects; existing locks sufficient): 3 simultaneous submits → one 200, two 409, one revision, one audit event; autosave vs submit → exactly one succeeds and the other gets `not_editable` or `version_conflict` (submitted text never changed afterwards; a stale-version submit never submits unseen text); upload + removal + submit → the revision manifest equals the active evidence exactly, late changes get 409; approve vs reject from two VC tabs → one decision, one audit event, status matches; two reopen decisions → one grant; two first-time C2 requests → one row, one request. The class passed 5 consecutive runs. Which waiter wins is decided by PostgreSQL's lock queue; both outcomes are asserted.

Commands and results:
- `python scripts/devdb.py start` (local dev PostgreSQL was stopped); all tests use Django's separate test database; the working database was not used.
- `python backend/manage.py test tests.test_phase6a tests.test_workflow` → **Ran 44 tests, OK**; `tests.test_phase6a.ConcurrencyTests` ×5 → **5 OK each**.
- Full regression: `python backend/manage.py test tests` → **Ran 500 tests, OK** (renderer running; 0 skipped).
- Browser (isolated runner only): `python e2e/run_isolated.py` → **Ran 23 tests, OK** (first run: 22 OK + 1 failure in the Phase 5B test → defect 3 above, fixed; reruns of that test alone failed 3/3 before the fix).
- Frontend: `npx tsc -b` + `npm run build` OK.
- The PDF renderer was started locally for the full run (`python renderer/server.py`); without it the same suite gave 500 tests OK with 48 renderer tests skipped.

Limitations: concurrency is exercised in-process through Django's test client (threads, separate PostgreSQL connections), not through Gunicorn/HTTP under load; measured load testing is later Phase 6 work. Automated checks are not college acceptance; policy questions are listed in `docs/progress.md`.

# Phase 6B validation (2026-10-17) — performance and failure recovery

**Environment (local only; not production capacity):** Windows 11 (10.0.26200), 20 logical CPUs, 15.7 GB RAM, Python 3.11.9, PostgreSQL 16.2 (dev cluster), Django `runserver --noreload` (threaded, `DJANGO_DEBUG=1`, needed for seeded demo accounts and plain-HTTP cookies). Gunicorn does not run on Windows and WSL is not installed, so the planned app server was **not** measured. Renderer `renderer/server.py`: pool 2, queue 4, job timeout 40 s; Django renderer timeout 45 s.

**Command:** `python e2e/run_perf.py --seconds 30` (results in `.work/perf-results.json`). It recreates `<working db>_perf`, migrates, seeds the catalogue, demo accounts and `e2e/perf_seed.py`, runs its own Django (:8002) and renderer (:8791) with evidence under `.work/perf/private`, then stops them, drops the database and removes `.work/perf`. The working database and uploads are never used.

**Dataset (synthetic):** 13 departments × 45 KRAs = 585 assignments; 6 reporting periods (P1 closed, P2 open; P3–P6 not yet open, so empty); 997 submissions, 704 revisions, 469 decisions, 1,408 Drive-link evidence rows; 13 Deans (one per department) + 1 VC; a long KRA 33 report (3 events × 40 rows, long text) and a wide KRA 31 table (80 rows × 14 columns).

**PDF results (final run):**

| Check | Result |
|---|---|
| Normal report / long KRA 33 / wide KRA 31 / progress (585 rows) | 200, valid PDF; 1 / 21 / 27 / 56 pages; 0.8 / 1.0 / 1.0 / 1.4 s on first render; `application/pdf`, `private, no-store`; repeat of a cached report 0.13 s |
| Anonymous progress export | 401 |
| Burst: 12 simultaneous distinct progress exports | renderer peak 2 active + 4 queued; 6 × 200 (all valid PDFs, 0.4–1.1 s), 6 × 503 `pdf_busy` (0.1 s): bounded, no hang |
| Renderer job timeout (renderer restarted with a 1 s limit, 585-row export) | 502 `pdf_failed` in 1.1 s; next small export 200 valid |
| Renderer stopped | progress export 503 `pdf_unavailable` in 2.1 s (Windows connection-refused delay); cached report still served; after renderer restart 200 without restarting Django |
| Chromium processes killed inside a running renderer | before fix: 2 failures (one per worker), then recovery; after fix: 4/4 exports 200, with two "relaunching" log lines |
| Submission/revision/decision/evidence fingerprints before vs after all PDF stages | identical |
| Chromium processes / RSS (renderer tree) | 9–10 processes throughout; about 0.50 → 0.67 GB across restarts and crash recovery |

**Mixed workload (final run; 30 s per stage; Deans: dashboard, report read, save, preview; VC: progress with random filters, review read, and every 6th loop a progress PDF / report PDF):**

| Users (Deans+VC) | Requests | Throughput | 5xx | Dean dashboard p50/p95 ms | Dean save p50/p95 | Dean preview p50/p95 | VC progress p50/p95 | Progress PDF p50/p95 | Report PDF p50/p95 |
|---|---|---|---|---|---|---|---|---|---|
| 4+1 | 2,319 | 78 req/s | 0 | 52 / 68 | 51 / 65 | 49 / 63 | 50 / 68 | 442 (n=1) | 477 (n=1) |
| 8+2 | 2,954 | 100 req/s | 0 | 88 / 118 | 81 / 106 | 69 / 92 | 83 / 111 | 493 / 531 | 510 / 653 |
| 13+2 | 2,765 | 94 req/s | 0 | 173 / 223 | 143 / 182 | 112 / 147 | 137 / 197 | 598 / 673 | 705 / 848 |

Machine CPU stayed at about 27–37%. Throughput flattens at 10–15 users. The likely cause is the single Django development-server process (one Python interpreter), but this was **not profiled — unconfirmed**; PostgreSQL and the renderer were not shown to be saturated either. The first run (before the renderer fix) had the same shape and 0 errors.

**Query counts:** `tests.test_phase6b.QueryCountTests`. Before the fix the VC assignments dashboard went from 9 queries (10 submissions) to 36 (100 submissions); now the VC/Dean assignments and VC progress counts are constant. Submission detail uses a fixed small number (≤ 6 periods).

**Failure recovery:**
- Backend (`tests/test_phase6b.py`): a renderer 200 with an HTML error page, empty or truncated body → 502 `pdf_failed`, nothing cached, submissions/evidence unchanged, recovery once healthy; mid-body disconnect → 502; reset/timeout → 503; the progress export refuses non-PDF; a failed evidence DB write → 500, not listed, no new file and no `.part` file; logs captured during failures contain no report text or test password.
- Browser (`test_phase6b_failed_autosave_and_upload_recover`, isolated runner): draft PATCH forced to 500 → "Save failed — will retry on next change", typed value kept; after recovery the next change saves both edits and a reload shows them; an upload aborted at the network → "Cannot reach the server…" alert, item not listed, API shows no row.
- Retries: duplicate submits and stale saves are covered by Phase 6A (one revision, 409s, no overwrite).
- Log scan of the perf run (8,346 lines, Django + renderer): 0 report-text marker hits, 0 password hits, 0 tracebacks (before the renderer fix: 2 tracebacks, the crash failures).

**Confirmed defects fixed (D-070):** non-PDF/truncated renderer reply returned and cached as a PDF; IncompleteRead → unhandled 500; orphan evidence file after a failed upload; assignments dashboard N+1; one failed job per renderer worker after a Chromium crash.

**Regression runs:** focused `tests.test_phase6b tests.test_workflow tests.test_phase3 tests.test_phase5b tests.test_reports tests.test_phase6a` → 91 OK (7 renderer tests skipped, renderer down at that point); full `python backend/manage.py test tests` with the renderer running → **Ran 506 tests, OK** (0 skipped); `python e2e/run_isolated.py` → **Ran 24 tests, OK**. Frontend code unchanged in 6B (build not rerun).

**Limitations / not measured:** Gunicorn workers, Nginx, TLS, Linux; DEBUG=0; file uploads under load (only the failure path); long-uptime Chromium memory; client–server network latency; more than 15 concurrent users (capped to protect this machine). These local numbers are not service-level guarantees.

# Phase 6C validation (2026-10-17) — usability, accessibility and documentation

**Method:** a scripted Playwright audit (temporary, on the isolated runner; synthetic demo accounts, disposable `<db>_e2e` database, evidence under `.work/e2e/private`) visited Dean login/dashboard, the workspace (Report/Evidence/Achievement tabs, a submit attempt) for KRAs 33, 32, 9, 4 and 20, and VC progress, review, reopening requests, assignments and KRAs, at 1280×900, 375×812 (phone) and 640×450 (= 1280 px at 200% zoom). Per page it counted visible controls without an accessible name, page-wide horizontal overflow (wide tables inside their own scroll region excluded), tabs without a controlled panel, non-tab children of tablists, positive tabindex, invalid fields without a description, and walked 25–30 Tab presses checking each focused element for a visible outline/ring. Plus code review of shared components (SchemaForm, Workspace, ReviewPage, EvidenceTab, ui.tsx). No automated contrast/axe tool is installed; colour pairs were checked by class (no `text-*-300/400` text on white is used). **This is not a full accessibility (WCAG) audit.**

**Findings → fixes (D-071):**

| Finding | Where | Fix |
|---|---|---|
| Tabs had `role=tab` but no `aria-controls`/tabpanel; no arrow-key operation; "+ Add" button and PDF link inside tablists | Workspace, review page, activity (event/programme) tabs | Shared `tabKeys` (Arrow/Home/End, roving tabindex); tabpanels with `aria-labelledby`; non-tab buttons moved out of tablists |
| Table-mode cell inputs had no accessible name (an unassociated sr-only span) | SchemaForm tables (e.g. KRA 33 engagements) | `aria-label` "Column, row N" on each cell input/select |
| Required "*" on not-applicable fields; "*" read aloud as "star" | KRA 32 card labels; card/fieldset labels | Shared `Req` marker (visual "*", sr text), shown only while the field applies; grid headers say "(required where applicable)" |
| Inactive activity fields shown as normal editable inputs | KRA 9 (9a/9b variants), KRAs 4–6 (component = No) | Hidden while not applicable, with a note that earlier values are kept but not checked, submitted or printed; values stay in the draft (verified: saved payload keeps them, switching back shows them) |
| VC header overflowed by 55 px at 375 px (Sign out off-screen) | Shell header | Header nav wraps |
| Date inputs showed no focus ring | `.input` utility | `focus-within` ring |
| Colour-only error dot on tabs | Workspace Evidence tab, activity tabs | sr-only "(needs attention)" / "(has errors)" |
| Errors of checkbox/radio/ratings groups not associated | MultiSelect, Checklist, Ratings | `aria-describedby` to the error text |
| Mobile Form/Preview toggle state not exposed | Workspace | `aria-pressed` |
| Inline finalize panel marked `role=dialog` without dialog behaviour | VC assignments | `role=region` |

**Checked and acceptable as is:** login pages; dashboards (no unnamed controls, no overflow at 375 px or 200%); buttons and inputs have visible focus rings; save state uses one `role=status` region (polite, announced on state change only); upload/delete errors and submit-blocking summaries use `role=alert`; read-only, loading, empty and closed-window states have explicit text; native `window.confirm` dialogs (remove row/event/evidence, submit, discard) are keyboard-accessible and return focus; wide tables scroll inside their own region.

**Regression:** new browser test `test_phase6c_tabs_names_markers_inactive_fields_and_phone_width` — arrow/Home keys on workspace tabs and panel association; "Alumni Name, row 1" accessible name; no unnamed controls, panel-less tabs or non-tab tablist children on the workspace; KRA 32 marker follows Equipment/Asset ↔ Financial; KRA 4 component answer Yes→No hides fields with the note, Save keeps `component_name` in the stored payload, back to Yes shows the value; VC dashboard at 375 px has no horizontal overflow and Sign out is on screen. Existing KRA 4–6 and KRA 8–10 browser tests (retention after switching/unticking) still pass.

**Commands:** `npx tsc -b` + `npm run build` (in `frontend/`) → OK; `python e2e/run_isolated.py -k phase6c` → 1 OK; full `python e2e/run_isolated.py` → **25 tests, OK (first full run: 23 OK + 2 failures where existing tests asserted pre-6C behaviour — the unticked KRA 9b input still visible, and the finalize panel as a dialog; both tests updated, the KRA 9 test now also proves the kept value returns when 9b is ticked again)**. Backend unchanged in 6C (backend suite not rerun; recorded 506 OK at 6B).

**Not covered / limitations:** screen-reader testing with NVDA/JAWS/VoiceOver; automated contrast measurement; 400% zoom/reflow at 320 px; the PDF documents themselves (tagged-PDF accessibility not attempted); the Phase 4 report layouts are unchanged.
