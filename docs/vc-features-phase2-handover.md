# VC features — Phase 2 handover

Plan: `docs/vc-features-implementation-plan.md` (v2.3) §9–10, executed as the second of two phases by owner instruction
(Phase 1: `docs/vc-features-phase1-handover.md`). Phase 2 = bulk approval with quick preview, durable approved-PDF
artifacts with a worker, and announcements (including the Analytics "pending departments" shortcut). Decisions:
D-075 (bulk), D-076 (artifacts/worker), D-077 (announcements). API: `docs/api.md`. Optional follow-ups in plan §17 are
not implemented.

**Local feature completion ≠ production readiness.** Everything below was run on Windows with the development servers
and isolated synthetic databases. The systemd unit has not been run on Linux; there is still no web/renderer deployment
definition (see "Production gates").

## Setup / upgrade

```bash
.venv/Scripts/python scripts/devdb.py start
.venv/Scripts/python backend/manage.py migrate
.venv/Scripts/python renderer/server.py
.venv/Scripts/python backend/manage.py runserver 127.0.0.1:8000
.venv/Scripts/python backend/manage.py run_artifact_worker
npm --prefix frontend run dev
```

New migrations: `submissions/0003_bulk_approval`, `reports/0002_approval_artifacts` (creates the queue; for each existing
approval it reuses an identical retained approved PDF as READY, otherwise queues a PENDING job — nothing existing is
regenerated, replaced or deleted), `announcements/0001_initial`. After upgrading, the worker renders the queued jobs for
earlier approvals; until then their downloads show "Preparing". Rollback: the migrations reverse cleanly
(`migrate reports 0001`, `migrate submissions 0002`, `migrate announcements zero`), dropping only the new tables; take a
database + private-storage backup first.

## Worker operation and recovery (D-076)

- **Start**: `python backend/manage.py run_artifact_worker` (same code, `DATABASE_URL` and `PRIVATE_STORAGE_ROOT` as Django;
  renderer reachable at `RENDERER_URL`). Several workers may run; jobs are leased with `SELECT … FOR UPDATE SKIP LOCKED`.
- **Stop**: SIGTERM / Ctrl+C finishes the current job, then exits; a second signal releases the lease immediately. A killed
  worker's job is recovered by any worker once `ARTIFACT_LEASE_SECONDS` (default 120 s) has passed.
- **Health**: `python backend/manage.py artifact_jobs --check` (exit 1 when no live heartbeat within
  `ARTIFACT_HEARTBEAT_STALE_SECONDS`, backlog above `ARTIFACT_BACKLOG_WARN`, or failed jobs) and `GET /health/artifacts/`
  (503 when not ok). Logs: logger `kra.artifacts` on stdout (journald under systemd).
- **Failures**: renderer busy/down/invalid output → retry with backoff 30 s, 60 s, 120 s… (≤ 15 min) up to
  `ARTIFACT_MAX_ATTEMPTS` (5); then FAILED. Users see "not available yet; the approval is recorded". Fix the cause, then
  `python backend/manage.py artifact_jobs --retry-failed` (or with job ids).
- **Database outage**: the long-running worker logs, reconnects and continues; `--once` exits with the error.
- **Deployment**: `infra/systemd/kiet-kra-artifact-worker.service` (Restart=always, SIGTERM with 120 s stop timeout,
  hardened, writable only `PRIVATE_STORAGE_ROOT`) and `infra/kiet-kra.env.example` (variable names, placeholders only).
  Run `manage.py migrate` before (re)starting it. The isolated browser runner (`e2e/run_isolated.py`) starts the worker
  alongside Django and Vite, and a browser test verifies an approval's PDF becomes ready without any manual step.

## Implemented paths

Backend
- `backend/apps/submissions/bulk.py`, `bulk_views.py`, models `BulkApproval`/`BulkApprovalItem`, migration `0003_bulk_approval`.
- `backend/apps/submissions/progress.py` — submitted-revision `revision_id`, `nil_reason`, `evidence_count` per row.
- `backend/apps/submissions/services.py` — `review(APPROVE)` enqueues the artifact in its transaction.
- `backend/apps/reports/artifacts.py`, models `ApprovalArtifact`/`WorkerHeartbeat`, migration `0002_approval_artifacts`,
  commands `run_artifact_worker`, `artifact_jobs`; `rendering.build_context(verified_as=…)`; storage keys `approved/…`.
- `backend/apps/submissions/views.py` — approved exports from artifacts (202/503 states); `config/urls.py` routes and
  `/health/artifacts/`; `config/settings.py` `ARTIFACT_*`, `BULK_*`.
- `backend/apps/announcements/` (models, services, views, migration `0001_initial`).

Frontend
- `frontend/src/features/vc/BulkApproval.tsx` (bulk panel, quick-preview drawer), `VCDashboard.tsx` (selection, context,
  resume), `PendingNotice.tsx` + `Analytics.tsx` (shortcut).
- `frontend/src/features/announcements/` (`VCAnnouncements.tsx`, `DeanAnnouncements.tsx`, `common.tsx`).
- `frontend/src/components/ui.tsx` (Announcements nav, Dean unread badge), `icons.tsx` (bell), `App.tsx`, `index.css`
  (phone layout of the selection column), `features/dean/DeanDashboard.tsx` (notices panel).

Infrastructure / tests
- `infra/systemd/kiet-kra-artifact-worker.service`, `infra/kiet-kra.env.example`, `e2e/run_isolated.py` (worker process).
- New: `backend/tests/test_vc_bulk.py`, `test_vc_artifacts.py`, `test_vc_worker_process.py`, `test_vc_announcements.py`;
  `test_vc_migration.py` (Phase 1 → Phase 2 upgrade); updated `test_phase6a.py` (new VC-only routes; approved PDF from the
  worker), `test_reports.py` (approved label from the artifact); browser `test_phase2_bulk_approval_preview_artifacts_and_announcements`.

## Validation (actual)

| Command | Result |
|---|---|
| `python backend/manage.py test tests --parallel 1` (renderer on :8790), final code | **Ran 546 tests, OK**, 0 skipped |
| `python e2e/run_isolated.py` (isolated DB/media, Django + Vite + **artifact worker**), final code | **Ran 28 tests, OK** |
| `npx tsc -b`, `npm run build` (frontend) | OK (Vite warns that the bundle exceeds 500 kB) |
| Focused: `tests.test_vc_bulk` 5, `tests.test_vc_artifacts` 7, `tests.test_vc_worker_process` 1, `tests.test_vc_announcements` 5, `tests.test_vc_migration` 2 | all OK |

Covered: 180-report all-filtered manifest processed 50/50/50/30 with one confirmation and accurate progress; reports
submitted after selection not added; manifest cap refused without truncation; selection exclusions; individual approval,
resubmission (newer revision) and a database error during a run → Skipped / Conflict / Failed with correct reasons and no
duplicate decision; retry via a new confirmed manifest; double confirm; repeated process after completion; expiry;
interruption + resume from a new session; ownership (404) and Dean refusal (403); two concurrent "tabs" on real connections
(`TransactionTestCase`, threads) → each of 60 items approved exactly once. Artifacts: approval with the renderer down;
202/HTML bounded-refresh processing state; worker output with the frozen reviewer label after a later return and an
account rename; backoff, permanent failure (503), operator retry; lease expiry recovery, discarded late result, graceful
release; `run_artifact_worker --once`, heartbeat and `/health/artifacts/`; legacy approval reusing a retained PDF; quick
preview = HTML only with the renderer mocked out (never called). A **real worker subprocess** consumed a committed job
automatically, was killed mid-render and a restarted worker finished it (attempts = 2, one artifact, file in the shared
storage). Announcements: draft invisibility, all/selected audiences, non-recipient detail/read/history 404, list never
marks read, content edits unread (counted once), pin/expiry/audience edits keep read state, added and re-added departments
unread, removed department loses access, stale read 409, expiry and withdrawal, version conflicts, plain-text/link
validation, pending-departments shortcut (only opened periods, draft only, eligibility revalidated, no grants created).
Upgrade from the Phase 1 schema keeps submissions and existing PDFs and queues/reuses artifacts. Browser: quick preview
with *Next report* and no `/export/` request, selection kept; 2 selected + 58 all-filtered approvals; the running worker
produced the approved PDF (text checked); ECE-only notice hidden from CSE, unread badge, read on open, unread after edit;
shortcut draft; no horizontal overflow at 375 px on the new pages. Screenshots of the dashboard selection, preview drawer,
bulk result, announcement editor, Dean dashboard/notice and pending draft were inspected; fix made: the VC's seven header
links now always use their own row (one row overflowed at 1536 px).

Not executed: the systemd unit on Linux, Gunicorn, production timeouts/latency for 50-item batches, real screen readers.

## Unresolved / notes

- Behaviour change (D-076): an approved revision that was later returned now downloads its original approval PDF
  ("Verified by VC - name") instead of the former on-demand "Historical revision N: … (later returned/superseded)" label.
  The revision history in the review page still shows the return.
- Bulk approval processes up to 50 items per request (database-only). Request latency against production timeouts has
  not been measured; reduce `BULK_BATCH_SIZE` if needed.
- The VC now has seven header links; they always sit on their own row under the logo/user line.
- Frontend bundle is now above Vite's 500 kB warning (no code splitting); functional, but worth splitting later.
- Quick preview uses the existing 750 ms debounced HTML preview; no response-time target was measured.

## Manual review checklist

1. Migrate a copy of the real database; check existing reports, grants and approved PDFs are unchanged; run the worker and
   confirm earlier approvals' PDFs become available.
2. VC dashboard → a period with reports awaiting review: open *Quick preview*, use *Next report*, close with Esc; the
   selection is kept; nothing is generated until *Download exact-revision PDF*.
3. Select a few reports → *Approve selected* → review → approve. Then *Approve all matching filters* with more than 50
   reports and watch "Processed 50 of N" until finished.
4. While a run is pending confirmation, approve one report individually in another tab and resubmit another as a Dean:
   the run reports them as Skipped / Conflict, never approving the newer revision.
5. Close the tab mid-run, sign in again → *Resume*.
6. Stop the renderer, approve a report (works), download its PDF (Preparing), start the renderer: the PDF appears. Return
   the report and rename the VC account: the approved revision's PDF still shows the original approval.
7. Announcements: publish one to all departments and one to CSE only; ECE cannot open the CSE notice by URL; pin/unpin and
   change expiry/audience without resetting read state; add ECE (unread for ECE only); edit text twice (one unread);
   withdraw.
8. Analytics → a closed period → *Announce to pending departments* → draft → review recipients → publish.

## Production gates (still open)

- Web, renderer and database deployment definitions (Gunicorn/Nginx or Compose) do not exist yet; only the worker unit is
  provided. Execute and verify the unit on the target Linux host (restart, shutdown, journald logs, storage permissions).
- Shared cache for login throttling before running more than one Gunicorn worker (unchanged from Phase 6).
- Backups/restore drill including the private storage (`approved/` files are now retained artifacts).
- Monitoring wired to `/health/artifacts/` or `artifact_jobs --check`.
- Institutional acceptance of the 45 report formats and of these VC features.
