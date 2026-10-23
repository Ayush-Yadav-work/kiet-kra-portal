# API reference

All endpoints are under `/api/v1/`, use the session cookie plus the `X-CSRFToken` header for writes, and return errors as
`{code, message, field_errors, request_id}` (D-021). Objects outside the caller's scope return 404.

## Existing endpoints (Phases 1–4)

| Method & path | Who | Purpose |
|---|---|---|
| `GET auth/csrf/`, `POST auth/dean/login/`, `POST auth/vc/login/`, `POST auth/logout/`, `GET auth/me/`, `POST auth/change-password/` | all | Session and account |
| `GET years/`, `GET periods/?year=`, `GET departments/`, `GET kras/`, `GET templates/<key>/<version>/` | Dean, VC | Catalogue reads (Dean: own department; templates only when assigned) |
| `GET assignments/?year=&period=` | Dean (own department), VC (all) | Finalized assignments with the period's submission summary and `latest_reopen_request` (the report's newest reopening request for that period: `{id, state PENDING|APPROVED|DENIED, reason, requested_at, decided_at, decided_by, decision_reason, kra_number, period, …}` or null; one query for all rows); also the VC's read-only view of past years |
| `GET/POST assignments/<id>/periods/<period>/`, `POST …/reopen-requests/` | Dean | Open/create the workspace row; request reopening |
| `GET submissions/<id>/` (its `current_revision` carries the submitted achievement, remarks, Nil and evidence manifest), `PATCH …/draft/`, `POST …/validate/`, `POST …/preview/`, `GET …/export/`, `POST …/submit/`, `POST …/review/`, `GET …/history/`, `POST …/reopen-requests/` | Dean / VC as applicable | Report workflow |
| `GET/POST submissions/<id>/evidence/`, `GET/DELETE evidence/<id>/`, `GET evidence/<id>/download/` | Dean / VC | Evidence |
| `GET reopen-requests/`, `POST reopen-requests/<id>/decision/`, `GET reopen-grants/active/` | VC (Dean: own) | Review administration. Denying needs a non-blank `reason` (400 otherwise); a denial creates no grant and changes no report |
| `GET progress/?year=&period=&department=&kra=&status=&search=&page=&page_size=` | VC only | Phase 5B (D-068): `{filters, counts, assigned, total, page, page_size, results}`; counts cover all filters except status; rows carry `display_status`, `status_label`, exact `target_text`/`achievement_text`, `is_nil`, `achievement_source` (`submitted`/`draft`/`none`), `revision_sequence`, `submitted_at`, `changed_since_submission`. 400 `invalid_filter` (period not in year, unknown status/department/KRA), 400 `too_many_rows` (> 5,000). Page size 10–100 (default 50) |
| `GET progress/export/?…same filters…` | VC only | PDF of **all** filtered rows (A4 landscape, repeating header, filters, counts, generation time); `attachment`, `Cache-Control: private, no-store`, not stored. 503 `pdf_busy`/`pdf_unavailable`, 502 `pdf_failed` from the renderer |

## Year/semester fields, Dean name and Nil date (D-079)

Applied to every stored template version at read time by `apps/reports/capabilities.py` (the `templates/<key>/<v>/`
schema, draft validation, submission validation, preview and PDF all use the same layer).

| Template | Field | Behaviour |
|---|---|---|
| KRA 1, 2, 3, 11, 19, 23 | `year_semester` ("Academic Session / Year/ Semester") | `term`: Year of study + Semester dropdowns; printed as `<academic year> / <year> / <semester>` |
| KRA 19 | `courses.year_semester` column | `term`: Year of study + Semester |
| KRA 44 | `semester` ("Semester/Year") | `term`: Year of study + Semester |
| KRA 7 | `semester` | `term`: Semester only (Odd/Even) |
| KRA 1, 2, 3, 11, 19, 23 | `hod` ("Head of the Department") | `auto: dean_name`, read-only |
| KRA 44 | `hod_name` ("Head of Department/Dean name") | `auto: dean_name`, read-only (optional) |
| KRA 7–10, 33 sign-off lines; Nil reports | "Head/Dean:" | printed from the revision's Dean-name snapshot |

- A `term` value is `{"year": "<option>", "semester": "<option>"}` (KRA 7: `{"semester": …}`); options come in the schema
  `parts`. Year-of-study options follow the Dean's department (KSOM, MCA: 1st–2nd Year; others 1st–4th Year); semesters are
  "Odd Semester" / "Even Semester". Drafts accept blanks, partial selections and old free text (a string, or
  `{"legacy": "…"}`); submission needs every part selected.
- `submissions/<id>/` (Dean) returns `payload` with old free text mapped when it names exactly one year/semester consistent
  with the options, otherwise as `{"legacy": "<text>"}` (shown for correction, never discarded). The stored draft changes
  only when the Dean saves. It also returns `dean_name` (profile full name, `""` when missing; always `""` for the VC).
- `auto` fields are ignored by validation and blanked on save; the printed name comes from the revision snapshot
  (`snapshot.dean.name`, set from the submitting Dean on submit) or, for drafts, the department's active Dean.
  `validate/` and `submit/` return `field_errors.dean_name` when the profile has no full name and the report is Nil or has a
  required Head/Dean field.
- Nil reports print "Head/Dean: <name>" and "Date: <revision submitted_at as an IST date>", e.g. "2 October 2026". Draft:
  "Set on submission"; correction draft: "Set on resubmission (previous submission: …)". Saving, previewing, exporting,
  approving or regenerating never changes it. `history/` shows the snapshot name.
- Not converted (different meaning): academic-year auto columns, KRA 9 passing years, KRA 14 "Programme / Year", KRA 15
  batch/year of establishment, KRA 21 year of qualifying, KRA 30 semester (already Odd/Even), KRA 13 "Head of Department /
  Competent Authority" and chairperson, coordinators, all event/report dates.

## Draft privacy (D-078)

The Vice Chancellor never sees a Dean's unsubmitted work. Enforced in the backend for every VC-facing route:

- A report that has never been submitted — untouched or a saved draft — is **Not submitted** for the VC everywhere
  (`progress/` rows, counts and PDF export; `analytics/` buckets, matrix, details, PDF/CSV; `assignments/` summaries;
  bulk-approval selection and reasons; the pending-departments shortcut). There is no Draft status, count or filter for the
  VC; an old `status=DRAFT` filter is treated as `NOT_SUBMITTED`. Such rows carry no submission id, achievement, Nil flag,
  edit version or "edited after submission" flag.
- VC submission-scoped endpoints (`submissions/<id>/`, `…/history/`, `…/preview/`, `…/export/`, `…/evidence/`, `…/review/`,
  `evidence/<id>/download/`) answer **404** for a never-submitted report, exactly as for one that does not exist.
- For submitted reports the VC sees only the submitted revision: detail values (`payload`, achievement, remarks, Nil),
  other periods' entries, preview and the current PDF come from the current revision (`edit_version` is `null`). After a
  rejection or return the status stays Rejected / Returned and the Dean's corrections stay private until resubmission.
  Evidence lists show the current revision's manifest; downloads are allowed for files in any submitted revision.
- Reopening requests stay visible and decidable, including for reports never started; `reopen-requests/` rows carry
  `submitted` (whether a submitted version exists to open) and no draft content.
- Deans are unaffected: their dashboard, `assignments/`, workspace, autosave, conflicts and downloads still show Draft.

## VC administration — annual assignments (Phase 5A, replaced by VC Phase 1; D-065, D-073)

Every endpoint below is **VC-only** (Deans get 403, anonymous 401/403). Every write is audited per draft
(`assignment_draft.create|update|remove|restore`), plus `assignments.copy` / `assignments.finalise` on the year.
Allocation states: **Unallocated** (no row), **Draft**, **Removed** (draft with `removed_at`), **Finalised** (an `AnnualAssignment`).
`items` everywhere is `[{id, edit_version}]` (≤ 1000, UUIDs validated); a changed `edit_version` is a 409 `conflict` with a `conflicts` list.

| Method & path | Body | Result / rules |
|---|---|---|
| `GET admin/templates/` | — | Installed template versions `{key, version, title, problem, used_by_kras}` |
| `GET admin/kras/` | — | Installed KRAs with `active`, `installed`, `default_template`. **Read-only**: `POST` is 405 — new KRAs and report templates are installed by developers (seed/migration), never by the VC |
| `GET admin/years/` | — | Years with `state` (`preparation`/`active`/`closed`) and draft/removed/finalised counts |
| `GET admin/allocations/?year=` | — | `{year, previous_year, departments, kras, allocations[], start, server_time}`; each allocation `{id, assignment_id, department, kra, state, target_text, previous_target, source_year, edit_version, removed_at, removed_by, finalised_by, finalised_at, effective_start_period}`; `start` = publication timing options at request time |
| `POST admin/drafts/` | `{year, kra, departments:[code…], target_text?}` | 201 `{created:[id], skipped:[{department, reason}]}`. Drafts only for the **listed** departments; prefilled from that department's previous-year finalised target, else `target_text` (may be blank). Never overwrites a draft, never restores a removed one ("use Restore"), never duplicates a finalised one. 409 `template_unavailable`, 409 `year_closed` |
| `PATCH admin/drafts/<id>/` | `{target_text, edit_version}` | 200 + row. Text stored exactly (≤ 500 chars). 409 `conflict` (stale version), 409 `not_draft` (removed/finalised) |
| `POST admin/drafts/bulk-target/` | `{items, target_text, apply?: true}` | Without `apply`: preview `{rows:[{id, department, kra, before, after}]}` (sorted by KRA, department); with `apply: true`: the same rows written in one transaction |
| `POST admin/drafts/remove/` · `POST admin/drafts/restore/` | `{items}` | Marks drafts Removed / Draft again; anything not in the expected state is refused with 409 `not_allowed` and nothing changes |
| `POST admin/years/<label>/copy/?preview=1` | `{source_year}` | Read-only plan `{create, drafts_preserved, removed_preserved, finalised_skipped, unavailable}` |
| `POST admin/years/<label>/copy/` | `{source_year}` | Creates the `create` rows of the same plan (year row locked; a repeat creates nothing). Drafts and removed rows are preserved, finalised pairs skipped |
| `POST admin/years/<label>/finalise/preview/` | `{items, start?: "auto"\|"next"\|"current"}` | `{token, count, kind, choices, choice, effective_start_period, grant, grant_expires_at, applicable_periods, rows[{previous_target, target_text…}]}`. `kind`: `before_year` (P1), `open` (current period, ≥ 72 h left), `near_deadline` (< 72 h: default `next`; `current` = 72-hour publication grant), `final_period` (`current` + grant must be chosen, else 409 `grant_required`). 409 `year_closed`, 409 `conflict` (blank target, inactive department/KRA, template missing, changed version) |
| `POST admin/years/<label>/finalise/` | `{token}` | One transaction, year row and drafts locked: creates the `AnnualAssignment`s (target frozen, `effective_start_period`, `finalised_by/at`) and, for `current` under 72 h, one `PUBLICATION` grant + untouched submission shell per assignment. Retry of a succeeded token → same outcome with `already_finalised: true`. 409 `stale_preview` (period or grant would differ now), 409 `preview_expired` (token > 15 min), 409 `conflict`; 400 `invalid` (token of another user/year). Nothing is partially finalised |

Removed in Phase 1: `POST admin/kras/`, `GET admin/drafts/`, `DELETE admin/drafts/<id>/`, `POST admin/years/<label>/finalize/`.
There is no endpoint that edits or deletes a finalised assignment; the model also rejects target/template/period changes.

**Applicability (Dean side).** Submission detail, period entries, `assignments/` rows and assignment-period views carry
`applicability`: `NOT_ASSIGNED` (period before the assignment's `effective_start_period`), `NOT_DUE` (period not yet open) or
`APPLICABLE`. Creating, editing, submitting or requesting reopening of a non-applicable slot is 409 `not_applicable`.
Legacy assignments (no start period) apply to every period.

## VC analytics (VC Phase 1; D-074)

| Method & path | Result / rules |
|---|---|
| `GET analytics/?year=&scope=period\|ytd\|year&period=<id>&department=<code>…&kra=<n>…&status=&page=&page_size=` | `{as_of, filters, drafts_pending, summary, breakdown, labels, departments, trend, department_trends, matrix, details:{total, page, page_size, results}}`. Completion = **approved applicable report slots ÷ expected applicable slots** (one slot = one finalised assignment in one period at or after its start). `period` = that period; `ytd` = periods opened so far; `year` = all six (future periods counted in the denominator and labelled Not due). 0 expected → rate `null`, label "N/A". `status` filters only `details`. Repeat `department`/`kra` to compare several. 400 `invalid_filter` |
| `GET analytics/export/?kind=pdf\|csv&…same filters…` | The same dataset as a download (`attachment`, `private, no-store`, not stored). PDF: A4 landscape, static CSS charts (no scripts), rendered by the existing bounded renderer (503 `pdf_busy`/`pdf_unavailable`, 502 `pdf_failed`). CSV: UTF-8 with BOM, one row per slot, formula-leading cells neutralised. More than 5,000 slots → 400 `too_many_rows` (narrow the filters; never truncated). The parameter is `kind`, not `format` (reserved by DRF) |

Both run in one `REPEATABLE READ, READ ONLY` transaction owned by the reader (the routes are `non_atomic_requests`); called
inside another transaction the reader raises instead of silently running at a weaker isolation.

## Bulk approval (VC Phase 2; D-075)

VC only; session + CSRF; a manifest belongs to the VC who created it (another user's id is 404). Approval goes through the
same `review` service as a single approval (exact-revision check, row lock, `review_approve` audit, approved-PDF job).

| Method & path | Body | Result / rules |
|---|---|---|
| `POST bulk-approvals/` | `{idempotency_key, scope: "selection", items: [{submission, revision}], filters?}` or `{idempotency_key, scope: "filtered", filters: {year, period, department?, kra?, search?}}` | 201 summary + `excluded` (selected rows not awaiting review / newer revision) + first 50 items. Freezes exact (submission, submitted revision) pairs. `filtered` = every report awaiting review matching the progress filters across all pages (the shown Status filter never widens it). More than `BULK_MANIFEST_CAP` (5,000) → 400 `too_many`, nothing created (never truncated). Same key again → the same manifest. 409 `nothing_eligible` |
| `GET bulk-approvals/` | — | The VC's 20 most recent runs (`resumable` = confirmed, unfinished, within 7 days) |
| `GET bulk-approvals/<id>/?outcome=&page=` | — | Summary `{total, processed, remaining, counts{APPROVED, SKIPPED, CONFLICT, FAILED}, confirmed_at, completed_at, expired, resumable, batch_size}` + items (50 per page) |
| `POST bulk-approvals/<id>/confirm/` | — | Once; repeat is a no-op. 409 `expired` after 15 minutes unconfirmed |
| `POST bulk-approvals/<id>/process/` | — | Processes up to `BULK_BATCH_SIZE` (≤ 50) unprocessed items, one transaction each, claimed with `FOR UPDATE SKIP LOCKED` in order; returns the summary + `batch` outcomes actually committed. Call until `remaining` is 0. Stale revision → `CONFLICT`; no longer Submitted → `SKIPPED`; database error → `FAILED` (others unaffected). 409 `not_confirmed`, 409 `expired` (resume window 7 days) |
| `POST bulk-approvals/<id>/retry/` | `{idempotency_key}` | New manifest (needs its own confirmation) from this run's `FAILED` items whose exact revision is still awaiting review. Conflicts/skips are never retried automatically |

Progress rows (`GET progress/`) now include `revision_id`, `nil_reason` and `evidence_count` of the submitted revision.

## Approved PDFs (VC Phase 2; D-076)

`GET submissions/<id>/export/[?revision=]` is unchanged for drafts and reports awaiting review. When the export is an
**approved** document (the current export of an Approved report, or an explicit revision that received an approval) it is
served only from that approval's retained artifact:

- ready → the PDF (`private, no-store`);
- pending/running → **202** `pdf_processing` with `Retry-After: 5` (JSON when `Accept: application/json`; otherwise a small
  page that refreshes itself at most 24 times, then offers *Try again*);
- failed after the retry budget → **503** `pdf_failed` (the approval stands; an operator retries the job).

Never another revision's file or a Pending-approval PDF. `GET /health/artifacts/` (outside `/api/v1/`) →
`{ok, problems[no_live_worker|backlog|failed_jobs], live_workers, pending, failed, oldest_pending_seconds}`, 503 when not ok
(counts only; restrict to internal monitoring at the proxy).

## Announcements (VC Phase 2; D-077)

| Method & path | Who | Rules |
|---|---|---|
| `GET announcements/?state=DRAFT\|ACTIVE\|EXPIRED\|PUBLISHED\|WITHDRAWN&page=` | VC | All announcements (20 per page) with state, audience, recipients, `read_count` (current version) |
| `GET announcements/?unread=1&page=` | Dean | Active (published, not expired/withdrawn) announcements addressed to the Dean's department, pinned first, then newest; `read` flags and `unread_count`. Never marks anything read |
| `POST announcements/` | VC | `{title ≤200, body ≤10000, audience: {all: true} \| {departments: [codes]}, pinned?, expires_at?}` → 201 draft. Plain text only: HTML tags and non-http(s) links are 400 |
| `GET announcements/<id>/` | both | Dean: 404 unless currently addressed to their department and active. Loading never marks read |
| `PATCH announcements/<id>/` | VC | `{edit_version, …}`; 409 `version_conflict` (with `current`). Published: title/body change → new `content_version` (unread again); audience/pin/expiry-only → read state kept, added departments start unread, removed ones lose access (also to history). 409 `withdrawn` |
| `DELETE announcements/<id>/` | VC | Drafts only (`{edit_version}`); published history is kept |
| `POST announcements/<id>/publish/` | VC | `{edit_version, acknowledge_eligibility?}`. Resolves the audience to a recipient snapshot ("all" = active departments now). A pending-shortcut draft is revalidated: changed eligibility → 409 `eligibility_changed` `{eligible, audience, newly_pending, no_longer_pending}` unless acknowledged |
| `POST announcements/<id>/withdraw/` | VC | Published → withdrawn (leaves Dean views; history kept) |
| `POST announcements/<id>/read/` | Dean | `{content_version}` — the version actually shown; 409 `stale_read` if it changed meanwhile |
| `GET announcements/unread-count/` | Dean | `{unread_count}` (each active announcement at most once) |
| `GET announcements/<id>/revisions/` | both | VC: every revision with audience; Dean: content revisions, only while currently a recipient |
| `POST announcements/recipients-preview/` | VC | `{audience}` → departments it resolves to now |
| `POST announcements/pending-draft/` | VC | `{year, period_ids: [opened periods], departments?, kras?, preview?}` → departments with ≥1 applicable Not submitted / Draft / Rejected / Returned slot in those periods; `preview: true` returns `{eligible, counts, periods, title, body}`, otherwise creates a **draft** (201). Never publishes, never reopens. 400 for unopened periods, 409 `nothing_pending` |

## Development commands (not HTTP)

- `python e2e/run_isolated.py [-k NAME] [--keep]` — browser suite on a disposable database (D-067); also runs the artifact worker.
- `python backend/manage.py run_artifact_worker [--once]` — approved-PDF worker (D-076); `artifact_jobs [--check] [--retry-failed [ID …]]` — queue status, health check, operator retry.
- `python backend/manage.py cleanup_e2e_data [--execute] [--copy-event ID]` — DEBUG only; report or remove browser-test residue with demonstrable provenance (D-067).
- `python e2e/run_perf.py [--seconds N] [--keep]` — Phase 6B local PDF-reliability, failure and mixed-workload measurements on a disposable `<db>_perf` database with its own Django (:8002) and renderer (:8791) (D-070).
