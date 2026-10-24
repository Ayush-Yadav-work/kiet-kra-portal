# KIET KRA Portal — full engineering, security, functional and UI/UX audit

Date: 2026-10-24 · Auditor: Claude (Claude Code) · Audit only: no application code, dependency or test was changed.

> **Update (2026-10-24, Batch A):** findings **H1, L1 and L2 are fixed** (D-080). H2 and the other findings remain open. See *Batch A results* at the end.

## 1. Executive verdict

**Functionally strong, operationally not production-ready.**

- **Functionally strong:** the application logic held up under everything exercised here.
  - All 45 KRA templates submitted, previewed and rendered to PDF, both as normal reports and as Nil reports.
  - The project invariants that were probed (department isolation, draft privacy, exact 72-hour reopening, idempotent submission and review, immutable history, server-derived Dean identity, Nil submission date) behaved as specified.
  - 561 backend and 33 browser regressions pass, and no known dependency vulnerabilities were reported.
- **Not production-ready:** the blockers are operational, not functional.
  - Login throttling uses a per-process memory cache.
  - There are no web, renderer or proxy deployment definitions.
  - There is no backup/restore procedure or restore drill.
  - Upload malware scanning is absent.
  - The 45 report formats have not been institutionally accepted.
- **No critical defects were found.** Two items rate High: the per-process throttle cache and the missing deployment/backup pieces. Both are production risks rather than code bugs.

This verdict covers only what was executed or inspected (sections 4–6). Passing tests do not establish production capacity, Linux compatibility or recovery readiness; none of those were tested.

## 2. Scope and baseline

| Item | Value |
|---|---|
| Branch / commit | `phase2-kra33-pilot` @ `a7302e8` (equal to `origin/phase2-kra33-pilot`) |
| Working tree at start | clean (no uncommitted application changes) |
| Environment | Windows 11, Python 3.11 venv, PostgreSQL 16 dev cluster (`scripts/devdb.py`, port 54329), Chromium renderer `renderer/server.py`, Vite dev server via `e2e/run_isolated.py` |
| Databases used | Django test DB (`test_<db>`) and the isolated browser DB (`<db>_e2e`, dropped after each run). **The working database was not used.** |
| Data | synthetic accounts and fixtures only; temporary media (`tests.base.TEST_STORAGE`, e2e media) |

The application is a Django 5.2 + DRF API (`/api/v1/…`, 60 routes) with a React/TS SPA and two roles:
- **Dean:** one active per department, enforced by a DB constraint.
- **VC:** one active college-wide, enforced by a DB constraint.

Reports are schema-driven, from 45 KRA template versions and 20 renderer templates. Main components:
- **Exports:** report PDFs (renderer), progress PDF, analytics PDF/CSV.
- **Background jobs:** the approved-PDF artifact worker (`run_artifact_worker`, leases, retries).
- **Deployment configuration:** only `infra/kiet-kra.env.example` and a systemd unit for the worker.

## 3. Coverage matrix (requirement → route → evidence)

Status meanings:
- **PASS**: executed in this audit and behaved as expected.
- **PASS (suite)**: covered by the existing regression suite, which passed in this audit.
- **FAIL**: executed and did not behave as required.
- **NOT VERIFIED**: not executed.
- **BLOCKED**: could not be executed with what was available.

| Area / invariant | Route(s) | Evidence | Status |
|---|---|---|---|
| Separate Dean/VC login, wrong-portal refusal | `auth/dean/login/`, `auth/vc/login/` | probe: Dean credentials on VC login → 400; browser `test_portals_reject_wrong_role`, `test_login_pages_*` | PASS |
| First-login password change gate | all APIs | probe: `must_change_password` user → 403 | PASS |
| Logout ends session; CSRF on mutations | `auth/logout/`, any PATCH | probe: `me` 200 → 401 after logout; PATCH without token → 403 | PASS |
| Session expiry (8 h cookie age) | — | settings inspection only | NOT VERIFIED (not executed) |
| One active VC / one active Dean per department | DB constraints | probe: second active VC and second CSE Dean → IntegrityError | PASS |
| Department isolation (direct IDs) | submissions, preview, export, history, draft, submit, evidence download/delete | probe: Dean B → 404 on all 8 | PASS |
| Role boundaries | progress, analytics, admin, announcements, bulk; draft/submit | probe: Dean → 403 on VC routes; VC → 403 on Dean writes | PASS |
| Draft privacy (lists, counts, APIs, preview, PDF, evidence, analytics, bulk, announcements) | many | `tests.test_draft_privacy` + updated VC suites | PASS (suite) |
| Post-rejection edits private until resubmission | detail/preview/export/evidence | `test_draft_privacy` | PASS (suite) |
| Completion = approved/expected; zero denominator N/A | `analytics/` | probe: future year → `completion: null`; `test_vc_analytics` | PASS |
| Finalised targets immutable; copy/bulk-edit/remove/restore/finalise | `admin/…` | `test_vc_assignments`, `test_phase5a`, browser `test_phase5a_vc_assignment_workflow` | PASS (suite) |
| Reopening 72 h, exact IST boundary, per KRA/period | `…/reopen-requests/`, decision | probe: grant = 72.0 h; editable/save 200 at expiry − 1 s; not editable/409 at expiry; another KRA same period → 409 | PASS |
| Reopen from an unstarted report | assignment-period reopen | probe: request created, approved | PASS |
| Duplicate submit / repeated approve / stale save | submit, review, draft | probe: 409 / 409 / 409; one revision only | PASS |
| Bulk approval: pages, exact versions, confirm, interruption, resume, conflicts | `bulk-approvals/…` | `test_vc_bulk` (incl. two concurrent tabs), browser phase-2 test | PASS (suite) |
| Approved-PDF worker: leases, retries, restart, failure visibility | worker | `test_vc_artifacts`, `test_vc_worker_process` | PASS (suite) |
| Announcements: draft, audience, publish, revise, unread, pin, expiry, withdraw, pending recipients | `announcements/…` | `test_vc_announcements`, browser phase-2 test | PASS (suite) |
| Evidence downloads separate from report PDFs | `evidence/<id>/download/` vs `…/export/` | code + suite | PASS |
| Dean identity server-derived, snapshotted; later profile change preserved | submit, preview, history | `test_term_and_dean`; probe sweep Nil PDFs show the snapshot name | PASS |
| Nil date = successful submission (IST), not save/approve/preview | Nil PDF | `test_term_and_dean` (IST boundary, resubmission, approval); sweep: 45/45 Nil PDFs show the name and "1 October 2026" | PASS |
| Year of study / semester / session distinguished; legacy values preserved | term fields | `test_term_and_dean` (mapping, programme length, legacy kept) | PASS |
| Verification text reflects version and approval | PDF footer/box | sweep: 45/45 PDFs carry "Pending approval" + page numbers; `test_reports` | PASS |
| KRA/template definitions developer-managed | `admin/kras/`, `admin/templates/` | code: GET only | PASS |
| Section navigation / Back to top | editor | browser `test_editor_section_navigation_and_back_to_top` | PASS |
| Screen-reader usability | — | — | NOT VERIFIED |
| Production deployment (Linux, Gunicorn, Nginx, TLS) | — | no artefacts exist | BLOCKED |
| Backup / restore | — | no procedure exists | BLOCKED |

## 4. Actual test results

| Check | Result | Evidence |
|---|---|---|
| `python backend/manage.py test tests --parallel 1` (renderer running) | **PASS — Ran 561 tests, OK** | `evidence/backend-suite.txt` |
| `python e2e/run_isolated.py` (+ the injected UI-audit harness) | **PASS — Ran 34 tests, OK** (33 product tests + 1 audit harness) | `evidence/browser-suite.txt` |
| `npx tsc -b`, `npm run build` | **PASS** (one >500 kB chunk warning) | console |
| Audit probes (`scripts/test_zz_audit_probes.py`, 6 tests) | **PASS** after two harness fixes (below) | `evidence/*.json`, `probes-run*.txt` |
| `manage.py check --deploy` with `DJANGO_DEBUG=0` | **PASS with 3 warnings** (HSTS subdomains/preload; `X_FRAME_OPTIONS=SAMEORIGIN` is deliberate for the preview iframe) | console |
| `pip-audit` (ephemeral `uvx`, backend + renderer requirements) | **PASS — no known vulnerabilities** | console |
| `npm audit` (prod and dev) | **PASS — 0 vulnerabilities** | console |
| Template sweep: 45 KRAs × (normal submit, VC preview, PDF, Nil submit, Nil PDF) | **PASS 45/45** | `evidence/template-sweep.json` |
| Long content / wide tables (KRA 15, 19, 20, 33) | **PASS** — wide tables repeat headings on every page (KRA 15: 7/7, KRA 20: 31/31) | `evidence/long-content.json`, `sheet-long.png` |
| Query counts (empty vs 60 submitted reports) | **PASS** — constant: progress 6, analytics 11, assignments 6→7, reopen list 3 | `evidence/query-counts.json` |
| UI metrics at 375/768/1024/1440 + 720 px (~200 % zoom), 13 screens | no page-level horizontal overflow; 25/25 keyboard tab stops with a visible focus ring | `evidence/ui/ui-metrics.json`, `evidence/ui/*.png` |

**Failures investigated (all harness defects, not product defects):**
- The first probe run raised `SnapshotError` from `/analytics/`. The analytics reader must own its transaction (D-074), and Django's `TestCase` wraps every test in one. Those probes were moved into a `TransactionTestCase`, the pattern `test_vc_snapshot` uses, and then passed.
- The long-content probe wrote PNGs before their folder existed. Fixed in the probe.
- Neither was dismissed as flaky: both causes are identified and fixed in the audit harness.

**Visual PDF review: what was actually inspected.**
- Page 1 of KRA 1, 4, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 27, 32, 33, 34, 36, 39, 40, 43, 44 and 45 (every layout family).
- Last pages of KRA 12, 13, 33 and 44.
- Long-content page 2 of KRA 15, 19, 20 and 33.
- Contact sheets: `evidence/sheet-{a,b,c,d,long}.png`.
- Every other KRA PDF was checked by text extraction only, not visually.

## 5. Prioritised findings

### High (production risk; no Critical found)

**H1 — Login throttling cannot work across processes.**
- *Location:* `backend/config/settings.py:90`. `CACHES` is `LocMemCache`; `apps/accounts/views.py:51-68` counts failures in that cache.
- *Reproduction:* run 2+ Gunicorn workers and send failed logins round-robin.
- *Expected / actual:* the limit (per user and per IP) should be global; actual is per worker, and counters reset on restart.
- *Impact:* password guessing gets N× the attempts with N workers.
- *Fix:* a shared cache (database cache table or Redis). Configure via env and refuse to start with `DEBUG=0` and LocMem. Already noted in `docs/progress.md`; still open.

**H2 — No production deployment, backup or restore artefacts.**
- *Location:* `infra/` holds only an env example and the worker's systemd unit. Missing:
  - Nginx/TLS proxy;
  - web service (Gunicorn) unit;
  - renderer service;
  - static/SPA serving and its CSP;
  - log rotation;
  - database and private-media backup and restore drill;
  - malware scanning of uploads.
- *Impact:* the system cannot be deployed or recovered reproducibly. Upload limits are only enforced in Django (no proxy `client_max_body_size`).
- *Fix:* see repair plan, batch B.

### Medium

**M1 — Login page downloads a 2.7 MB background PNG** (`frontend/src/assets/login-background.png`, built as `login-background-*.png` 2,695 kB; campus banner 421 kB, logo 192 kB).
- *Impact:* slow first paint on mobile and campus networks for every user.
- *Fix:* WebP/AVIF at 1920 px (~200–300 kB) with a `srcset`; downscale the logo.

**M2 — Small touch targets.**
- *Affected:* native checkboxes and radios, 16 px (VC dashboard and assignment selection, analytics filters, announcement audience, report multiselects); "View all" (Dean dashboard); "← All announcements"; the preview "Fit width" select.
- *Measured:* below 24 px in `ui-metrics.json`.
- *Impact:* WCAG 2.2 target size (AA, 24 px or spacing); hard to use on phones.
- *Fix:* 20–24 px controls inside ≥ 44 px label rows, which most rows already have; increase checkbox size or label padding.

**M3 — Pending institutional acceptance of all 45 report formats.** Recorded as Phase 4's exit gate in `docs/progress.md`. Not a code defect, but a release gate.

### Low

**L1 — Drive-link validation accepts a non-default port.**
- *Location:* `apps/evidence/services.py:90` checks scheme, host and userinfo, not port.
- *Reproduction:* probe `https://drive.google.com:8443/file/d/x` → 201.
- *Impact:* low (still Google's host, https), but not a canonical Drive URL.
- *Fix:* require `parsed.port in (None, 443)`.

**L2 — CSV formula guard ignores leading whitespace.**
- *Location:* `apps/submissions/analytics_views.py:40-46` prefixes only values that *start with* a trigger character.
- *Reproduction:* probe achievement `" =1+1"` is written unchanged.
- *Status:* whether common spreadsheet software evaluates it is **not verified**.
- *Fix:* test on `s.lstrip()` (and strip leading control characters) before prefixing.

**L3 — Reopening-request list silently capped at 200** (`apps/submissions/views.py`, `ReopenRequestsView`: `qs[:200]`).
- *Impact:* older requests are invisible with no indication.
- *Fix:* paginate like the other lists.

**L4 — Horizontally scrolling content without an affordance below ~1100 px.**
- The main navigation scrolls sideways (VC "Announcements"/"Change password" are off-screen at 768 px; "Reopening r…" is cut at 375 px).
- The announcements table at 375 px cuts the State badge and hides the action column inside its panel.
- *Fix:* fade or scroll hint on overflowing nav; card layout for the announcements table below 640 px, as the report tables already do.

**L5 — Head/Dean name not applied to some sign-off boxes** (scope decision D-079).
- KRA 12's "Dean" box and KRA 45's "HoD"/"Dean" boxes stay blank signature lines.
- KRA 13's "Head of Department / Competent Authority" is blank by design (it may be another person).
- *Fix:* confirm the intended meaning with the institution; extend `capabilities.FIELDS` or the templates if wanted.

**L6 — Programme-length assumptions.** ASH and KSOP default to 4 years of study (`apps/reports/capabilities.py: PROGRAMME_YEARS`). No department-to-programme setting exists. Needs institutional confirmation.

### Informational / design improvements

- `check --deploy`: HSTS `includeSubDomains`/`preload` not set (decide with IT). `X_FRAME_OPTIONS=SAMEORIGIN` is required for the preview iframe.
- Single 537 kB JS chunk (161 kB gzip): acceptable; route-level code splitting would help first load on phones.
- Unresolved policy questions in `docs/progress.md`: reopening for an ended academic year; VC review window.
- The VC review screenshot of a seeded CSE KRA 1 shows an empty report. That row is created directly by an e2e fixture with `payload={}`; it is **not** a product path (real submission validates content).

## 6. UI/UX and accessibility: what was actually tested

**Screens and widths:** 13 screens at 375, 768, 1024 and 1440 px, plus 720 px as a stand-in for 200 % zoom, with populated synthetic data. Screenshots are in `evidence/ui/`. The screens:
- login (Dean, VC);
- Dean dashboard, report workspace (KRA 1) and announcements;
- VC dashboard, assignments, analytics, announcements list and editor, reopening requests, KRAs and review.

**Automated checks (`ui-metrics.json`):**
- page-level horizontal overflow: none;
- controls rendered off-screen;
- unlabelled controls: none flagged;
- small targets (M2);
- clipped text. Most hits are intentional screen-reader-only text. Real truncations are deliberate one-line department names in analytics filters and two-line announcement excerpts.

**Keyboard:** 25 consecutive Tab stops in the Dean workspace all showed a visible focus indicator. Section navigation and Back to top keyboard behaviour is covered by the browser regression.

**Reduced motion:** exercised only for the editor navigation test.

**Not verified:**
- screen-reader output (no NVDA/JAWS/VoiceOver run);
- automated contrast scan (none run here; the suite's `test_phase6c_measured_contrast_of_shared_controls` passed);
- real browser zoom (viewport approximation only);
- modal focus trapping (the app uses `window.confirm`; native dialogs were not assessed);
- touch devices.

**Language:** labels are generally plain. Save, Submit/Resubmit, Approve/Reject and Reopening are distinct controls with distinct wording.

## 7. Performance and operations

**Executed locally:**
- query counts are constant as data grows (no N+1 on progress, analytics, assignments or reopen lists);
- API latency 9–72 ms on the local test DB;
- the long reports produced 7–31 pages without renderer errors.

**Code/config inspection only:**
- renderer sandbox: JavaScript disabled, offline, every non-`data:` request aborted, bound to 127.0.0.1;
- upload limits: per file, per report active and history totals, magic-byte sniffing (PDF/JPEG/PNG);
- `nosniff` and sandbox CSP on evidence downloads;
- secure cookies and HSTS when `DEBUG=0`;
- `SECRET_KEY` required from the environment;
- health endpoints `/health/` and `/health/artifacts/`;
- worker systemd unit with `Restart=always`.

**Not executed:** Linux/Gunicorn capacity, multi-worker behaviour, renderer memory over long uptime (Phase 6B noted growth to ~0.67 GB), backup/restore.

## 8. Unverified areas (explicit)

- Screen-reader usability.
- Real-device touch and zoom.
- Session-expiry UX after 8 h.
- Behaviour behind a TLS proxy.
- Linux, Gunicorn and Nginx.
- Production capacity.
- Backup and restore.
- Spreadsheet behaviour of the L2 value.
- Institutional acceptance of all 45 formats and programme lengths (L5, L6).
- Visual review of PDFs other than those listed in section 4.

## 9. Evidence index

`docs/audits/evidence/`:
- **Suite logs:** `backend-suite.txt`, `browser-suite.txt`.
- **Probe results:** `template-sweep.json`, `security-probes.json`, `invariant-probes.json`, `analytics-probes.json`, `long-content.json`, `query-counts.json`; run logs `probes-run.txt`, `probes-run-2.txt`.
- **PDF images:** `pdf-pages/` (PDF page images), contact sheets `sheet-*.png`.
- **UI:** `ui/` (screenshots and `ui-metrics.json`).

`docs/audits/scripts/`:
- `test_zz_audit_probes.py`: copy it into `backend/tests/` to rerun, then remove it.
- `ui_audit_inject.py`: injects the UI harness into `e2e/test_browser.py`; restore the file afterwards.
- `contact_sheet.py`.

All data shown is synthetic; no credentials or secrets are included.

## Batch A results (2026-10-24)

| Finding | Fix | Evidence |
|---|---|---|
| H1 login throttling | PostgreSQL table `accounts_loginthrottle` (migration `accounts.0002`) with one atomic `INSERT … ON CONFLICT … RETURNING` per key; attempts are reserved before the password check; same limits (5 per portal+username, 20 per IP, 15-minute fixed window); 503 `login_unavailable` (fail closed) if the store is unreachable; no cache backend is used, so there is nothing to fall back to | `tests/test_batch_a_security.py` — 12 concurrent reservations get distinct counts 1–12; 12 concurrent wrong-password logins → exactly 5 password checks, 5×400 + 7×429; **three separate OS processes** (fresh Django processes, standing in for separate workers or a restarted worker) share one counter: 3 + 2 failures, then the correct password in a third process → 429; window expiry, IP limit across usernames/portals, 503 with no password check |
| L1 Drive link ports | `apps/evidence/services.is_drive_url`: https, drive/docs host, no username/password, port `None` or `443`; malformed/out-of-range ports rejected. The only create path (`add_link`) uses it; links are never updated | URL table test (4 valid, 15 invalid incl. `:8443`, `:0`, `:99999`, `:abc`, `:-1`, credentials); API create path 201/400 |
| L2 CSV formulas | `cell()` prefixes `'` when the first character after leading whitespace, control characters, Unicode spaces or a BOM is `= + - @` (and the existing tab/CR rule); applied to every cell of the analytics CSV (the only CSV export) before `csv.writer` quoting; stored values unchanged | Unit cases (16 dangerous, 10 ordinary incl. `a=b`, `1-2 days`, quotes, newlines), quoting round-trip, real `analytics/export/?kind=csv` with stored values checked unchanged |

Checks:
- `python backend/manage.py test tests --parallel 1` (renderer running): **573 OK**.
- `python e2e/run_isolated.py`: **33 OK**.
- `npx tsc -b` and `npm run build`: OK.
- `makemigrations --check`: no changes.

Not verified:
- **Spreadsheet behaviour.** Excel and LibreOffice were not run. The tests prove the exported text is sanitised, not how any spreadsheet program treats it.
- **Cross-worker protection under Gunicorn on Linux.** It was demonstrated with separate local processes against PostgreSQL, not with Gunicorn on Linux.

Remaining deployment requirements for H1:
- the reverse proxy must forward the real client address to `REMOTE_ADDR`; otherwise all users share one IP counter;
- the throttle is only as available as the database.

H2 (deployment, backup/restore, malware scanning) is still open.
