# KIET KRA Portal — Final VC Features Implementation Plan

Version 2.3 | 19 October 2026 | Owner-agreed functional scope

Repository location: `docs/vc-features-implementation-plan.md`

## 1. Authority, outcome and execution

This document supersedes versions 1.0, 2.0, 2.1 and 2.2 of this feature plan. It incorporates the owner's final clarifications. Implement the complete scope; milestones organize dependencies and validation, not mandatory approval stops. Continue through independent work automatically. Ask only for a genuinely blocking institutional decision or unavailable external access.

Deliver:

1. Annual KRA assignment preparation with department-specific text targets, previous-year reuse, draft correction and selective finalisation.
2. VC report-approval progress analytics by KRA, department, bimonthly period and academic year.
3. Comparison of two or more departments, with charts, tables and PDF export.
4. Bulk approval of eligible submitted report revisions.
5. College-wide and department-targeted in-portal announcements.

Explicit changes from v1:

- Remove numeric achievement metrics, numeric target configuration, attainment calculations and their scaffolding. Progress means approved reports divided by expected reports.
- Replace unrestricted KRA CRUD with annual assignment and target management. VC cannot create report templates, edit master KRA definitions or delete historical KRAs.
- New KRAs require developer implementation of editor, live preview, validation and PDF support.
- Selected assignments finalise separately. Publication and target locking happen together; drafts remain private to VC.
- Copy previous-year department targets without overwriting drafts or duplicating finalised assignments.
- Full implementation is authorised; do not stop after the audit or each milestone.

This is an implementation specification, not evidence that the repository already implements it. Verify actual code before choosing exact models, paths or commands. Preserve unrelated work. Do not commit, push or deploy without a separate instruction.

### Review corrections incorporated through v2.3

- Finalisation locks individual assignments; July 1 does not freeze unfinished drafts.
- Late publication has an immutable effective start period, reflected in reporting permissions and denominators.
- Existing Draft/Submitted/Rejected/Approved database statuses remain unchanged; Returned is a derived label only.
- The master plan C11 untouched-draft rule applies everywhere.
- Unread counts consider each active announcement once; metadata-only edits preserve existing recipients' read state.
- Bulk approval never synchronously renders PDFs; durable artifact generation preserves approved history.
- PDF charts are static and script-free; analytics uses a single materialised database snapshot.
- Bulk selection spans the whole filtered set; sequential bounded requests process every confirmed item.
- Approved-artifact workers are wired into deployment and local startup, with heartbeat and recovery checks.
- Near-deadline publication has an explicit current/next-period choice and a full 72-hour opportunity when the current period is selected.
- Dean screens share applicability rules; unallocated departments are distinct from saved drafts.
- Review-context columns, changed-target filters, targeted reminder drafts and pinned announcements improve the workflows.
- Snapshot isolation is established in an owned outer transaction and tested with real transaction boundaries; it is never silently skipped inside atomic blocks.
- Quick preview uses server-rendered HTML without invoking Chromium; PDF generation requires an explicit action.
- Assignment-publication grants reuse the required Submission relation with an exact three-way source constraint and partial uniqueness.

## 2. Existing architecture and invariants

Reported stack: Django/DRF, PostgreSQL, React/TypeScript/Vite/Tailwind, session authentication with CSRF, existing internal Playwright PDF renderer. Reuse installed versions, service patterns and approved KIET UI. No stack rewrite or duplicate approval/progress engine.

Verify existing implementation/UI plans, repository instructions, migrations, API documentation, progress, validation and decisions. UI-3 completion is not established by this document. Inspect Git status and actual screens; preserve unfinished UI work.

Preserve:

- One active college-wide VC; one active Dean per department; separate login portals.
- Backend department isolation, including direct-ID access, uploads and exports.
- Installed catalogue of 45 KRAs and department-specific source targets; do not hardcode 45 or 13 in business logic.
- One report slot per finalised assignment and bimonthly period; immutable submitted versions.
- Six configured periods per academic year, existing July–June cycle, Asia/Kolkata display and existing half-open time boundaries.
- Reporting windows, 72-hour scoped reopening and existing rejection/return/resubmission behaviour.
- Report editor/live preview, separate evidence and achievement sections, draft autosave and concurrency protection.
- Separate evidence downloads; evidence is not embedded in report PDFs.
- Pending approval / Verified by VC — [name] labels, Nil reason requirements and audit records.
- Exact target/achievement strings. No automatic parsing or inferred achievement scores.

Existing assigned targets are treated as finalised and immutable during upgrade. A report-window reopening never unlocks an annual target.

## 3. Terms and lifecycle

| Term | Meaning |
| --- | --- |
| Installed KRA | Developer-maintained definition with a working report template/editor/preview/PDF |
| Annual allocation | One academic year + one KRA + one department, containing that department's target |
| Unallocated department | No allocation row for this year/KRA/department; no reporting obligation |
| Draft allocation | VC-only, editable and not yet an obligation visible to the Dean |
| Removed draft | Excluded from that year's planned allocations; restorable before finalisation |
| Finalised assignment | Published annual allocation with immutable target and template reference |
| Report slot | One finalised assignment × one applicable reporting period |
| Approved report | Slot whose current authoritative workflow state is approved |

State transitions: draft → finalised; draft → removed; removed → draft. No finalised → draft, removed or deleted transition in this release.

Academic-year settings must support preparation, active and closed states, reusing existing state/date rules where available. Draft allocations may be created, copied, edited, removed, restored and finalised in preparation or active years. Closed years are read-only for annual setup. Finalised allocations are always locked, regardless of the year state. The restriction concerns changing a published target, not completing an unpublished allocation after July 1. Existing report reopening rules are independent of annual-setup eligibility.

At finalisation, freeze an `effective_start_period` using these rules:

- Before year start: Period 1.
- During an open period with at least 72 hours remaining: current period.
- With fewer than 72 hours remaining: default to the next period if one exists. Show an explicit alternative, “Start in current period and grant 72 hours”. Explain the applicable periods and deadlines before confirmation.
- In the final period, when fewer than 72 hours remain and there is no next period: current-period publication must include the 72-hour assignment-publication grant. Without accepting that scope, leave the allocation unpublished.
- After the academic year closes: refuse new publication. An already granted reporting window may extend past year-end under existing submission/grant rules; it does not reopen annual setup.

For the current-period/72-hour choice, atomically create the finalised assignment, one untouched Submission shell and a grant ending at finalisation time + 72 hours. No grant is created for next-period publication. Do not backdate to closed periods or prorate target text. Final review shows the chosen start period, applicable periods, ordinary deadline and any special grant. A Period 3 start creates four annual slots, even when publication occurred near the end of Period 2.

This requires an explicit extension of the existing ReopenGrant source constraint. Prefer reusing its existing required `submission` FK: `submission.assignment` already identifies the finalised assignment and `submission.period` identifies the granted period. Do not add a redundant `assignment_id` merely for this source. Keep submission non-null for all source types.

Use an explicit three-way database CHECK (adapt field/enum spelling to the repository):

```text
(source = REQUEST AND request_id IS NOT NULL AND review_decision_id IS NULL)
OR (source = REVIEW_DECISION AND request_id IS NULL AND review_decision_id IS NOT NULL)
OR (source = ASSIGNMENT_PUBLICATION AND request_id IS NULL AND review_decision_id IS NULL)
```

Make source non-null with only these allowed values. Add a partial unique constraint/index on `submission_id WHERE source = ASSIGNMENT_PUBLICATION`; do not impose global uniqueness that would block later legitimate REQUEST/REVIEW_DECISION grants. Source type alone is not authorization: create publication grants only inside atomic assignment finalisation, validate the Submission belongs to that exact assignment and effective period, and audit actor/finalisation identity. For other sources, validate referenced request/review decision belongs to the same Submission. Cross-table ownership conditions are enforced by the shared service/appropriate existing database mechanisms; a simple row CHECK cannot verify related-row contents.

Do not fabricate rejection decisions or Dean requests. Migration must replace the old two-way source check, retain existing data and foreign keys, and add the conditional uniqueness constraint. If actual code already introduced a redundant assignment FK, either safely reconcile it or enforce all three nullable-source columns explicitly: REQUEST only request set; REVIEW_DECISION only review_decision set; ASSIGNMENT_PUBLICATION only assignment set. Also verify assignment matches submission.assignment. Do not silently drop populated references during migration.

Existing grant authorization, countdown and expiry must recognise the new source. The shell follows C11 and stays Not submitted until used. Repeated finalisation returns the existing grant and must not extend its expiry. Preserve the normal reopening process after that grant expires.

Use one server timestamp and validate half-open period boundaries. If a confirmation preview crosses a period boundary or the 72-hour threshold before execution, reject it as stale and require a refreshed scope confirmation; never silently change the confirmed start period or grant choice. Already successful retries return their original outcome even after a boundary or year closure.

Do not disable current-year report operations or rewrite historical assignments because of this setup rule. Migrated existing assignments remain operational.

## 4. Annual assignment UX

### 4.1 Entry and year preparation

Provide VC navigation named “Annual assignments”. Select academic year; display its status and counts of draft, removed and finalised allocations. Show editable drafts in preparation/active years, read-only published assignments, and a read-only setup for closed years.

For a preparation or active year, offer:

- “Copy previous year setup”.
- “Send previous year KRAs”.
- “Add installed KRA” for a developer-installed catalogue item not yet in this draft setup.

Both previous-year actions use the same copy/review services. “Send previous year KRAs” is a shortcut to copy or reuse drafts and open final review; it never silently publishes targets.

Default source is the immediately preceding academic year. If absent, show an explicit source-year selector or empty setup. For the first year, reuse existing catalogue/seed targets through the current setup mechanism; do not invent a previous year.

“Add installed KRA” initially opens a department selector without writing allocations for all departments. Create draft rows only for explicitly selected departments when the VC saves. Unselected departments display Unallocated; they are not Removed and do not count as unfinished drafts. A saved draft later deselected uses the explicit Remove action and retains restore history. Copy setup creates drafts only for eligible source assignments, not every available department. Restore reuses a removed row; selecting an unallocated department creates a new row under the same uniqueness rules.

### 4.2 Copy semantics

Copy source-year finalised assignments: installed KRA/template reference, department and that department's exact target. Carry source assignment/year identifiers for comparison and traceability. Do not copy the source effective start period: determine the destination start period at finalisation. Require an earlier source year and an eligible destination year.

Do not copy reports, achievements, evidence, review status, approval signatures/labels, finalisation state or reporting-window grants.

Copy preview must show:

- New draft allocations to create.
- Existing drafts preserved.
- Existing finalised assignments skipped.
- Explicitly removed drafts preserved as removed.
- Unavailable/incompatible templates or inactive departments requiring resolution.

Copy is transactional and repeatable without duplicates. Concurrent copy requests use database uniqueness; retry returns the established outcome. Do not overwrite manually edited drafts or resurrect removed drafts automatically. Restore is a separate visible action. A developer must explicitly provide compatibility handling if the source template is no longer available.

### 4.3 Department selection and targets

Open an installed KRA to view fixed title, instructions and report format. The VC can edit target text and department allocation, not the report definition.

Show department checkboxes and an editable review table:

| Department | Previous-year target | New-year target | State | Actions |
| --- | --- | --- | --- | --- |
| CSE | Exact source text | Editable draft text | Unallocated/Draft/Finalised/Removed | Select/edit/remove/restore as permitted |

Provide “Apply target to selected departments” for explicit bulk draft editing. Show affected departments before replacing their draft values. Never silently replace distinct prefilled targets merely because departments were selected. Finalised rows are disabled and cannot enter a target-edit action.

Support different target strings for different departments. Keep meaningful whitespace and content; reject whitespace-only values at finalisation. Drafts may be incomplete. Show changed target indicators using stored source values, not a mutable lookup into another year's current data.

Provide filters All allocations, Changed targets, Unfinished drafts, Finalised, Removed and Unallocated, with clearly scoped counts. Changed targets compares exact new target text with the stored source target snapshot; source-less new allocations have a separate New indicator. Filtering never silently discards selected rows: show total selected and selected outside the current filter in review.

Selection controls must distinguish selected for editing from selected for finalisation. Explain each action's scope in its label or confirmation. Preserve unsaved edits during filter changes or warn before navigation. Reuse the project's optimistic edit-version approach for concurrent tabs.

### 4.4 Removal and restoration

“Remove from this year's draft” removes only selected draft allocations. A KRA-level remove action affects its draft department allocations and must disclose finalised rows that cannot be removed. Never imply that a partly finalised KRA was removed everywhere.

Keep a Removed view with restore. Restore reuses the removed draft and retained target when valid. Restore never reopens finalised assignments or changes prior years. No cascade deletion of master KRA, template, report, evidence or history.

### 4.5 Finalise and send

VC selects specific draft allocations, possibly grouped by KRA/departments. Final review shows year, KRA, department, old target, new target, proposed effective start period, applicable periods/deadlines and exact allocation count. State that these targets become locked and visible to the selected Deans.

Server preflight checks actor, year eligibility, installed template readiness, department validity, nonempty target, draft versions, effective-period choice and any mandatory 72-hour grant. Return a short-lived confirmation bound to exact allocation IDs, versions and proposed effective periods, or equivalent server-validated mechanism.

Finalise the confirmed selection atomically in a database transaction. Lock rows deterministically and revalidate all conditions. If any selected draft is stale/invalid, finalise none of that selection and return actionable conflicts. This avoids unintentionally publishing a partially checked annual setup. Use a documented selection cap if needed.

Store finalised_by, finalised_at, exact target snapshot, immutable effective start period and immutable template/definition reference. Publishing means Dean portal visibility, not sending email. Repeated submission/retry must be idempotent; a retry after success returns the outcome without a duplicate assignment. Unselected drafts remain editable in preparation and active years.

After finalisation:

- Target, year, department, KRA, effective start period and template reference are locked server-side.
- Dean sees own assignment and may report only in its applicable periods within the existing windows/grants. Enforce applicability in report creation, preview, submission and reopen endpoints, not only dashboard filtering.
- Update the Dean dashboard, report-opening navigation, Achievement tab six-period summary, history links and year/period pickers to use the same applicability service. Periods before effective_start_period show “Not assigned for this period”; hide fill/edit/submit/request-reopen actions. Applicable future periods show Not due with actions disabled until the normal window opens. API responses provide explicit applicability/reason codes so UI does not guess from a missing Submission row. Preserve authorised historical access for migrated records under their retained obligations.
- VC sees who finalised it and when.
- No reassignment/unlock button, API loophole or seed command can change it.

Before and during an academic year, show VC unfinished drafts and explain that unpublished allocations are excluded from Dean obligations and completion denominators. Display draft allocation counts beside analytics to make incomplete setup visible. Show the actual effective period and any granted deadline for late publication; do not assume every active-year assignment starts in the current period. This is an in-app indication, not a new scheduler or notification service.

## 5. Backend design for assignments

Prefer extending the current assignment model if it already supports draft/finalised states. Do not build a parallel catalogue or competing target store.

Conceptual fields (adapt to existing schema): academic_year, kra, department, target_text, state, source_assignment, source_year, source_target_snapshot, template_version, effective_start_period, edit_version, removed_at/by, finalised_at/by, created/updated timestamps.

Required constraints and services:

- Unique `(academic_year, kra, department)` identity across active/removed states; restore rather than duplicate.
- Nonempty target and complete template reference for finalisation.
- FK protection for referenced catalogue/templates and history.
- Centralised edit/remove/restore/finalise service rules shared by APIs, admin and management commands.
- Database constraints for expressible invariants; use the repository's existing database-level immutability mechanism where present. Services/admin paths must not bypass locks.
- Concurrency guard on target edits and copy; finalisation serialised with edit/remove and year closure, effective-period and 72-hour-threshold checks using a single captured server time. Finalisation previews expire when their confirmed period choice or near-deadline/grant conditions change.
- Audit actor, operation, affected IDs, old/new target values as appropriate under existing audit privacy policy, version and timestamps. Never log credentials or evidence contents.

Remove or disable existing VC create/edit/delete-master-KRA endpoints and UI that conflict with this scope. Enforce the restriction in the backend, not just navigation. Preserve developer/operator catalogue installation through controlled software updates. Update old tests/docs to reflect the intentional permission change.

Suggested logical API actions: list/detail annual allocations, copy-preview/copy, edit draft, bulk-target-preview/apply, remove/restore, finalise-preview/finalise. Match existing routing conventions and standard errors; do not duplicate endpoints if current services can be extended.

## 6. Exact progress calculations

### 6.1 Primary metric

`Report approval completion (%) = approved eligible slots / expected eligible slots × 100`

The numerator counts distinct report slots currently approved. Historical revisions are not additional reports. Submitted-awaiting-review, drafts, rejected and returned reports contribute zero to the approved numerator. An approved Nil report counts as an approved report; this does not imply that its target was achieved.

Display `30 of 40 reports approved — 75.0%`. Use one decimal for display, unrounded counts for aggregation. Zero denominator displays “No assignments” or “No applicable reporting periods”, never a fabricated 0% or 100%.

### 6.2 Scope and denominator

Only finalised assignments generate expected slots. Draft and removed allocations are excluded. Respect department/KRA/year filters before computing counts. Do not use a hardcoded count of 45 for every department.

For new annual setups finalised before year start, each assignment requires one report in each of the year's six configured periods. For active-year publication, include only periods at or after its frozen effective start period, including a confirmed next-period start under the near-deadline rule. Example: publication during Period 3 means four full-year slots; once only Period 3 has opened, its YTD denominator is one. Periods before applicability display “Not assigned for this period”, not “Not submitted”. Draft counts are visible separately and excluded from the percentage.

| View | Expected slots | Approved numerator |
| --- | --- | --- |
| One opened bimonthly period | Finalised assignments applicable to that period | Approved slots in that period |
| Year-to-date | Applicable slots in periods whose opening time has arrived, including the current open period | Approved slots in those periods |
| Full academic year | Applicable slots across all six periods, including future periods | Approved slots across that year |

Full-year future obligations intentionally reduce full-year completion until reports are approved. Label future slots “Not due”; do not call them overdue or missing submissions. In period-trend charts future periods are marked Not due, with no fake measured zero. A selected future period can show planned count but approval rate is Not due.

Example: 40 assignments, two periods opened, 60 approved reports: YTD = 60/80 = 75%; full-year = 60/240 = 25%. The full-year denominator is reports, not distinct KRAs.

A legacy midyear assignment requires inspection of existing effective dates/rules. Preserve existing obligations and reports. Do not silently add past obligations or drop existing slots. Reuse explicit effective-period data; if missing and material, document the affected records and resolve that migration rule before declaring their analytics verified. Do not derive legacy applicability from the migration execution time. New active-year publications follow the explicit effective-period rule above; historic obligations are preserved through an evidence-based backfill.

### 6.3 Status and comparison semantics

Keep existing database states Draft, Submitted, Rejected and Approved. Do not introduce a RETURNED enum or change save/resubmit transitions to implement analytics. Return for correction remains Approved → Rejected, with the existing review action recorded.

Use one shared classification function for dashboards, analytics, filters and exports:

| Condition on an applicable, opened slot | Display bucket |
| --- | --- |
| No Submission row | Not submitted |
| Draft with edit_version = 0 and no active evidence | Not submitted (untouched shell, C11) |
| Other Draft | Draft |
| Submitted | Awaiting review |
| Rejected with latest relevant review action RETURN | Returned for correction, a derived label |
| Other Rejected | Rejected |
| Approved | Approved |

Active evidence includes any active supported evidence source, including Drive links, under existing rules. Evidence may not increment edit_version; do not rely on that field alone. Reopening requests/grants do not make untouched shells genuine drafts. Reuse the established C11 predicate and test its removal behaviour.

Determine Returned from the latest relevant decision for the current workflow/revision, not merely the existence of any historical approval. After return → resubmit → reject, display Rejected. Pending resubmission edits retain the current review classification according to existing workflow. If a combined Rejected filter is retained for compatibility, document that it includes returned-for-correction records while chart buckets remain mutually exclusive. A current returned record does not count as approved even when an older approved artifact exists.

Future applicable slots are Not due; earlier non-applicable slots are excluded. Nil and active reopening are supplementary flags, not extra status buckets.

Yearly department completion is sum(approved slots) / sum(expected slots); never average department or period percentages without weighting. KRA annual progress uses the same slot-based rule. Reopening never creates another slot or changes the target.

Status filters may narrow the detail table, but headline approval rates and comparison denominators stay based on selected year/period/departments/KRAs, independent of status filtering. Clearly indicate this to avoid an Approved-only filter incorrectly producing 100%.

Charts show current status grouped by report period. They do not reconstruct status as it existed at an earlier date. Show data generation time. Do not add target attainment, numeric achievement, qualitative rankings or an overall institutional performance score.

## 7. Analytics and comparison UI

VC Analytics screen:

- Academic year, bimonthly/YTD/full-year scope, departments and KRA filters.
- Clear approved/expected/remaining counts and approval completion card.
- Workflow breakdown with consistent labels and colours.
- Department comparison bars with approved/expected labels.
- Bimonthly approval trend; future periods visibly Not due.
- Department × KRA table: period status, or annual approved/expected fraction.
- Detail table with department, KRA, period, exact target, achievement text, status and applicable Nil/reopening indicators.

Comparison allows two or more departments, including all currently available departments. Show both counts and rates so smaller assignment totals are not mistaken for worse performance. Provide the same year/scope/KRA filters and PDF export. No assignment is N/A, not zero achievement.

Use a readable layout for many departments: horizontal bars and paginated/scrollable labelled detail tables. Charts must have accessible table equivalents, labels/tooltips, keyboard-accessible controls, distinct series and no colour-only meaning. Keep the established KIET tokens and shared controls. Include loading, empty, error and retry states; cancel/ignore stale responses when filters change.

Reuse a chart dependency if installed. If a new dependency is necessary, verify official compatibility and choose one library; record the reason. Do not add external analytics/chart services. No large animation or dashboard redesign beyond these features.

## 8. Shared data service and exports

Use a single backend analytics service for screen counts, chart data, comparison tables, CSV and PDFs. Reuse existing progress/approval logic. Validate year-period relationships and authorised filter IDs. Build one materialised consistent dataset per request and derive every count, series and table from it. Under PostgreSQL READ COMMITTED, transaction.atomic() alone does not give successive SELECT queries the same snapshot. Do not issue unrelated .count() queries for headline cards, chart groups and export rows.

Default implementation: use a read-only REPEATABLE READ transaction, configured before its first relevant query. Fetch finalised assignments including required metadata, configured reporting periods, and current Submission rows annotated with relevant review action and active-evidence existence using a small bounded number of ORM queries (typically three core reads; extra metadata reads must share the snapshot). Materialise everything inside the transaction. Build applicable `(assignment_id, period_id)` slots in Python and join submissions through a dictionary keyed by that pair. Include expected slots with no Submission row; exclude pre-applicability slots. Aggregate all cards, charts and tables from these same materialised tuples.

Do not force an assignment × period cross join with a non-FK composite join through ordinary Django select_related/prefetch machinery. A well-tested single SQL statement is an optional alternative, not the required approach. If used, preserve missing slots and avoid one-to-many duplication through EXISTS/subqueries. No lazy ORM reads after the snapshot closes. Capture one as_of time for all business-time classification. Keep the transaction short and close it before PDF rendering or response streaming; do not change isolation globally for review/write operations.

### 8.1 Snapshot transaction ownership and tests

Implement one explicit snapshot-reader boundary. PostgreSQL isolation must be selected before the transaction's first data query, not after an authentication query inside the same transaction and not inside a nested savepoint. Inspect `ATOMIC_REQUESTS`, request wrappers and callers before implementing this boundary.

Default request path: authenticate/authorize normally, then call the reader on an autocommit connection with no enclosing atomic block. Where ATOMIC_REQUESTS is enabled, opt the relevant analytics/export view out using the supported Django view-level mechanism so the reader owns its outer transaction. Open that transaction, set `REPEATABLE READ, READ ONLY` before its first data SELECT, and perform every dataset query on that connection. Authentication completed in an earlier autocommit transaction does not invalidate this new snapshot. Keep write operations, audit writes and artifact persistence outside the read-only dataset transaction.

If the reader is called inside an existing transaction, do not simply skip SET TRANSACTION and proceed with weaker isolation. Require a caller-owned snapshot that was correctly configured before any queries, use a separately managed connection to the same primary database with explicit lifetime/isolation guarantees, or raise a clear integration error. Select one approach and document it. A separate connection cannot see the caller's uncommitted fixtures/writes; do not use it as a hidden test workaround or route it to a lagging replica.

Use `TransactionTestCase` for tests exercising this real reader/API transaction boundary, including authentication/fixtures committed before snapshot reads and concurrent writes on separate connections. Standard `TestCase` wraps tests in transactions and is suitable for pure aggregation/unit tests with materialised input, not for pretending to verify this isolation boundary. Do not globally change all tests, silently weaken isolation when testing, or catch the transaction error and rerun at READ COMMITTED. Include tests with ATOMIC_REQUESTS enabled, nested caller rejection/supported snapshot handling, concurrent approval between dataset queries, and connection reuse after success/failure. No leaked read-only or changed session-isolation state may affect later writes.

Technical references for the implementer: PostgreSQL SET TRANSACTION documentation (`https://www.postgresql.org/docs/16/sql-set-transaction.html`), Django transaction management (`https://docs.djangoproject.com/en/5.2/topics/db/transactions/`) and testing tools (`https://docs.djangoproject.com/en/5.2/topics/testing/tools/`). Verify against installed versions.

The current 13 × 45 × 6 example contains 3,510 slots, but this is not a permanent limit or a performance guarantee. Measure time/memory on representative data, keep configurable limits and ensure no hidden per-row queries. Test a concurrent approval between reads to prove internal consistency.

Suggested logical routes: VC-only progress analytics, comparison analytics and their PDF/CSV exports. Paginate detail endpoints while returning aggregates for the entire selected dataset. Limit input counts and export size server-side; document limits and report oversize requests clearly. Never silently truncate.

PDF requirements:

- Heading, college identity, selected scope/departments/KRAs, IST generation time.
- Formula definition, approved/expected counts and clear YTD/full-year label.
- Charts plus corresponding readable tables and complete filtered details within documented bounds.
- Embedded local fonts, repeated table headers, page numbering, readable long names and no clipped charts.
- Existing renderer queue/timeouts/error handling; no network chart rendering.
- Render PDF charts as static server-generated inline SVG or Django/Jinja HTML/CSS bars from the same authorised dataset. No chart JavaScript, React hydration, canvas initialisation or remote assets are required. Do not accept arbitrary client HTML/SVG. Escape labels and omit script/event handlers/external references. Frontend chart-library output is not the PDF implementation.
- Verify charts with JavaScript disabled and renderer network/file requests blocked. Preserve existing renderer security controls; C12 covers inline assets/network blocking, while the master plan separately prohibits active report scripts.
- Private/no-store responses and VC authorisation on generation/download.

Exports recompute data at their timestamp using the same definitions/filters. A screen loaded earlier may differ after reviews; display the export timestamp and do not claim frozen screen data unless a snapshot token is implemented. Within the export, charts and tables must match.

CSV is supplementary and uses the same filtered dataset; neutralise spreadsheet formulas in user-entered text. Export is read-only and cannot submit or approve records. Existing report PDFs and evidence downloads must remain unchanged.

## 9. Bulk approval

Add row checkboxes to the existing VC review/progress list. Support “Select this page”, “Select all eligible reports matching these filters”, “Approve selected” and “Approve all matching filters”. Show year/period/department scope and count before confirmation.

Show compact review context alongside selectable rows: exact annual target, submitted-revision achievement, Nil badge/reason and submitted evidence-manifest count. Show the submitted snapshot, not newer draft values. The quick-preview drawer defaults to escaped server-rendered HTML for the exact submitted revision, using the existing sandboxed iframe and report template engine. Opening or switching the drawer must not invoke Chromium, enqueue a PDF job, or run report JavaScript. Preserve selection, cancel/ignore stale preview responses and clearly identify revision/status. Closing or failing to load it must not change approval state. Preview is helpful, not mandatory. Paginate context efficiently, with no per-row fetch storm.

Provide a separate explicit “Download exact-revision PDF” action. Submitted revisions use the existing authorised Pending approval export path and bounded renderer busy/timeout handling. For an approved historical revision, use the durable artifact path in section 9.1; do not create a second approved-artifact generation mechanism. No automatic PDF generation on hover, drawer open, row selection or prefetch. This keeps quick review available while approved-artifact jobs occupy the renderer. Test rapid preview switching with a busy/unavailable renderer: HTML previews must still work without PDF requests. Do not promise a fixed millisecond response time without measurements.

Only currently submitted/awaiting-review revisions are eligible. Approval covers report, evidence and achievement together. Approval is attributed to the logged-in VC and reuses existing audit/PDF semantics.

Implementation:

1. Server prepares a manifest of exact report IDs and submitted revision IDs, actor, filters, creation/expiry time and idempotency key.
2. VC reviews the scope and confirms once. Newly submitted records after selection are not silently added.
3. Process the complete confirmed manifest through sequential requests of at most 50 items each, with deterministic locking and per-item transactions using the existing approval service. The 50-item limit is a processing request limit, not the selection/manifest limit.
4. Recheck revision/state/permissions at execution. Stale revisions, already reviewed records or ineligible items receive explicit skipped/conflict results.
5. Persist per-item results and batch state; retries cannot duplicate approval events. Interrupted sessions can retrieve outcomes after reauthentication as the authorised VC.
6. Show approved/skipped/conflicted/failed counts and reasons. Retry unresolved items only after appropriate fresh validation; do not blindly approve a newer revision.

### 9.0 Full-manifest orchestration

“All matching filters” freezes every eligible item across pagination, not just the visible page. Use a configurable manifest cap initially 5,000 items, sufficient for the current full-year example; do not hardcode 600 as an annual maximum. If exceeded, explicitly require narrower filters before confirmation; never truncate. Single-page selection and all-filtered selection have distinct labels and counts.

Confirm the manifest once. The frontend then calls a server-controlled process-next action sequentially until all confirmed items have terminal outcomes. Return processed/total, approved/conflicted/skipped/failed counts and a server resume token/cursor. Example: 180 reports require batches of 50, 50, 50 and 30; do not show completion after 50. A bounded server batch returns actual committed outcomes, not estimated progress.

Clients must not choose arbitrary records outside the confirmed manifest. A unique manifest-item guard plus row locking/claiming prevents two tabs or duplicate requests from reviewing an item twice. Cursor advancement and persisted outcomes must survive lost responses. While processing, show “Processed 50 of 180”; failures/conflicts are visible terminal outcomes for that pass. Do not endlessly retry failed items. Further retries follow the existing exact-revision checks and show the unresolved selection.

When the page closes or the network/session fails, committed approvals remain. On reopening, fetch the stored manifest and offer Resume for unprocessed confirmed items. Do not imply the browser keeps processing while closed. Confirmation expiry applies before initial confirmation; a confirmed operation has a separately documented retention/resume policy, with role/session/current-revision revalidation on every processing request. A changed filter does not change the confirmed selection. After completion refresh the queue and analytics.

Unlike annual finalisation, bulk approval permits partial success because reports are independent decisions. A failed item does not undo other completed approvals. Expired unconfirmed manifests require new selection; already confirmed retry requests retrieve recorded results. Keep confirmation ownership checks and CSRF enforcement. Approval batching itself need not use a worker. Approved-artifact generation uses the durable processing mechanism below; do not remove that requirement merely to avoid a worker.

Do not approve drafts, rejected/returned records or future unsubmitted reports. Do not introduce a requirement to open every report individually. Double-click prevention in the UI supplements, not replaces, database idempotency.

### 9.1 Approval and approved-PDF generation

Inspect the existing approval call path before reuse. Neither single nor bulk approval may wait for Chromium rendering inside the approval transaction or synchronous approval loop. Keep database review transitions, immutable approval/reviewer snapshots, audit and cache-version invalidation in the transaction; write a durable artifact job/outbox row in the same commit. A renderer outage must not roll back a valid review decision.

Retain the master plan requirement to store approved PDFs as historical artifacts. Default: a restart-safe worker consumes committed artifact jobs through the existing bounded renderer. Reuse an existing job facility; otherwise a small database-backed worker/management command is sufficient. Do not require a new broker unless justified. A post-commit notification may wake the worker, but cannot replace the durable job record. No in-process fire-and-forget thread or request-bound generation.

Jobs reference the exact immutable submission revision, approval decision, reviewer-name snapshot, verification timestamp, template and renderer version. Do not read the submission's latest status or current VC name to construct a historical approved artifact. A return or later approval cannot overwrite an older artifact. Keep private storage, a unique artifact/job key, atomic publish, content hash and idempotent retries; protect concurrent worker/download generation.

Persist pending/running/ready/failed state, retry count and last safe error. Recover abandoned running jobs using a bounded lease; apply bounded retries/backoff and expose failed jobs for operator retry. Download requests for a pending approved artifact return an explicit processing/retry response and ensure its job exists. They must never serve an older revision or a Pending approval document as that approved artifact. Once ready, return the retained authorised file. PDF generation failure and review failure are distinct UI states.

Document worker start/stop, restart recovery, configuration, logs and readiness checks for local development and server deployment. The implementation is incomplete if required jobs have no runnable consumer.

Wire the worker into the repository's real deployment definition: if Docker Compose is used, add a dedicated artifact-worker service in the existing compose file (for example infra/docker-compose.yml); if systemd is used, supply a supervised service unit. Inspect the actual path rather than creating a competing deployment layout. Run the worker using the same application version, database configuration and private-artifact storage as the backend, with internal-only renderer access. Include least-required secrets, restart policy, graceful shutdown/lease release, logging and health/heartbeat observation. Container startup order alone is not readiness: retry dependency connections. Apply migrations through the existing controlled migration step before consumers run.

Update local startup commands/scripts, deployment runbook, environment example, upgrade/rollback steps and monitoring. Verify the complete configured stack consumes a pending job automatically without manually starting an undocumented process. Test worker restart, renderer outage/recovery and shared-storage access. Expose a safe operator health signal for stale heartbeat, growing pending backlog and permanently failed jobs; user-facing downloads show Processing with bounded polling/Retry-After and a retryable failure message, not an endless error screen.

Do not add synchronous on-demand PDF rendering as the default fallback. It would create a second consumer path and still requires lease/idempotency and request-time budgets. A future measured enhancement may allow a single download to claim the same durable job, but must obey the same renderer queue, unique artifact publication and immutable snapshot rules. Worker deployment and recovery are mandatory regardless of any such fallback. Existing historical approved documents remain intact. Lazy-only generation is not the default because unrequested approvals would never receive stored artifacts.

Initially cap approval request batches at 50 database-only items, then measure request latency against configured server timeouts. Reduce the cap if required; 50 is not a performance guarantee. Test approval with renderer unavailable, durable job creation, restart recovery, repeated worker execution, and return/name-change before artifact generation.

## 10. Announcements

VC capabilities: draft, edit, preview recipients, publish, revise published content, withdraw, optional expiry, pin/unpin, and view history. Audience is all departments or selected departments with at least one valid recipient. In-portal only: no email, SMS, WhatsApp, attachments or scheduled publication in this release.

Suggested entities: announcement with a current published revision pointer, immutable published revisions, department audience snapshots and per-user read receipts. Track content version separately from metadata revision, or explicitly carry receipts forward for unchanged content. Reuse existing audit and pagination conventions.

“All departments” resolves to a stored audience snapshot at publication. Future departments are not silently added to old notices. Published edits create revisions and an Updated indicator. Title/body changes create a new content version and become unread for current recipients. Audience-only, expiry-only or pin-only edits preserve read state for recipients who remain authorised; newly added recipients start unread, and existing unread recipients remain unread. If a removed recipient is later re-added, treat that new audience membership as unread. Implement explicit receipt carry-forward or equivalent content-version/audience-membership tracking; do not infer read state solely from an older historical receipt. A revision's audience controls current access; removing a department removes its access to that announcement through direct IDs and older revision routes too. Historical audience remains in VC audit records.

Dean portal: Announcements inbox, compact unread count and recent notices on dashboard. Open detail to mark that revision read; list loading must not mark notices read. Read state is user-specific. Unread count counts distinct active, nonexpired, nonwithdrawn announcements accessible to the current Dean, evaluating only the current published content/revision. One announcement contributes at most one unread item, regardless of revision count. A read request identifies the revision actually opened; if content changes concurrently, it cannot mark unseen new content read. Metadata-only transitions may preserve the established read state under the above rule. Backend derives department from signed-in identity and filters list/detail/read endpoints consistently.

Expired/withdrawn announcements leave active Dean views; preserve VC history. VC may delete unpublished drafts, not published audit history. Escape content, prefer plain text with line breaks, validate links and reject arbitrary HTML. Validate timezone/expiry. Read counts indicate opened notices, not proven comprehension.

Pinned announcements appear first in the current authorised inbox/dashboard, then remaining notices by publication/update time; use a compact pinned section with a view-all link instead of unlimited banners. Pinning does not bypass expiry, withdrawal or audience rules and does not reset read state. Use a simple Pinned flag; no additional urgent-priority hierarchy is required.

Add “Announce to pending departments” on VC Analytics. For an explicitly selected opened period (or selected opened periods from a yearly scope), derive departments with at least one applicable Not submitted, Draft, Rejected or Returned-for-correction slot under the current KRA filters. Exclude Awaiting review, Approved, Not due, unallocated and pre-applicability slots. If a yearly scope is selected, require the VC to confirm which opened periods the notice concerns. This is a shortcut to a new editable announcement draft, never immediate publication. Show proposed recipient departments, scope and a factual suggested message; VC reviews recipients/text and publishes through the normal announcement flow. Revalidate recipients before publication; disclose eligibility changes and require review instead of silently adding recipients. Empty recipient set disables the shortcut. The announcement does not grant reopening or promise that a closed reporting window is open.

Use navigation/focus refresh and existing fetching patterns. Websockets are unnecessary. Announcements never alter deadlines, targets or reopening grants.

## 11. Migration and upgrade strategy

1. Inspect actual schema and migrations. Record existing assignment/publication semantics and any partially implemented v1 features before adapting them.
2. Add required fields/tables incrementally with safe defaults. Avoid destructive schema changes to remove old experimental functionality; disable obsolete user-facing capabilities and document retained data.
3. Backfill existing published/assigned records as finalised, preserving exact targets, IDs, template versions and reports. Do not mark them drafts just because a new finalised_at field is null.
4. Use reliable existing timestamps for migrated audit fields. If unavailable, explicitly record migration provenance; never fabricate a historic actor or date.
5. Preserve real draft assignments as drafts where confidently identifiable; flag ambiguous cases rather than unlocking used targets.
6. Backfill applicability from reliable existing obligations/effective dates without dropping historical slots. Extend grant source constraints for assignment-publication grants while preserving existing source invariants, foreign-key integrity and audit. Add artifact-job state and uniqueness without regenerating or replacing existing retained PDFs. Introduce announcement current-revision/read-state constraints as needed.
7. Establish uniqueness and FK protections after checking existing data. Do not auto-delete duplicates or merge records with history.
8. Verify seed reruns preserve finalised targets, draft edits, removed allocations and developer-managed template versions.
9. Test both clean installation and upgrade from representative existing database state in isolation. Document backup, migration, rollback compatibility and setup commands before production execution.

Suggested indexes follow real queries: allocation year/KRA/department/state; report assignment/period/status; bulk manifest/actor/item; announcement publication/state/audience; read receipt user/content-version or carried-forward revision; artifact job state/lease and unique approval-artifact key. Avoid N+1 queries per chart cell or department. Measure representative full-year queries.

Use isolated synthetic databases/media for tests. Do not modify real college records, reference originals, credentials or production configuration as incidental cleanup.

## 12. Implementation milestones — continue automatically

| Milestone | Work | Completion evidence |
| --- | --- | --- |
| F0: Inspect and reconcile | Actual code/UI state, earlier-plan conflicts, service/model map, worker deployment wiring, grant-source migration decisions | Decision log and exact implementation map; immediately continue |
| F1: Annual allocations | Previous-year copy, draft targets, department selection, remove/restore, atomic finalisation and visibility | Complete VC-to-Dean flow, upgrade/lock/concurrency tests |
| F2: Progress analytics | Shared slot dataset, approval formula, period/YTD/full-year UI/charts/tables | Known-fixture counts reconcile across filters |
| F3: Comparison and exports | Multi-department views, PDF/CSV, pagination/accessibility | 2/3/all-department checks; charts/tables/export agree |
| F4: Bulk approval | Full-manifest orchestration, exact-revision confirmation, bounded requests/resume and deployed durable artifact worker | Concurrent single/bulk review, interruption and artifact recovery tests |
| F5: Announcements | VC authoring/lifecycle/audience and Dean inbox/read state | Targeted access and revision/read tests |
| F6: Integration and handover | Required suites/build, migrations, PDFs, responsive review, documentation | Honest results, reproducible walkthrough and remaining external gates |

These milestone meanings supersede the old F0–F7 table. Do not retain the old numerical-metrics or unrestricted-CRUD milestones. Update links and progress descriptions accordingly.

Work efficiently: inspect relevant files, reuse services, run focused tests while developing, then required full regressions on final shared changes. Do not stop after writing planning documents. Maintain a compact checkpoint if context is exhausted so work resumes at the correct milestone.

## 13. Required validation matrix

| Area | Essential cases |
| --- | --- |
| Permissions | Anonymous/Dean cannot manage assignments, approve, author notices or access VC analytics/exports; direct-ID checks |
| Copy | Selected-only new draft creation; Unallocated vs Removed; correct department-specific targets; first-year fallback; repeated/concurrent copy; drafts preserved; finalised skipped; removed not restored automatically |
| Targets | Text retained exactly; blank finalisation refused; batch edit affects only confirmed draft departments; conflict across tabs |
| Finalisation | Partial selection locks only selected rows; stale selection changes none; retry idempotent; finalise vs edit/remove race; July 1 remains publishable; period-boundary preview conflict; closed-year refusal; under-72-hour next/current choices; atomic publication grant and shell; final-period/year-end grant; finalised targets stay locked |
| Removal | Draft-only remove/restore; finalised row protected; master/template/history untouched; KRA-level partial removal accurately disclosed |
| New KRA policy | VC master-create/edit/delete APIs denied; developer-installed complete template eligible; incomplete template cannot publish |
| Migration | Existing finalised assignments remain locked; historical reports/targets/PDFs unchanged; source provenance honest; seed idempotency |
| Snapshot isolation | TransactionTestCase API path; ATOMIC_REQUESTS wrapper; nested reader handling; no silent isolation downgrade; concurrent writers; connection settings restored |
| Grant constraints | Valid three sources; every invalid null/source combination refused; non-null submission; source ownership checks; one publication grant per submission; other valid later grants allowed; retry never extends expiry; safe old-check migration |
| Preview | Rapid HTML drawer navigation sends no renderer/PDF jobs; exact submitted snapshot; stale response ignored; PDF download explicit; renderer outage does not break HTML review |
| Analytics | Missing and untouched Draft shell both Not submitted; evidence-only Draft including Drive link; existing enum unchanged; return → resubmit → reject classification; approved Nil; reopen/revisions never duplicate slots |
| Formula | 30/40=75%; 60/80=75% YTD and 60/240=25% year; weighted aggregation; zero denominator; status filter does not inflate rate |
| Periods | IST boundary, current open applicable period included in YTD, future Not due, full-year future denominator, legacy effective-period treatment; new Period 3 publication yields four annual slots; excluded prior periods cannot be reopened via new assignment; Dean dashboard and six-period Achievement view hide invalid actions; next-period start excludes current period |
| Comparison | Unequal assignment counts; 2/3/all departments; unassigned N/A; long labels; selected-KRA scope |
| Exports | Authorised filters, exact totals, full filtered rows within cap, repeated headers, escaped content/CSV safety, timeout/busy, no review writes; script-free charts with JavaScript disabled; concurrent approval cannot cause chart/table drift |
| Bulk | 180-item run is 50/50/50/30 with one confirmation; annual selection beyond 600; manifest cap refuses without truncation; duplicate tabs and interrupted batch resume; selection-page vs all-filtered, stale revision, double confirmation, parallel individual approval, partial failure, resume, expiry, correct audit/PDF label; no synchronous rendering; outage/restart jobs retained; duplicate consumers idempotent; configured deployment starts worker with heartbeat/shared storage; later return/name change does not rewrite approved artifact |
| Announcements | Draft invisibility, all/selected audiences, nonrecipient detail/read denied, content edits unread; audience/expiry/pin-only read-state retained; pinned ordering still respects expiry/audience; pending-department shortcut requires review and cannot reopen reports; one badge count after multiple edits; newly added/re-added audience unread; stale read request; former recipient denied; expiry/withdrawal; malicious text |
| UI | Keyboard, focus, contrast, screen-reader labels/table equivalents, changed-target filters preserve visible selection scope, preview drawer retains selection, 375px and desktop, real zoom when available, stale response handling |

Run the repository's required backend suite after shared workflow/schema changes, browser regression suite after shared UI changes, and frontend typecheck/build. Record actual commands and totals, failures and skips. A rerun pass alone does not prove a failure was harmless; diagnose meaningful intermittent failures. Inspect representative PDFs and desktop/mobile screens. Do not mark manual college review or production tests passed based on local automation.

## 14. Acceptance walkthrough

Use synthetic VC and at least two Dean accounts in isolated data:

1. Prepare a future academic year from a prior-year setup.
2. Confirm CSE/ECE retain their distinct old targets. Edit CSE only; compare old/new values.
3. Apply one target to an explicitly selected draft group, then correct one department individually.
4. Remove and restore a draft allocation; demonstrate earlier-year records unaffected.
5. Finalise CSE only. Confirm its target is locked and its Dean sees it; ECE draft remains editable and invisible to its Dean.
6. Repeat copy/finalise to demonstrate no overwrite or duplicate. Advance isolated test time past July 1 and show remaining drafts can still be corrected/published. Publish a separate allocation in Period 3 and confirm four annual slots, no past-period obligations and unchanged previously locked targets. Then test near-close next-period default and current-period + 72-hour choice, including the untouched shell and Dean six-period view.
7. With controlled test time and fixtures, enter different period/report states. Verify the formula, YTD/full-year difference and future Not due labels.
8. Compare departments with unequal totals and export a readable matching PDF.
9. Bulk-approve selected submitted revisions; concurrently alter one eligible state and show safe conflict reporting and retry behaviour. Use more than 50 reports to confirm automatic sequential batches and interruption/resume. Stop the renderer, approve successfully, then restart the configured worker/renderer services and verify the retained PDF uses the original approval snapshot even after a later return.
10. Publish one all-department notice and one CSE-only notice. Show ECE cannot access the latter, even by URL; create a notice through the pending-departments shortcut and explicitly review recipients; pin/unpin it without changing read state; add ECE without resetting CSE read state; edit content repeatedly and show one unread notice; revise/withdraw and verify access rules.

## 15. Documentation and completion criteria

Update current API docs, README/setup/migration notes, progress, validation, feature decisions and team acceptance checklist. Record exact file paths and actual implementation choices, particularly assignment year eligibility, migrated obligations, status mapping, export limits and idempotency.

Definition of done:

- All five features work end to end with backend permissions and approved UI style.
- No numeric achievement subsystem or unrestricted VC master-KRA CRUD remains exposed as part of this feature.
- Annual targets lock at finalisation and previous-year reuse is safe and repeatable.
- Graphs and exports use verified report-slot counts and explicit time scopes.
- Bulk approval, restart-safe approved-artifact storage and announcement audience/read isolation pass meaningful tests.
- Unfinished active-year drafts remain publishable; late assignments have explicit applicability; no new Returned enum or incorrect untouched-draft counts.
- Analytics/export datasets are snapshot-consistent and PDF charts work without JavaScript.
- Upgrade preserves existing work and historical evidence; relevant final-code checks pass or exact external blockers are disclosed.
- Owner receives runnable setup commands and a short review checklist. Remaining college template acceptance, production hosting, backup/recovery and server-capacity gates stay visible.

No deployment, automatic Git push or project-completion percentage is implied by finishing local implementation.

## 16. Paste-ready Claude Code prompt — full implementation

```text
Implement docs/vc-features-implementation-plan.md version 2.3 in full. This replaces the old feature scope: approved-report progress only; annual department-specific draft targets with selective finalisation; developer-managed new KRAs; department comparison/exports; bulk approval; targeted announcements.

Read repository instructions and relevant current plans/progress/decisions, then verify actual code and Git state. Preserve existing work. If any earlier-plan functionality already exists, reconcile it safely with v2.3 instead of blindly rebuilding or deleting data.

Execute F0–F6 as internal milestones and continue automatically. Do not stop after the audit or ask for phase-by-phase approval. Reuse existing Django/DRF, PostgreSQL, React and PDF services. Implement complete models/migrations, service rules, APIs, UI, exports and meaningful tests. Resolve routine engineering choices yourself and document them; pursue independent work if one genuine external blocker remains.

Follow the plan's exact denominator, future-period, draft/publication, target-locking, copy/restore, bulk-revision and announcement-access rules. Do not parse target strings into numeric achievement. Preserve submitted history, existing report formats, evidence handling and department isolation. Backend enforcement is mandatory. Apply all corrections through v2.3: active-year draft publication with frozen effective period, existing status enum and C11 classifier, current-announcement unread semantics, database-only approval with durable approved-PDF jobs, static script-free PDF charts and one snapshot-consistent analytics dataset. Include full-manifest batch orchestration, actual worker deployment wiring, near-deadline current/next-period publication with atomic grant-source support, Dean applicability UI, selected-department-only draft creation and the specified review shortcuts. Use bounded ORM reads inside an explicitly owned read-only repeatable-read snapshot, with TransactionTestCase boundary tests and no silent fallback. Default quick preview to exact-revision HTML without Chromium. Use the explicit three-way grant-source check and conditional publication-grant uniqueness; reuse submission.assignment instead of adding a redundant FK. Include a runnable artifact worker and recovery tests; never silently drop approved historical-artifact storage.

Use isolated synthetic test data. Run relevant focused checks during development and required final backend/browser suites and frontend build. Verify migration upgrade, representative PDFs and responsive UI. Fix regressions without weakening tests. Distinguish executed passes, skips and unresolved failures.

Update progress, validation, API/setup/migration docs and a concise handover. Inspect selectively and avoid repeated scans or verbose logs; token efficiency must not reduce quality. Maintain a checkpoint if context runs low.

Do not commit, push, deploy, reset existing work or modify real college data. Finish with completed features, exact remaining blockers, commands I must run, test results and a brief manual review checklist. Begin now and continue until the complete implementable plan is finished.
```

## 17. Review traceability

| Supplied review item | Resolution |
| --- | --- |
| 1: July 1 hard lock | Sections 3–6: only finalised assignments lock; active-year drafts remain publishable with effective-period scope |
| 2: Returned enum conflict | Section 6.3: existing Rejected state and latest-review derived label; historical approval alone is insufficient |
| 3: C11 shell rows | Section 6.3: explicit shared untouched-draft/evidence predicate |
| 4: Unread multiplication | Section 10: one current announcement count, metadata-only read preservation and content-change race handling |
| 6: Bulk PDF timeout | Section 9.1: database-only approval, durable artifact jobs and runnable recovery-capable consumer |
| 7: Client charts in PDF | Section 8: static server charts tested with scripts and external requests disabled |
| 8: READ COMMITTED drift | Section 8: single materialised query or explicit repeatable-read snapshot; no lazy follow-up reads |

Item 5 was not present in the supplied screenshots; no finding is invented for it. Reviewer timing estimates are not adopted as measured facts. This document updates requirements; repository code and deployment behaviour still require verification during implementation.

### Second review traceability (v2.2)

| New review finding/suggestion | Resolution |
| --- | --- |
| All-filtered selection vs 50-item requests | Section 9.0: complete manifest, sequential processing, persisted progress/resume and explicit cap |
| Worker missing from deployment | Section 9.1: actual Compose/systemd service, local startup, storage, heartbeat and stack smoke tests |
| Suggested direct-download fallback | Not adopted as default; bounded processing UI and supervised worker prevent permanent pending states without duplicating render paths |
| Near-deadline assignment | Section 3: default next period; explicit current-period grant; final-period policy; source-constraint migration |
| Dean six-period display | Section 4.5: shared applicability, explicit N/A labels and hidden invalid actions |
| Difficult one-query ORM cross join | Section 8: bounded ORM reads in read-only repeatable-read, Python slot join; single SQL optional |
| Unallocated departments | Sections 3–4: no row until selected/saved, distinct Unallocated/Removed states |
| Approval context/preview | Section 9: submitted-snapshot columns and selection-preserving quick preview |
| Changed-target filter | Section 4.3: source comparison, new allocation marker and disclosed selection scope |
| Pending-department reminder | Section 10: derived recipient draft with explicit review/publication and no automatic reopening |
| Pinned announcements | Section 10: compact authorised pinned ordering, expiry/withdrawal respected, no unread reset |

These are specified requirements and acceptance tests, not claims that the current code contains every predicted bug. Performance figures in review screenshots remain unverified and are not used as guarantees.

### Third review traceability (v2.3)

| Finding | Resolution |
| --- | --- |
| SET TRANSACTION inside TestCase/nested transaction | Section 8.1: owned outer snapshot, ATOMIC_REQUESTS integration, TransactionTestCase for transaction-boundary tests; never silently skip isolation |
| Quick-preview PDF competes with artifact worker | Section 9: default exact-revision HTML, no implicit Chromium job; PDF generation is an explicit action |
| Three-way grant constraint ambiguity | Section 3: required Submission relation reused, exact source CHECK, partial unique constraint and ownership validation |

### Optional follow-up ideas — not required for v2.3 completion

These suggestions are product enhancements, not defects in the five agreed deliverables. Do not expand mandatory scope automatically.

- Inline Reject/Return from preview: if later requested, reuse exact-revision review services, mandatory reason and existing optional reopening choices. Reject is available only for Submitted; Return only for Approved. After a successful action update selection and invalidate/revalidate any unconfirmed approval manifest. Never mutate an already-confirmed manifest to swap in a different revision or infer that the action succeeded before the server commits.
- Dean annual target-sheet PDF: if later requested, export only that Dean's finalised assignments for the selected year, with exact targets, template/KRA labels, effective periods and generation time. Exclude drafts and other departments. Label partial publication clearly because remaining assignments may still be unpublished; do not present it as the permanently complete annual list. Apply normal private-download authorization and script-free rendering.

The screenshot's proposal to merely guard SET TRANSACTION with `if not in_atomic_block` is insufficient if the skipped branch still serves multi-query analytics at weaker isolation. The specification deliberately preserves the consistency guarantee instead. No new implementation defect is claimed without repository inspection.
