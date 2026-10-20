# KIET KRA Portal — Project Handover

Prepared 2026-10-17 from the project's own docs and git history; updated at the end of Phase 6C. Results in §7 are labelled with when they were run.
**This document contains no secrets.** Environment variables are listed by name only. `backend/.env` and the demo credentials file were not opened.

> **This file alone does not transfer the working project.** It explains the project and how to continue it. The repository, the local database, private evidence files and environment configuration must be transferred separately (see §9).

---

## 1. Purpose

A college-hosted portal for KIET's bimonthly KRA (Key Result Area) reporting.

- **Department Deans** fill in a structured report for each assigned KRA and two-month period, upload evidence and enter an achievement.
- **One college-wide VC** reviews submissions (approve / reject / return with a reason), manages KRAs, assignments and targets, and exports progress.

## 2. Stack and architecture

| Part | Technology |
|---|---|
| `backend/` | Django 5.2 LTS + Django REST Framework, PostgreSQL 16, session login with CSRF protection |
| `renderer/` | Separate internal PDF service (Playwright + Chromium pool) on 127.0.0.1:8790. No browser runs inside the web workers |
| `frontend/` | React 19 + TypeScript + Vite + Tailwind, React Hook Form |
| `seed/catalogue_2026-27.json` | Reviewed 45-KRA catalogue and 2026–27 targets |

**How it fits together:**

- **Backend apps:** `backend/apps/{accounts, catalogue, submissions, evidence, reports, audit}`.
- **Forms are schema-driven.** Each KRA's form is a JSON schema in `backend/apps/reports/schemas/*.json`, or a builder in `families.py` registered in `BUILDERS`.
  - The schema's `renderer` key selects the layout in `backend/templates/reports/*.html`.
  - Field types: text, longtext, integer, decimal (kept as exact strings), date, select, multiselect, checklist, ratings, table.
  - Supports `when` conditions, opt-in `keep_inactive`, and row/activity rules (`date_order`, `lte`, `ref_in`).
- **The same template serves** the live preview and the PDF export. Page styles are report, survey and sheet; the font is Tinos.
- **VC progress:** `apps/submissions/progress.py` builds one SQL dataset that feeds the table, the status counts and the progress PDF.
- **API:** everything is under `/api/v1/`. It is documented in `docs/api.md`.
- **Errors:** every error returns `{code, message, field_errors, request_id}`.

**Important paths:**

| Path | What it holds |
|---|---|
| `backend/tests/` | Backend test suite (Django test runner, PostgreSQL) |
| `e2e/run_isolated.py`, `e2e/test_browser.py` | Browser tests and their isolated runner |
| `scripts/devdb.py` | Local PostgreSQL helper (start/stop; writes `backend/.env` on first start) |
| `scripts/extract_seed.py`, `compare_pdf.py`, `pdf_overview.py` | Seed extraction and PDF comparison tools |
| `infra/` | Empty (deployment artefacts not yet written) |

## 3. Authoritative plan and references

| Document | Role |
|---|---|
| `docs/implementation-plan.md` (v2.0) | **Authoritative plan.** Identical to the root copy `KIET_KRA_Claude_Code_Implementation_Plan (2).md` |
| `docs/decisions.md` | Decision log D-001 … D-068; items needing a college answer are marked **college** |
| `docs/progress.md` | Phase checklist. Its two header lines (lines 3–4) are stale; the sections below them are current |
| `docs/validation.md` | Recorded test commands and results per phase |
| `docs/api.md` | Endpoint reference, including Phase 5A/5B |
| `docs/template-inventory.md`, `docs/source-audit.md` | Source-format inventory and audit |
| `README.md` | Setup and per-phase review notes. **Its opening status lines and "Tests" section are stale** (they say "Phase 2 pilot" and "45 tests", and they run browser tests directly) |
| `reference/` (in git, 32 files) | 30 source template PDFs, plus `reference/workbook/original-tracker.xlsx` and its Markdown conversion |

- **Repository instructions:** there is no `CLAUDE.md` or `AGENTS.md`.
- **Launch configs:** dev-server launch configs live outside the repo at `../.claude/launch.json`.

## 4. Established business rules

- **Accounts:**
  - Exactly one active VC for the whole college, enforced by the database (`one_active_vc`).
  - At most one active Dean per department (`one_active_dean_per_department`).
  - Separate Dean and VC login pages. A wrong-portal login is rejected and creates no session.
  - Authorization is checked on every endpoint. Objects outside a Dean's department return 404 (D-021).
- **Login throttling:** 5 failures per 15 minutes per portal and username, plus 20 per 15 minutes per IP (D-016).
- **Targets:**
  - Annual targets are stored as exact text and are fixed once assigned. Both the API and the model reject changes.
  - The VC drafts assignments for the current or future years, only for department/KRA pairs that have no assignment yet.
  - Ended years are read-only (D-065, D-066).
- **Reporting cycle:**
  - Six periods per academic year (Jul–Jun), with boundaries at 00:00 Asia/Kolkata.
  - A report row is created only by a Dean action inside an open window (D-017).
- **Workspace:** each report has Report, Evidence and Achievement tabs.
  - **Report:** a form with a live preview and PDF export.
  - **Autosave:** coordinated, with conflict detection (`edit_version`).
  - **Validation:** incomplete drafts save. Required fields and cross-checks apply only at Validate or Submit (D-028).
  - **Untouched drafts:** a draft never edited and without evidence displays as "Not submitted" (rule C11).
  - **Nil reports:** need a reason and still go to the VC.
- **Submission:**
  - Submitting creates an immutable revision holding the content, a snapshot and the evidence manifest.
  - Review screens, history and approval labels read only from the submitted revision (D-068).
- **Evidence:**
  - Accepted: PDF, JPEG and PNG (checked by file signature) or Google Drive links.
  - Limits: 20 MB per file, 100 MB active, 500 MB history (D-019).
  - Files are stored privately and downloaded through authorized endpoints. They are never embedded in report PDFs.
  - Removed files stay downloadable for history.
- **Reopening:** a 72-hour grant scoped to one submission. It comes either with a review decision or through a Dean request after the period closes (rule C1).
- **Audit log:** reviews, grants, VC administration actions and cleanups.
- **No calculations:** no automatic totals, percentages or rankings anywhere.
- **Standing project constraints:**
  - No synthetic data in production seeds.
  - Do not weaken security, replace PostgreSQL silently or bypass deadline rules.
  - Never claim tests passed that were not run.
  - Never claim production readiness from local pilot success.
  - No commit, push or deploy without the owner's approval.

## 5. Phases completed

| Phase | Content | Commit(s) |
|---|---|---|
| 0–2 | Source audit and seed; foundation and access control; KRA 33 pilot | `3f4748a` |
| 3 | Template families: KRAs 20, 7, 32 | `f9ebf88` |
| 4 (bounded batches) | All other KRAs (table below), event-tab reset fix `6b34e82`, 45-KRA coverage reconciliation | `713e092` … `d14b72e` |
| 5A | VC: create KRAs on an installed layout; draft assignments (exact target text); copy a year to next-year drafts with conflicts reported; transactional, double-click-safe finalize; audit | `a012da6` |
| 5A follow-up | Current-year locking corrected (only ended years are read-only); isolated browser-test runner; DEBUG-only `cleanup_e2e_data` command | `1cd9f13` |
| 5B | VC progress: one dataset for table, counts and uncached VC-only PDF of all filtered rows; review reads the submitted revision; filters kept on return | `c88a191` |
| 6A | Permissions and workflow-integrity hardening: route-wide permission sweep, deadline/72 h edges, real concurrent-request tests. Fixes: no reopening of not-yet-started periods, export no-store, stale dashboard responses, test storage isolation (D-069) | `2fb8415` (pushed) |
| 6B | Performance and failure-recovery validation with `e2e/run_perf.py`. Fixes: PDF reply validation, IncompleteRead handling, no orphan upload files, dashboard N+1, renderer relaunch-and-retry after a Chromium crash (D-070) | `71d326c` (in sync with origin at fetch, 2026-10-17) |
| 6C | Usability/accessibility fixes (tabs, cell names, applicability-aware required markers, inactive-field notes, phone-width header, focus) and documentation reconciliation; acceptance checklist (D-071) | `b5e5931` (on origin, verified by fetch 2026-10-17); follow-up (wording, contrast D-072, per-KRA checklist) **uncommitted** |

### 45-KRA status

**Implemented ≠ approved.** All 45 KRAs have a template, an assignment mapping (585/585 assignments) and tests (D-064). **0 of 45 are institutionally accepted.** The Phase 4 review gate is still open.

The format type comes from `docs/decisions.md`. "Supplied" means a source format was given; "adapted" and "project-created" formats especially need college review.

| KRA(s) | Format | Commit | Implemented | Institutionally accepted |
|---|---|---|---|---|
| 33 (pilot) | Supplied | `3f4748a` | Yes | No |
| 7, 20, 32 | Supplied | `f9ebf88` | Yes | No |
| 11 | Supplied | `713e092` | Yes | No |
| 23 | Supplied | `6d72505` | Yes | No |
| 1, 2, 3 | Supplied (course family) | `73765ac` | Yes | No |
| 36, 37 | Supplied (FDP/STP family) | `39de3d8` | Yes | No |
| 8, 9, 10 | Supplied (consolidated surveys) | `331a234` | Yes | No |
| 19 | Supplied | `2fbd120` | Yes | No |
| 13, 17, 18 | Supplied | `61840c6` | Yes | No |
| 15, 22, 31, 38 | Supplied | `92508f7` | Yes | No |
| 4, 5, 6, 24 | Supplied | `6c9dd60` | Yes | No |
| 12, 25, 26 | Supplied | `11a519c` | Yes | No |
| 27, 28, 29, 30 | Project-created (event family) | `8ea5527` | Yes | No |
| 43 | Adapted | `8ce4b52` | Yes | No |
| 44, 45 | Supplied | `8ce4b52` | Yes | No |
| 21, 39 | Adapted | `e4e934c` | Yes | No |
| 14, 16, 34, 35 | Project-created | `41885d4` | Yes | No |
| 40, 41, 42 | Project-created | `d14b72e` | Yes | No |

Total: 45 implemented, 0 accepted.

### Remaining work

- **Phase 4 exit:** institutional review and acceptance of all 45 formats. This is an owner/college task, not code.
- **Phase 6:** remaining slices — 6D production configuration, a Gunicorn/Linux performance repeat, the team walkthrough and owner sign-off (§11). 6A, 6B and 6C are done.
- **Phase 7:** deployment, backups and restore drills.
- **Deferred by plan:**
  - C10 evidence ZIP;
  - an OpenAPI document;
  - frontend component tests;
  - deployment artefacts (Nginx/Gunicorn/Compose, backups, monitoring).

## 6. Current repository state

Updated 2026-10-17 at the end of Phase 6B.

| Item | State |
|---|---|
| Branch | `phase2-kra33-pilot` |
| HEAD | `b5e5931` — "Phase 6C: usability/accessibility fixes and documentation reconciliation" (= `origin/phase2-kra33-pilot` after `git fetch`, 2026-10-17) |
| Remote | `origin` = `https://github.com/Ayush-Yadav-work/kiet-kra-portal.git`. `git fetch` on 2026-10-17 (start of Phase 6C): `origin/phase2-kra33-pilot` = `71d326c`, 0 ahead / 0 behind. `main` holds only the earlier history |
| Uncommitted work | **Phase 6C follow-up** (not committed): `frontend/src/index.css`, `frontend/src/features/report-builder/SchemaForm.tsx`, `frontend/src/features/report-builder/Workspace.tsx`, `e2e/test_browser.py`, `docs/acceptance-checklist.md`, `docs/progress.md`, `docs/validation.md`, `docs/decisions.md`. This handover file is untracked |
| Ignored, not in git | `backend/.env`, `.env`, `.work/` (about 648 MB locally), `.venv/`, `frontend/node_modules`, `frontend/dist`, `.claude/` |

> Phases 6A (`2fb8415`), 6B (`71d326c`) and 6C (`b5e5931`) are committed and on origin. The 6C follow-up is **uncommitted**; commit it (excluding this file unless the owner wants it in git) before transferring via git.

## 7. Latest recorded test and build results

| Check | Result | Source |
|---|---|---|
| Backend suite: `manage.py test tests` (renderer running) | 506 tests, OK, 0 skipped | Recorded at Phase 6B (`71d326c`); not rerun in 6C (no backend change) |
| Browser suite: `e2e/run_isolated.py` (isolated database only) | 26 tests, OK | Run in the 6C follow-up (25 OK at `b5e5931`, 24 OK at 6B) |
| Frontend `tsc -b` + `npm run build` | OK | Run in Phase 6C |
| Local performance/failure run: `e2e/run_perf.py` | 0 server errors at 5–15 users; PDF bounded at 2 active + 4 queued; outage, crash and timeout recover | `docs/validation.md`, Phase 6B (Windows development server — not production capacity) |
| Working database unchanged by browser runs | 24 table fingerprints identical across 4 isolated runs | Phase 5A follow-up, `1cd9f13` |
| 45-KRA coverage | 45 template versions; 585/585 assignments mapped | D-064, `d14b72e` |
| Sample PDFs | `.work/renders/kra*/`, `.work/renders/progress/sample.pdf` (54 pages), visually checked | `docs/validation.md` (files not in git) |

These are recorded results from 2026-10-17. Rerun them on the new machine (§10, step 6) before relying on them.

## 8. Known bugs, assumptions, college decisions and release blockers

**Release blockers:**
1. Institutional acceptance of all 45 report formats, especially the adapted ones (21, 39, 43) and the project-created ones (14, 16, 27–30, 34, 35, 40–42).
2. Phase 6 hardening completed and signed off by the owner.
3. Phase 7 deployment, backups and a tested restore.
4. A shared throttle cache before running more than one Gunicorn worker. Login throttling currently uses an in-process cache.
5. Capacity on the real server: `e2e/run_perf.py` was measured only on Windows with Django's development server. Repeat it with Gunicorn on the college Linux server before setting user limits.
6. An owner decision on earlier test residue in the working `.work/private` (252 evidence / 1,455 generated files) and database. Nothing has been deleted.

**Pending college decisions:** about 36 items are marked **college** in `docs/decisions.md`. Examples:
- minimum evidence sets for most KRAs;
- KRA 19: the duplicate "PSO1" column (D-012);
- KRA 39: "INR in Lakhs" versus the target size (D-057);
- KRA 45: the meaning of "MBU";
- KRA 43: affiliation and the 20% rules;
- KRAs 34–35: the Rs. 5,000 annual condition (D-060);
- KRAs 25/26: the inter-university level;
- KRA 7: the consolidated layout, and KRA 32: its extra type/column (D-030, D-031);
- the D-036 and D-038 assumptions.

**Known issues and limits:**
- **Table rows:** tables are capped at 100 rows (`KRA_MAX_TABLE_ROWS`).
- **Page breaks:** long rows break only at row boundaries. One sample (KRA 15, long) ends with a page holding only the verification box.
- **KRA 33:** the PDF footer sits about 8 pt off the source position.
- **Inactive fields (KRA 9, KRAs 4–6):** hidden with a note while not applicable; values are retained in the draft and in submitted revisions, skipped by submit validation and not printed. The two template intros still say "not submitted" (needs a new template version to correct).
- **Security:** no malware scanning of uploads.
- **Autosave:** after a failed save, the queue retries on the next change only (the indicator says so). A save whose response was lost gets a version conflict on retry; the Conflict dialog keeps the typed values.
- **Renderer memory:** renderer + Chromium RSS rose from about 0.5 to 0.67 GB during a run with restarts; monitor it under long uptime.
- **Policy questions from 6A:** reopen requests for ended academic years, and no VC review window; see `docs/progress.md`.
- **Accessibility:** scripted audit, keyboard/tab fixes and measured contrast of shared controls done (6C, D-071/D-072); **pending human checks:** screen reader, real 200% browser zoom (not drivable in automated Chromium), real phone — see `docs/acceptance-checklist.md` §6. Not a full WCAG audit.

**Data and security notes:**
- **Browser-test leftovers in the working database:** reported earlier, not re-verified.
  - A `cleanup_e2e_data` dry run listed 5 records with test provenance.
  - It also listed a batch of 584 unedited 2027–28 drafts (copy event 2089), which are removable only with explicit confirmation.
  - Older 2026–27 ECE demo report drafts remain as report data. The cleanup does not touch them.
  - **Nothing has been deleted.** Review the dry run before using `--execute`.
- **Credential exposure:** during development the local dev-database credentials appeared once in tool output. They were never committed. Rotating them is recommended.

## 9. What must be transferred separately

Git carries only what has been **pushed** (or bundled). None of the following is in git:

| What | Location | Notes |
|---|---|---|
| Repository | GitHub `origin`, branch `phase2-kra33-pilot` | A fresh clone brings code, migrations, schemas, templates, tests, docs, seed JSON and `reference/`. Push or bundle any local commits first |
| Uncommitted/untracked files | `git status` | Phase 6C files listed in §6 until committed, and this file |
| Development database | `.work/pgdata` (PostgreSQL 16 data directory, port 54329) | Catalogue, 2027–28 drafts, demo accounts, test leftovers, any manually entered data |
| Private evidence | `.work/private/` | Uploaded evidence files. **Private data:** share only with authorized people |
| Environment config | `backend/.env` | Holds secrets. Do not send it in chat or email. Recreate it on the new machine, or copy it securely together with `pgdata`; its `DATABASE_URL` must match that data |
| Demo credentials | `.work/demo-credentials.txt` | Regenerated by `seed_demo`. Do not share casually |
| Generated samples | `.work/renders/` (also `extract/`, `*_before`) | Optional; can be regenerated |
| Reference sources | `reference/` | Already in git. Any originals outside the repo (unknown) must be sent separately |
| Tooling | `.venv/`, `frontend/node_modules/` | Reinstall; do not copy |
| Launch configs | `../.claude/launch.json` | Optional |

**Consistent backup:** copy the database and `.work/private/` together, with no app activity in between. Either:
- stop PostgreSQL (`scripts/devdb.py stop`) and copy `.work/pgdata` and `.work/private` together; or
- with the database running, take `pg_dump -Fc` of the database named in `DATABASE_URL`, then copy `.work/private`.

Compare sizes and checksums after copying.

## 10. New-machine setup

These instructions come from the README and docs. They were not executed for this handover.

**Runtimes:**
- Python 3.11;
- Node 20+ (tested with 24);
- PostgreSQL 16 (bundled through the `pgserver` pip package on Windows);
- Playwright with Chromium.

**Environment variable names (values never included here):**
- **Django:** `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SSL_REDIRECT`
- **Storage and limits:** `PRIVATE_STORAGE_ROOT`, `EVIDENCE_MAX_FILE_MB`, `EVIDENCE_MAX_ACTIVE_MB`, `EVIDENCE_MAX_HISTORY_MB`, `KRA_MAX_ACTIVITIES`, `KRA_MAX_TABLE_ROWS`
- **Renderer client:** `RENDERER_URL`, `RENDERER_TIMEOUT_SECONDS`
- **Renderer service:** `RENDERER_PORT`, `RENDERER_POOL`, `RENDERER_MAX_QUEUE`, `RENDERER_JOB_TIMEOUT`
- **Browser tests (set by the runner):** `KRA_API_TARGET`, `KRA_E2E_*`

After cloning (step 1), change into `kiet-kra-portal/` and run every later command there. The paths are for Windows; on Linux/macOS use `.venv/bin/python`.

1. **Clone and create the Python environment:**
   ```bash
   git clone https://github.com/Ayush-Yadav-work/kiet-kra-portal.git
   ```
   ```bash
   cd kiet-kra-portal
   ```
   ```bash
   git checkout phase2-kra33-pilot
   ```
   ```bash
   py -3.11 -m venv .venv
   ```
   ```bash
   .venv/Scripts/pip install -r requirements-dev.txt
   ```
2. **Install the renderer's browser:**
   ```bash
   .venv/Scripts/python -m playwright install chromium
   ```
3. **Install frontend dependencies:**
   ```bash
   npm --prefix frontend install
   ```
4. **Set up the database.**
   - **Fresh setup:** this starts PostgreSQL and writes a new `backend/.env` with a generated URL and secret.
     ```bash
     .venv/Scripts/python scripts/devdb.py start
     ```
     Then migrate and seed:
     ```bash
     .venv/Scripts/python backend/manage.py migrate
     ```
     ```bash
     .venv/Scripts/python backend/manage.py seed_catalogue
     ```
     ```bash
     .venv/Scripts/python backend/manage.py seed_demo
     ```
     `seed_demo` creates demo accounts (DEBUG only) and writes their passwords to `.work/demo-credentials.txt`.
   - **Restoring existing data:** put the copied `.work/pgdata`, `.work/private` and a matching `backend/.env` in place before `devdb.py start`, then run only `migrate`.
     - *Unverified:* a pgdata directory moves only between the same PostgreSQL major version and platform. Otherwise restore a `pg_dump` into a fresh database (for example with `pg_restore`; also unverified).
   - **Linux/macOS (unverified):** use any PostgreSQL 16 and set `DATABASE_URL` and `DJANGO_SECRET_KEY` yourself.
5. **Start the services**, one per terminal:
   ```bash
   .venv/Scripts/python renderer/server.py
   ```
   ```bash
   .venv/Scripts/python backend/manage.py runserver 127.0.0.1:8000
   ```
   ```bash
   npm --prefix frontend run dev
   ```
   Open http://localhost:5173 and use `/dean/login` or `/vc/login`.
6. **Verify the setup:**
   ```bash
   .venv/Scripts/python backend/manage.py test tests
   ```
   ```bash
   npm --prefix frontend run build
   ```
   ```bash
   .venv/Scripts/python e2e/run_isolated.py
   ```
   The browser runner uses a throwaway `<db>_e2e` database, ports 8001 and 5174, and isolated uploads. **Never run `e2e/test_browser.py` directly.** It refuses to run unless `KRA_E2E_ISOLATED=1`.
7. **Optional test-data cleanup** (DEBUG only). Dry run first:
   ```bash
   .venv/Scripts/python backend/manage.py cleanup_e2e_data
   ```
   Then, only after reviewing the dry-run report:
   ```bash
   .venv/Scripts/python backend/manage.py cleanup_e2e_data --execute
   ```

## 11. Next bounded phase — Phase 6: Hardening and acceptance

Do it in bounded slices, each with its own review and commit. **6A** (`2fb8415`), **6B** (`71d326c`) and **6C** (`b5e5931`, plus an uncommitted follow-up) are done. The next bounded slice is **6D: production configuration**.

| Slice | Scope (plan §Phase 6 and §12) | Acceptance criteria |
|---|---|---|
| ~~6A: Permissions and workflow integrity~~ (done, `2fb8415`) | Server-side authorization for reports, revisions, evidence, downloads, previews/PDFs, reopening, assignments and progress. Deadlines and reopen windows (Asia/Kolkata, 72 h). Immutable targets and revisions. Concurrency: autosave vs submit, evidence vs submit, duplicate submit, competing VC decisions, stale tabs | Anonymous users get no protected content. Deans cannot reach another department through IDs, nested routes or download URLs, and cannot call VC actions. No private evidence on a static/media route. Deadline boundaries are tested with controlled clocks. Stale or competing requests cannot overwrite newer decisions or change submitted evidence. Each confirmed defect has a regression test. The full backend suite and the relevant isolated browser tests pass. Results are recorded in `docs/validation.md` |
| ~~6B: Performance and failure recovery~~ (done, `71d326c`; D-070) | Renderer queue/timeout/outage/crash, mixed workload, failure recovery | See `docs/validation.md`, Phase 6B |
| ~~6C: Usability and accessibility~~ (done, `b5e5931` + follow-up; D-071, D-072) | Keyboard navigation, labels, mobile layout, empty/error states | See `docs/validation.md`, Phase 6C |
| **6D: Production configuration** (next) | Dependency audit; `DEBUG=0` settings; secure cookies; shared throttle cache; upload safety | Deployment checklist written and verified locally. No secrets in the repository |
| 6D (cont.): Linux/Gunicorn repeat of `e2e/run_perf.py` | On the target server class | Measured limits recorded; no capacity claim without it |
| 6E: Walkthrough | One VC and at least two Dean test accounts, end to end, using `docs/acceptance-checklist.md` | Owner signs off the documented acceptance |

**Phase 6 exit:** no critical data-isolation or workflow defects, plus documented acceptance signed off by the project owner. Automated verification does not count as college acceptance.

**Out of scope:** Phase 7 deployment, the evidence ZIP and any template designer.

## 12. Continuation prompt for Claude Code

Paste this into Claude Code from the `kiet-kra-portal/` folder on the new machine:

```text
Read KIET_KRA_PROJECT_HANDOVER.md at the repository root, then docs/implementation-plan.md, docs/progress.md, docs/decisions.md and docs/validation.md.

READ-ONLY VERIFICATION FIRST. Do not create, modify, delete, stage or commit files. Do not install, migrate, seed, start services, run cleanup commands or touch any database. Never print .env contents, passwords, tokens or credentials.

1. Using GIT_OPTIONAL_LOCKS=0, report the branch, HEAD, working-tree status and ahead/behind against origin/phase2-kra33-pilot. Confirm HEAD is b5e5931 or a later descendant (a 6C follow-up commit, if made). List any uncommitted files and say whether they match the 6C follow-up list in handover §6.
2. Check presence only (never contents) of: .venv, frontend/node_modules, backend/.env, .work/pgdata, .work/private, .work/demo-credentials.txt. Report the installed Python, Node and PostgreSQL versions.
3. Compare this machine with handover §9–§10. List what is missing or inconsistent, and which recorded results in §7 have not yet been rerun here.
4. Restate the next bounded phase (handover §11) and the open blockers (§8).

Then STOP and wait for my explicit instruction before installing, running tests or implementing anything.
```
