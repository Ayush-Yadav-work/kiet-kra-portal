# Validation log

All results below were actually run on 2026-10-16 on the development machine (Windows 11, Python 3.11, PostgreSQL 16.2
via `scripts/devdb.py`, Chromium 156 via Playwright 1.64). Local pilot only — no server, load or recovery testing yet.

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
