# VC features — Phase 1 handover

Plan: `docs/vc-features-implementation-plan.md` (v2.3), executed in two phases by owner instruction. Phase 1 = annual
assignments + progress analytics/department comparison. Phase 2 has **not** been started. Decisions: D-073, D-074. API: `docs/api.md`.

## Setup / upgrade

```bash
.venv/Scripts/python scripts/devdb.py start
.venv/Scripts/python backend/manage.py migrate
.venv/Scripts/python backend/manage.py seed_catalogue
.venv/Scripts/python renderer/server.py
```

New migrations: `catalogue/0003_vc_phase1_allocations` (draft/assignment fields; back-fills `source_target`/`source_year`
from `copied_from`) and `submissions/0002_publication_grant` (grant source `PUBLICATION`, three-way constraint, uniqueness).
Both reverse cleanly (tested). Existing assignments keep `effective_start_period = NULL` = applies to all periods.

## Implemented paths

Backend
- `backend/apps/catalogue/allocations.py` — allocation service: year state, start options/72-hour rule, `applicability()`, copy plan/copy, add departments, edit, bulk target, remove/restore, finalise preview (signed token) and finalise (locks, idempotent retry, publication grants).
- `backend/apps/catalogue/admin_views.py`, `backend/config/urls.py` — VC admin routes (KRAs read-only).
- `backend/apps/catalogue/models.py`, `backend/apps/submissions/models.py` + the two migrations.
- `backend/apps/submissions/services.py` — `is_untouched`, `classify`, `not_applicable` guard on create/edit/submit/reopen; `views.py`, `scope.py`, `progress.py` expose/respect applicability.
- `backend/apps/submissions/analytics.py` (`read_snapshot`, `parse`, `load`, `compute`, `dataset`), `analytics_views.py` (API, CSV, PDF), `backend/apps/reports/rendering.py` (`analytics_pdf_parts`), `backend/templates/reports/analytics.html`.

Frontend
- `frontend/src/features/vc/AdminAssignments.tsx` (Annual assignments), `Analytics.tsx` (new), `AdminKRAs.tsx` (read-only).
- `frontend/src/features/dean/DeanDashboard.tsx`, `report-builder/Workspace.tsx`, `achievements/AchievementTab.tsx` — Not assigned / Not due.
- `frontend/src/components/ui.tsx` (VC nav: Analytics; header row break for the VC below 2xl), `App.tsx`, `api/types.ts`.

Tests
- New: `backend/tests/test_vc_assignments.py`, `test_vc_analytics.py`, `test_vc_snapshot.py` (TransactionTestCase), `test_vc_migration.py`.
- Ported to the new API: `test_phase5a.py`, `test_phase5b.py`, `test_phase6a.py`, `test_cleanup_e2e.py`, `tests/base.py` (`finalise` helper).
- Browser: `e2e/test_browser.py::test_phase5a_vc_assignment_workflow` replaced by the Phase 1 flow.

## Validation (actual)

See `docs/validation.md` → "VC features Phase 1": backend 527 OK / 0 skipped with the renderer; isolated browser suite 27 OK; frontend `tsc -b` + build OK.

## Unresolved / notes

- The 72-hour threshold and finalisation use server time at confirmation; a review left open across the threshold returns `stale_preview` (by design) and the VC reviews again.
- Analytics exports above 5,000 slots are refused (`too_many_rows`); the full institution for a full year is 585 × 6 = 3,510 slots, so current data fits.
- The VC header keeps its six links on a second row below 1536 px (single row at 2xl). Owner may prefer a different arrangement.
- Policy questions from 6A are unchanged. Institutional acceptance of the 45 formats is still pending.
- Not checked: production (Linux/Gunicorn) behaviour, real screen readers (accessible names verified via Playwright roles/labels only).

## Manual review checklist

1. Migrate + seed an existing copy of the database; confirm existing 2026-27 assignments and reports are unchanged.
2. VC → Annual assignments → 2027-28 → Copy previous year setup: check the review lists, create drafts, run it again (nothing new).
3. Edit a target with symbols/line breaks; reload — text is exact; *Changed targets* shows it.
4. Remove a draft, check *Removed*, restore it; tick an *Unallocated* department and allocate.
5. Select some drafts → Review and finalise → check start period text → Finalise and send; the rows become read-only; others stay editable.
6. Sign in as that Dean: only finalised targets appear, from their start period; earlier periods say "Not assigned for this period".
7. VC → Analytics: switch scopes, pick a period, a KRA and two departments; compare counts with the dashboard; export PDF and CSV and compare the totals.
8. Check the KRAs page is read-only.

## Phase 2 starting points (not started)

- **Bulk approval + quick preview**: add a selectable review queue next to `frontend/src/features/vc/ReviewPage.tsx` / the VC dashboard; reuse `classify()` and the decision service in `backend/apps/submissions/services.py` (per-item optimistic `edit_version`, one audit event per decision).
- **Approved-artifact jobs/worker**: build on `backend/apps/reports/rendering.py` + `GeneratedDocument` and the bounded renderer (`renderer/server.py`); no worker process exists yet.
- **Announcements, pinned notices, pending-department shortcuts**: no models/routes exist; the pending-department list can reuse `analytics.dataset()` buckets (NOT_SUBMITTED/DRAFT/RETURNED per department).
- Plan sections: see the Phase 2 parts of `docs/vc-features-implementation-plan.md`.
