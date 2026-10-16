# KIET KRA Portal

College-hosted portal for bimonthly KRA reporting: one Vice Chancellor, one Dean per department.
Plan: [`docs/implementation-plan.md`](docs/implementation-plan.md) (v2.0). Status: **Phase 2 pilot (KRA 33) — local only, awaiting acceptance.**
Not production-ready: see [`docs/progress.md`](docs/progress.md) for scope and open items.

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
Visual check of KRA 33 output against the source PDF (needs the renderer):
```bash
.venv/Scripts/python backend/manage.py render_sample
```
```bash
.venv/Scripts/python scripts/compare_pdf.py "reference/templates/KRA 33 Alumni Events organized.docx.pdf" .work/renders/kra33_single.pdf .work/renders/cmp
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
