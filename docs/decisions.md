# Decision log

Plan = `docs/implementation-plan.md` (v2.0). Entries are routine technical choices or recorded assumptions; items marked
**college** need institutional confirmation before production but do not block local development.

| ID | Decision | Reason / status |
|---|---|---|
| D-001 | Local dev uses real PostgreSQL 16 from the `pgserver` wheel's bundled binaries (`scripts/devdb.py`), bound to 127.0.0.1 with a generated password. Production uses the college's PostgreSQL. SQLite is never used. | No PostgreSQL installed on the dev machine and no admin install required. Same engine as production |
| D-002 | Python 3.11 venv in `.venv`; Node 24 for the frontend. | 3.11 has wheels for every dependency incl. pgserver; Django 5.2 LTS supports it |
| D-003 | 13 departments keyed by workbook sheet code. `KSOM` is the single code for the sheet titled "MBA"; full names are proposals. **college** | Plan Phase 0 asks for canonical names before final seed |
| D-004 | Targets are stored as text exactly as displayed by Excel (General format: `3.0` → `3`); strings kept byte-for-byte. | Plan 2.2: keep target strings intact |
| D-005 | KRA activity text = `Instructions` sheet, byte-for-byte. | 12/13 sheets identical; ASH differs only in whitespace |
| D-006 | Seed contains definitions, targets, departments, years and periods only — no achievements, people or credentials. Accounts are provisioned by `manage.py provision_user` (prints a one-time random password, forces change). Demo users only via `manage.py seed_demo`, refused when `DEBUG` is off. | Plan 1.6, 10 |
| D-007 | Reporting periods use `[opens_at, closes_at)` at 00:00 Asia/Kolkata, stored in UTC; all 6 periods for 2026-27, 2027-28 and 2028-29 are seeded. Assignments only for 2026-27. | Plan 2.2–2.3 |
| D-008 | Reviews, reopen requests and grants live in the `submissions` app (not a separate `reviews` app). | One workflow with shared row locks/transactions; avoids cross-app circular imports |
| D-009 | Renderer = stdlib `ThreadingHTTPServer` + N worker threads, each owning one Playwright sync Chromium (N = `RENDERER_POOL`, default 2). Jobs queue with a bound; full queue → 503 "busy". Only `127.0.0.1`. Every non-`data:` request is aborted. | Plan C4, C12 without adding a web framework |
| D-010 | Report font: Tinos (SIL OFL-1.1, metric-compatible with Times New Roman) embedded as base64 `@font-face`; logo PNG extracted from the supplied KRA 33 PDF and embedded as a `data:` URI. | Templates use Times; Times itself is not redistributable. C12 |
| D-011 | KRA 33 adaptations: (a) page-4 Date/Signature overflow merged into the signature block; (b) source boilerplate in sections 2, 3, 7, 8 shown as editor guidance, not prefilled report claims; (c) "Type of Activity" becomes a select of the four listed types; (d) section 4 becomes a checklist of the 12 listed activities plus "other"; (e) section 9 Yes/No values are entered by the Dean, never inferred from uploaded evidence; (f) signature lines stay blank lines — portal adds textual verification only; (g) multiple events repeat sections 1–9 inside one PDF with a period summary on top. | Plan 5.2, 3.2, 3.3 |
| D-012 | KRA 19a PO/PSO matrix duplicate `PSO1` will render as PSO1/PSO2 with a note. **college** | Phase 4; documented, not silent |
| D-013 | KRA 33 minimum evidence proposal: at least one item in each of *Event Notice/Invitation*, *Attendance Sheet*, *Photographs*; other 10 categories optional. Nil needs none. **college** | Plan 3.2 asks for a reviewed minimum set |
| D-014 | PDF header (logo + rule) and footer (`Page N \| M` + verification label) use Chromium header/footer templates; the HTML preview shows the header once. | Repeats on every page exactly like the source |
| D-015 | Private files live under `PRIVATE_STORAGE_ROOT` (dev: `.work/private/`), random UUID keys, streamed only through authorised views. | Plan 3.2, 10 |
| D-016 | Login throttling: 5 failures / 15 min per (portal, username) and 20 / 15 min per IP, cache-backed. | Plan 2.1.1, 10 |
| D-017 | Submission rows are created only by Dean actions: opening the workspace while the period (or a grant) is editable, or a reopen request. A closed period with no row is read-only with "Request reopening". | Plan 4 / C2 |
| D-018 | Template schema is JSON (`backend/apps/reports/schemas/<key>_v<n>.json`) loaded into `TemplateVersion` by the seed; backend validates, frontend renders generically from it. Assignments for KRAs without a template yet have `template_version = NULL` and show "Template pending (Phase 4)". | Plan 8.1–8.3 |
| D-019 | Evidence: PDF/JPEG/PNG verified by magic bytes; Drive links must be `https://drive.google.com/…` or `https://docs.google.com/…`; 20 MB per file, 100 MB active, 500 MB history — env-configurable. Malware scanning: not available locally (recorded honestly). | Plan 3.2, C5, C6 |
| D-020 | Frontend dev server (Vite, port 5173) proxies `/api` to Django (8000) so cookies/CSRF are same-origin. Production serves the built SPA from the same origin. | Plan 10 |
| D-021 | API errors use `{code, message, field_errors, request_id}`; 404 (not 403) for objects outside the Dean's department to avoid confirming existence. | Plan 9 |
| D-022 | Login/logout endpoints are wrapped in `csrf_protect` (DRF skips CSRF for anonymous requests) to prevent login CSRF. | Found by test during Phase 1 |
| D-023 | Verification labels: current export shows "Verified by VC - name" only while Approved; an explicit revision export keeps its approval as "Historical revision N: Verified by VC - name (later returned/superseded)". | Plan 4, 8.11 |
| D-024 | Report fonts embed the Latin subset only; non-Latin names fall back to server system fonts — install Noto (incl. Devanagari) on the server. | Keeps preview payload small; verify in Phase 6 |
| D-025 | Submission header's status shows Draft as soon as the first autosave succeeds (client view of the C11 rule; server remains authoritative). | UX consistency |
