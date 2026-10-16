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
