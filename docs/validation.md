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
