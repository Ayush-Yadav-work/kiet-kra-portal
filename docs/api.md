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
| `GET submissions/<id>/`, `PATCH …/draft/`, `POST …/validate/`, `POST …/preview/`, `GET …/export/`, `POST …/submit/`, `POST …/review/`, `GET …/history/`, `POST …/reopen-requests/` | Dean / VC as applicable | Report workflow |
| `GET/POST submissions/<id>/evidence/`, `GET/DELETE evidence/<id>/`, `GET evidence/<id>/download/` | Dean / VC | Evidence |
| `GET reopen-requests/`, `POST reopen-requests/<id>/decision/`, `GET reopen-grants/active/`, `GET progress/` | VC (Dean: own) | Review administration |

## Phase 5A — VC administration (D-065)

Every endpoint below is **VC-only** (Deans get 403, anonymous 401/403). Every write is audited.

| Method & path | Body | Result / rules |
|---|---|---|
| `GET admin/templates/` | — | Installed template versions `{key, version, title, problem, used_by_kras}`; `problem` is non-null when the layout file is missing or the schema is unusable |
| `GET admin/kras/` | — | All KRAs with `active` and `default_template` (KRAs 1–45: the template of their latest assignment) |
| `POST admin/kras/` | `{title, nba_ref?, naac_ref?, number?, template_key, template_version, confirm_layout: true}` | 201 + KRA. Stored as `"KRA <n>: <title>"`; number defaults to the next free one. 400 when the template is not installed or unusable, when `confirm_layout` is not `true` (the VC confirms the activity fits that existing layout), or the number is taken. Audit `kra.create` |
| `GET admin/years/` | — | `{label, start_date, locked, finalized_assignments, drafts_pending, drafts_finalized}`; a year is locked once it has started |
| `GET admin/drafts/?year=&department=` | — | Draft assignments `{id, department, kra, target_text, template, copied_from_year, finalized}` |
| `POST admin/drafts/` | `{year, department, kra, target_text, template_key?, template_version?}` | 201 + draft (template defaults to the KRA's). 409 `year_locked`, 409 `conflict` when a draft or finalized assignment already exists (never overwritten). Target text stored exactly. Audit `assignment_draft.create` |
| `PATCH admin/drafts/<id>/` | `{target_text?, template_key?, template_version?}` | 200. 409 `finalized` once finalized; 409 `year_locked`. Audit `assignment_draft.update` |
| `DELETE admin/drafts/<id>/` | — | 204 for an unfinalized draft; 409 once finalized. Audit `assignment_draft.delete` |
| `POST admin/years/<label>/copy/` | `{source_year}` | `{created, conflicts:[{department, kra, reason}]}`. Copies the source year's finalized assignments (active departments/KRAs) into drafts; existing drafts and finalized assignments are reported, never overwritten; repeat calls create nothing. Source must be earlier; target must not have started. Audit `assignments.copy` |
| `POST admin/years/<label>/finalize/` | `{expected_pending}` | `{finalized}`. One transaction with the year row locked: every pending draft becomes an operational assignment. 409 `nothing_pending` (double click), 409 `stale` (count changed since review), 409 `conflict` (an assignment already exists — nothing finalized). Audit `assignments.finalize` |

There is no endpoint that edits or deletes an operational assignment; the model also rejects target/template changes.
