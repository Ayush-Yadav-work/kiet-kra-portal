# API reference

All endpoints are under `/api/v1/`, use the session cookie plus the `X-CSRFToken` header for writes, and return errors as
`{code, message, field_errors, request_id}` (D-021). Objects outside the caller's scope return 404.

## Existing endpoints (Phases 1–4)

| Method & path | Who | Purpose |
|---|---|---|
| `GET auth/csrf/`, `POST auth/dean/login/`, `POST auth/vc/login/`, `POST auth/logout/`, `GET auth/me/`, `POST auth/change-password/` | all | Session and account |
| `GET years/`, `GET periods/?year=`, `GET departments/`, `GET kras/`, `GET templates/<key>/<version>/` | Dean, VC | Catalogue reads (Dean: own department; templates only when assigned) |
| `GET assignments/?year=&period=` | Dean (own department), VC (all) | Finalized assignments with the period's submission summary; also the VC's read-only view of past years |
| `GET/POST assignments/<id>/periods/<period>/`, `POST …/reopen-requests/` | Dean | Open/create the workspace row; request reopening |
| `GET submissions/<id>/` (its `current_revision` carries the submitted achievement, remarks, Nil and evidence manifest), `PATCH …/draft/`, `POST …/validate/`, `POST …/preview/`, `GET …/export/`, `POST …/submit/`, `POST …/review/`, `GET …/history/`, `POST …/reopen-requests/` | Dean / VC as applicable | Report workflow |
| `GET/POST submissions/<id>/evidence/`, `GET/DELETE evidence/<id>/`, `GET evidence/<id>/download/` | Dean / VC | Evidence |
| `GET reopen-requests/`, `POST reopen-requests/<id>/decision/`, `GET reopen-grants/active/` | VC (Dean: own) | Review administration |
| `GET progress/?year=&period=&department=&kra=&status=&search=&page=&page_size=` | VC only | Phase 5B (D-068): `{filters, counts, assigned, total, page, page_size, results}`; counts cover all filters except status; rows carry `display_status`, `status_label`, exact `target_text`/`achievement_text`, `is_nil`, `achievement_source` (`submitted`/`draft`/`none`), `revision_sequence`, `submitted_at`, `changed_since_submission`. 400 `invalid_filter` (period not in year, unknown status/department/KRA), 400 `too_many_rows` (> 5,000). Page size 10–100 (default 50) |
| `GET progress/export/?…same filters…` | VC only | PDF of **all** filtered rows (A4 landscape, repeating header, filters, counts, generation time); `attachment`, `Cache-Control: private, no-store`, not stored. 503 `pdf_busy`/`pdf_unavailable`, 502 `pdf_failed` from the renderer |

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

## Development commands (not HTTP)

- `python e2e/run_isolated.py [-k NAME] [--keep]` — browser suite on a disposable database (D-067).
- `python backend/manage.py cleanup_e2e_data [--execute] [--copy-event ID]` — DEBUG only; report or remove browser-test residue with demonstrable provenance (D-067).
- `python e2e/run_perf.py [--seconds N] [--keep]` — Phase 6B local PDF-reliability, failure and mixed-workload measurements on a disposable `<db>_perf` database with its own Django (:8002) and renderer (:8791) (D-070).
