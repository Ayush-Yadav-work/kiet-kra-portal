# KIET KRA Portal

College-hosted portal for bimonthly KRA reporting: one Vice Chancellor, one Dean per department.
Plan: [`docs/implementation-plan.md`](docs/implementation-plan.md) (v2.0). Status: **Phase 2 pilot (KRA 33) — local only, awaiting acceptance.**
Phase 3 (KRAs 20, 7, 32) implemented and awaiting review. Not production-ready: see [`docs/progress.md`](docs/progress.md).

| Part | Stack |
|---|---|
| `backend/` | Django 5.2 LTS + DRF, PostgreSQL, session auth + CSRF |
| `renderer/` | Internal PDF renderer: Playwright + Chromium pool on 127.0.0.1:8790 |
| `frontend/` | React + TypeScript + Vite, Tailwind, React Hook Form |
| `seed/` | Reviewed catalogue + 2026-27 targets extracted from `reference/workbook/` |
| `docs/` | Plan, source audit, template inventory, decisions, progress, validation |

## Local setup (Windows, PowerShell or Git Bash; run from `kiet-kra-portal/`)

Prerequisites: Python 3.11, Node 20+ (tested with 24).

```bash
py -3.11 -m venv .venv
```
```bash
.venv/Scripts/pip install -r requirements-dev.txt
```
```bash
.venv/Scripts/python -m playwright install chromium
```
```bash
npm --prefix frontend install
```
```bash
.venv/Scripts/python scripts/devdb.py start
```
`devdb.py` starts a local PostgreSQL 16 on 127.0.0.1:54329 and writes `backend/.env` (database URL, secret key, `DJANGO_DEBUG=1`). On Linux/macOS use `.venv/bin/python` and any PostgreSQL; set `DATABASE_URL` and `DJANGO_SECRET_KEY` yourself.

```bash
.venv/Scripts/python backend/manage.py migrate
```
```bash
.venv/Scripts/python backend/manage.py seed_catalogue
```
```bash
.venv/Scripts/python backend/manage.py seed_demo
```
`seed_demo` (DEBUG only) creates synthetic accounts `demo.vc`, `demo.dean.cse`, `demo.dean.ece` and writes their random passwords to `.work/demo-credentials.txt` (git-ignored). Real accounts: `manage.py provision_user --role DEAN --department CSE --username … --name "…"` prints a one-time password.

## Run (three terminals)

```bash
.venv/Scripts/python renderer/server.py
```
```bash
.venv/Scripts/python backend/manage.py runserver 127.0.0.1:8000
```
```bash
npm --prefix frontend run dev
```
Open http://localhost:5173 → Dean login (`/dean/login`) or VC login (`/vc/login`). Vite proxies `/api` to Django, so the session cookie stays same-origin.

## Tests

```bash
.venv/Scripts/python backend/manage.py test tests
```
45 tests on the real PostgreSQL test database. The 3 PDF tests run only when the renderer is up (otherwise they are reported as skipped).
```bash
npm --prefix frontend run build
```
Browser regression tests (need the three servers below running and `seed_demo` done; they edit ECE demo drafts only):
```bash
.venv/Scripts/python e2e/test_browser.py
```
Synthetic sample PDFs for KRAs 33, 20, 7 and 32 (`normal`, `long`, `empty`, `nil`) → `.work/renders/kra<N>/` (needs the renderer):
```bash
.venv/Scripts/python backend/manage.py render_sample
```
Side-by-side with the source (example for KRA 7):
```bash
.venv/Scripts/python scripts/compare_pdf.py "reference/templates/KRA 7 Curriculum Feedback (Faculty).docx (1).pdf" .work/renders/kra7/normal.pdf .work/renders/kra7/cmp
```

## Pilot review checklist (Phase 2 acceptance)

Use two browsers/profiles (one browser profile holds one session at a time).
1. **Dean (CSE):** dashboard → KRA 33 → *Open* for P2. Fill events (add a second event, add/remove table rows), watch autosave and the live preview; open the *Final PDF preview*.
2. Evidence tab: add files (PDF/JPEG/PNG ≤ 20 MB) and Drive links; the minimum set (notice, attendance, photographs — proposal D-013) is required to submit. Achievement tab: enter the period achievement.
3. Submit. Try *Nil* on another period: reason required, no evidence needed.
4. **VC:** dashboard counts/filters → *Review* → Reject with a reason. **Dean** sees the reason on the dashboard, corrects and resubmits; **VC** approves; PDF now reads "Verified by VC - …"; *Return for correction* keeps the approved revision in History.
5. **Reopening:** Dean opens P1 (closed) → *Request reopening* → VC approves in *Reopening requests* → Dean dashboard shows the "Reopened KRAs — Action Required" banner with countdown.
6. Reject/return on a closed period (or <72 h left) shows "Grant 72 hours to resubmit", checked by default.
7. Confirm Dean ECE cannot see CSE data and that the VC portal refuses Dean credentials.

Please record template-fidelity/usability feedback and decisions on the **college** items in `docs/decisions.md` (D-003, D-012, D-013) before Phase 3.

## Phase 3 review checklist (KRAs 20, 7, 32)

After `git pull`/checkout, re-run `manage.py migrate` (no new migrations in Phase 3) and `manage.py seed_catalogue` so KRAs 20, 7 and 32 get their templates; restart Django and the renderer.
1. **KRA 20 (Dean):** open KRA 20 → add records with the card editor; enter an end date before the start date and confirm the draft still saves but *Submit* lists the error; preview/PDF show one landscape table with repeating headers.
2. **KRA 7 (Dean):** enter averages such as `3.80` and `4.255` — the draft keeps exactly what you typed; *Submit* rejects more than 2 decimals ("not rounded") and values outside 1–5 / 1–10; respondents cannot exceed faculty surveyed. Check the consolidated wording (D-030).
3. **KRA 32 (Dean):** switch a record between *Financial Contribution* and *Equipment/Asset* — payment fields become NA and clear; item details are required for non-financial records; no totals anywhere.
4. For each: Evidence tab minimum (D-029–D-031), Achievement tab, Nil, then as VC reject after the period closes with "Grant 72 hours", Dean resubmits, VC approves and the PDF reads "Verified by VC - …".
5. Compare `.work/renders/kra20|kra7|kra32/*.pdf` with the source PDFs and record decisions on D-029–D-031 in `docs/decisions.md`.

## KRA 11 review (Bridge Courses)

Run `manage.py seed_catalogue` (maps KRA 11 idempotently) and restart Django. As a Dean open KRA 11: add two courses (*+ Add course*), syllabus modules, outcomes and assessment; leave the feedback score blank once to see the source's blank line; check *Final PDF preview*. Samples: `.work/renders/kra11/normal.pdf`, `long.pdf`, `empty.pdf`, `nil.pdf` (regenerate with `manage.py render_sample --kra 11`). Record decisions on D-034.

## KRA 23 review (Skill Development & Employability Training)

Run `manage.py seed_catalogue`, restart Django, open KRA 23 as a Dean: enter the programme title, tick only the objectives that applied, add several *Detail of Program* records (try completed > enrolled — the draft saves, *Submit* reports it), add a second programme with *+ Add programme*, then *Final PDF preview*. Samples: `.work/renders/kra23/normal.pdf`, `long.pdf`, `empty.pdf`, `nil.pdf` (regenerate with `manage.py render_sample --kra 23`). Record decisions on D-035.

## KRAs 1–3 review (course-report family)

Run `manage.py seed_catalogue`, restart Django. As a Dean open KRAs 1, 2 and 3 for the same period: each is a separate report. KRA 1 asks for a Course Code (enrolment optional), KRA 2 follows the source wording, KRA 3 asks for the Platform / Certifying Body. Samples: `.work/renders/kra1|kra2|kra3/normal.pdf`, `kra2/long.pdf`, `*/nil.pdf`. Decisions: D-036.

## KRAs 36–37 review (FDP / STP family)

Run `manage.py seed_catalogue`, restart Django. As a Dean open KRA 36 (staff training: STP labels, write your own objectives/outcomes) and KRA 37 (FDP on I&E/IPR: tick focus area, objectives, outcomes). In KRA 37 enter 12 hours — the draft saves, *Submit* refuses below 30 hours; Nil still submits. Add participants and modules, then *Final PDF preview*; submit and approve as the VC to see "Verified by VC". Samples: `.work/renders/kra36/normal.pdf`, `kra37/normal.pdf`, `kra37/long.pdf`, `*/nil.pdf` (regenerate with `manage.py render_sample --kra 36 --kra 37`). Decisions: D-037.

## KRAs 8–10 review (consolidated surveys)

Run `manage.py seed_catalogue`, restart Django. As a Dean: KRA 8 / KRA 10 — enter counts, organisations, tick relationships, enter averages (try `4.255` or `5.01`: the draft keeps it, *Submit* explains the error). KRA 9 — tick 9a, 9b or both; untick one to see its data kept but left out of the preview/PDF. Samples: `.work/renders/kra8/normal.pdf`, `kra8/long.pdf`, `kra10/normal.pdf`, `kra9/only9a.pdf`, `kra9/only9b.pdf`, `kra9/normal.pdf` (both), `kra9/long.pdf`, `*/nil.pdf` (regenerate with `manage.py render_sample --kra 8 --kra 9 --kra 10`). Decisions: D-038.

## KRA 19 review (Industrial Visits)

Run `manage.py seed_catalogue`, restart Django. As a Dean open KRA 19: add visits with *+ Add visit* (one report for the period), fill the 19a sections, add matrix rows (cells accept short text such as `3` or `H`; no scale is enforced), and enter the 19b consolidated summary; upload individual feedback forms in the Evidence tab. Check: both matrix columns read "PSO1" (D-012 unresolved), counts rule (forms ≤ participated ≤ class size) only at *Submit*. Samples: `.work/renders/kra19/normal.pdf`, `multi.pdf`, `long.pdf`, `empty.pdf`, `nil.pdf` (regenerate with `manage.py render_sample --kra 19`). Decisions: D-039, D-012.

## KRAs 18, 17, 13 review (industry collaboration)

Run `manage.py seed_catalogue`, restart Django. As a Dean: **KRA 18** — *+ Add mou* per MoU, fill its details, then *+ Add record* for each activity (try type "Other"; leave an evidence Yes/No blank to see —). **KRA 17** — one record per centre/lab; check all source columns appear on one landscape table. **KRA 13** — *+ Add membership* per faculty member; add contribution rows and meetings; leave "To" blank for a continuing tenure. Samples: `.work/renders/kra18/{normal,multi,long,empty,nil}.pdf`, `kra17/{normal,long,empty,nil}.pdf`, `kra13/{normal,multi,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 18 --kra 17 --kra 13`). Decisions: D-040 to D-043.

## KRAs 15, 22, 31, 38 review (table reports)

Run `manage.py seed_catalogue`, restart Django. As a Dean, add records with *+ Add record*: **KRA 15** — switch Category to Faculty to see Programme/Batch become not applicable (NA in the PDF) and enter an Employee ID; leave Registration/DPIIT blank. **KRA 22** — type/domain accept any text (suggestions are the source samples). **KRA 31** — try teams > participants, then *Submit*. **KRA 38** — try an end date before the start date; note the title's percentage is not computed. Samples: `.work/renders/kra{15,22,31,38}/{normal,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 15 --kra 22 --kra 31 --kra 38`). Decisions: D-044 to D-047.

## KRAs 4, 5, 6 and 24 review

Run `manage.py seed_catalogue`, restart Django (frontend changed: rebuild for production). As a Dean: **KRAs 4–6** — *+ Add programme*; answer Yes and add completion records; switch a programme to No and check the preview shows NA and no students (values return when switched back). Each KRA keeps its own data. **KRA 24** — add records; switch a Placement record to Higher Education: the employer/package fields show "NA (entered value kept, not used)", the preview shows only the institution/programme, and switching back restores them. Samples: `.work/renders/kra{4,5,6,24}/{normal,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 4 --kra 5 --kra 6 --kra 24`). Decisions: D-048, D-049.

## KRAs 12, 25, 26 review (awards)

Run `manage.py seed_catalogue`, restart Django. As a Dean: **KRA 12** — fill Coordinator/Date, add award records (an award shared by several people: one record, names one per line); check the four signature labels print as blank lines. **KRAs 25/26** — add a team award as one record with every member on its own line (Team), and an individual award; check the PDF shows one row per award. Level "University (inter-university)" reflects the workbook wording (D-051). Samples: `.work/renders/kra{12,25,26}/{normal,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 12 --kra 25 --kra 26`). Decisions: D-050, D-051.

## KRAs 27–30 review (events organized)

Run `manage.py seed_catalogue`, restart Django. As a Dean, open each of KRAs 27–30: *+ Add event* for several events; check the KRA-specific fields (27 sport, 28 cultural activity, 29 theme, 30 club/forum + semester) and that narratives start empty. KRA 30 shows its per-club/per-semester target unchanged. These are portal formats, not supplied templates (D-052). Samples: `.work/renders/kra{27,28,29,30}/{normal,multi,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 27 --kra 28 --kra 29 --kra 30`).

## KRAs 43, 44, 45 review

Run `manage.py seed_catalogue`, restart Django. As a Dean: **KRA 43** — project-created conference format: enter paper counts (try published > accepted, then *Submit*) and set indexing to "Verified in Scopus" to see the reference become required. **KRA 44** — check the six phases start empty (source text under *Template guidance*) and the 14-item Yes/No evidence list. **KRA 45** — tick SDGs, add resource persons, and note "Implementation/follow-up plan" replaces the undefined "MBU"; photographs/brochure/certificates go to the Evidence tab only. Samples: `.work/renders/kra{43,44,45}/{normal,multi,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 43 --kra 44 --kra 45`). Decisions: D-053 to D-055.

## KRAs 21 and 39 review (adapted formats)

Run `manage.py seed_catalogue`, restart Django. As a Dean: **KRA 21** — add training programmes (try attended > enrolled, then *Submit*); add optional qualifying students and check the PDF labels them supporting information only. **KRA 39** — add a grant with a sanctioned amount and receipts in rupees (e.g. `500000.50`); check sanctioned, received and utilized amounts print separately and nothing is totalled; note the PDF's unit remark about "INR in Lakhs" vs the target. Samples: `.work/renders/kra{21,39}/{normal,multi,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 21 --kra 39`). Decisions: D-056, D-057.

## KRAs 14, 16, 34, 35 review (project-created formats)

Run `manage.py seed_catalogue`, restart Django. As a Dean: **KRA 14** — add a registration and its student team (Submit refuses an empty team). **KRA 16** — add an ambassador; certificate fields may stay blank. **KRAs 34/35** — enter the sanctioned amount and several payments in rupees (e.g. `3000.50`, `1499.99`): each smaller payment is accepted, sanctioned and paid amounts print separately and nothing is totalled; 35 accepts a blank valid-to for life membership. Samples: `.work/renders/kra{14,16,34,35}/{normal,multi,long,empty,nil}.pdf` (regenerate with `manage.py render_sample --kra 14 --kra 16 --kra 34 --kra 35`). Decisions: D-058 to D-061.

## KRAs 40, 41, 42 review (project-created formats) and Phase 4 gate

Run `manage.py seed_catalogue`, restart Django. As a Dean: **KRA 40** — add an audit, findings with Refs (F1, F2) and actions naming those Refs; try an action Ref that does not exist, then *Submit* (refused); choose "Follow-up of an earlier audit" to report progress without a new audit. **KRAs 41/42** — add activities and tick the diversity / constitutional dimensions addressed. Samples: `.work/renders/kra{40,41,42}/{normal,multi,long,empty,nil}.pdf`. Decisions: D-062 to D-064. All 45 KRAs are implemented and tested; the Phase 4 gate stays open until the college reviews every format.

## Phase 5A review (VC assignments and next-year targets)

Run `python backend/manage.py migrate`, restart Django and Vite. Sign in as the VC: **Assignments** — pick 2027-28, *Copy 2026-27 assignments into drafts* (run it twice to see the conflict list), choose a department, edit a target (any text, kept exactly) and *Save*, *Review and finalize* → the summary by department → *Confirm finalize*; finalized rows become read-only and appear for that department's Dean. 2026-27 is shown read-only (locked). **KRAs** — create a KRA by choosing an installed layout and ticking the confirmation. A Dean opening `/vc/assignments` is redirected, and `/api/v1/admin/...` returns 403. API reference: `docs/api.md`. Decision: D-065.

## Browser tests and cleaning old test data

Browser tests: `python e2e/run_isolated.py` (needs the dev PostgreSQL and `npm install`; uses its own `<db>_e2e` database and ports 8001/5174, then removes them). Do not run `e2e/test_browser.py` directly.

Older runs left Phase 5A records in the working database. Review, then remove only what has test provenance (DEBUG only):

```bash
python backend/manage.py cleanup_e2e_data
python backend/manage.py cleanup_e2e_data --execute
```

The report also lists any copy batch (e.g. `audit event 2089 … 584 unedited draft(s)`); remove it only if you confirm it came from a test run: `python backend/manage.py cleanup_e2e_data --execute --copy-event 2089`. Records it calls ambiguous are never deleted. Decisions: D-066, D-067.

## Phase 5B review (VC progress and export)

Sign in as the VC: the dashboard is the progress page. Filter by year, period, department, KRA, status or text; status cards count the filtered dataset. Draft achievements are marked "Unsubmitted draft"; submitted ones show their revision. *Export PDF* downloads every filtered row (not just the visible page). *Review* / *View & history* opens the submission with the submitted revision's achievement and evidence; *← Progress* returns to the same filters. A synthetic sample is at `.work/renders/progress/sample.pdf` (regenerated by `python backend/manage.py test tests.test_phase5b` when the renderer is running). Decision: D-068.
