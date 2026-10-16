# KIET KRA Portal — Master Implementation Plan

**Version:** 2.0 (Master) | **Date:** 16 October 2026 | **Audience:** Development team and Claude Code  
**Status:** Agreed functional scope; proposed technical implementation. No application has been implemented by this document.  
**Supersedes:** v1.2. See section 0 for what changed.

## 0. Changes from v1.2

| # | Change | Sections | Status |
|---|---|---|---|
| C1 | VC reject/return when the period is closed **or closes within 72 hours** offers a "Grant 72 hours to resubmit" option, checked by default, which creates a normal ReopenGrant ending at decision time + 72 hours | 2.3, 3.4, 4, 9 | Accepted (approved by project owner; replaces the v1.2 rule) |
| C2 | A Dean's reopen request creates the Submission row if none exists (a real Dean action, not a fake dashboard draft) | 2.3, 4, 7, 9 | Accepted |
| C3 | Evidence changes never bump `Submission.edit_version`; report, achievement and remarks saves go through one client save queue that is flushed before tab switches | 3.1, 3.3, 7 | Accepted |
| C4 | Chromium runs in one dedicated internal renderer process with a fixed browser pool, never inside Gunicorn workers | 6, 8 | Accepted |
| C5 | Evidence gets `source_type` (FILE / DRIVE_LINK); file-only columns are nullable for links, enforced by a check constraint | 7 | Accepted |
| C6 | The 100 MB limit counts only active (not removed) evidence; separate 500 MB cap across all history of one submission | 3.2, 7 | Accepted |
| C7 | Preview debounce raised to about 750 ms; iframe scroll position preserved across updates | 8 | Accepted |
| C8 | Backend pinned to Django 5.2 LTS (security support until April 2028) | 6, 16 | Accepted |
| C9 | Dean dashboard shows a "Reopened KRAs — Action Required" banner with a server-derived countdown | 3.5 | Accepted (Phase 2) |
| C10 | "Download all evidence as ZIP" for the VC | 3.4 | Deferred; optional after Phase 2 pilot |
| C11 | A Draft row with `edit_version = 0` and no active evidence (never saved or used by the Dean) displays as Not submitted on dashboards, progress PDFs and filters until the first draft save or evidence upload | 2.3, 3.4, 4, 7 | Accepted |
| C12 | Report branding (logos, fonts, print CSS) is inlined into the HTML so the renderer's network/file blocking cannot break it | 8 | Accepted |

> Build a secure college-hosted portal for one Vice Chancellor and one Dean per department. Replace the workbook workflow, support KRA-specific forms and live report previews, and submit one consolidated report, evidence set and achievement entry per KRA per two-month period.

## 1. Instructions for Claude Code

1. Read this entire plan before changing code. Inspect the repository and any `AGENTS.md`/`CLAUDE.md` first. This is a fresh project, but do not overwrite work another team member has added.
2. Inspect the local reference-folder structure and complete the source audit described in section 5.1 before application implementation. Copy this plan into `docs/implementation-plan.md`; maintain phase progress in `docs/progress.md`. Record consequential technical decisions in `docs/decisions.md`.
3. Follow the phases in order. Complete a working vertical slice before expanding all 45 templates. Report implemented features, verification performed, known limitations and next steps after each phase.
4. Do not substitute generic forms for prescribed reports, generate fake achievements, or claim exact PDF fidelity without visual comparison.
5. Preserve agreed scope. Technical defaults below are recommendations, not additional institutional policy. Record assumptions; ask only when the source materials cannot resolve a material ambiguity.
6. Keep credentials and personal records out of git. Separate clearly labelled synthetic test fixtures from production seed data.
7. Do not declare production readiness until the acceptance gates, real-server checks and restore test pass.
8. Do not deploy to the college server without authorized access and deployment approval. Implement and test locally first.

## 2. Confirmed product requirements

### 2.1 Roles

| Role | Allowed actions |
|---|---|
| VC | Institution-wide view; create KRAs; assign departments and annual targets; review; approve/reject; return approved reports for correction; grant 72-hour reopening; download progress summaries |
| Dean | View only own department; fill reports; manage evidence; enter achievements; save drafts; download; submit/resubmit; request reopening |

- Initially provision one active VC and one active Dean for each department. No public signup.
- Department name comes from the authenticated Dean account, never from a trusted client-supplied department ID.
- Restrict viewing, editing, exporting and downloading across departments on the server.
- No faculty, student, external-survey respondent or IQAC accounts in release 1.
- Administrative account maintenance is an operator function, not a new institutional role.

### 2.1.1 Separate Dean and VC login portals

- Provide `/dean/login` and `/vc/login` as distinct login pages with role-specific titles and descriptions. A simple root landing page links to both.
- Dean login routes to `/dean/dashboard`; VC login routes to `/vc/dashboard`.
- Dean page accepts only active DEAN accounts; VC page accepts only the active VC account. A valid account for the other portal receives a generic wrong-portal/invalid-login message without establishing a session.
- Use one Django user model, PostgreSQL database and secure server-side session system. Separate login pages do not require separate backends or duplicated account tables.
- Provide explicit `/auth/dean/login/` and `/auth/vc/login/` endpoints, each enforcing its fixed role on the server. Never trust a client role selector to authorize access.
- An existing authenticated user visiting their login page redirects to their own dashboard. An existing session for the opposite role shows a return-to-own-portal or sign-out option; never silently changes roles.
- Restrict all `/dean/*` and `/vc/*` routes and their APIs. Role checks precede object/department scope checks. A typed URL cannot bypass authorization.
- Dean department is derived after authentication; no editable department selector or account registration is offered on the login page.
- Both portals include password visibility, accessible labels, loading/error states, password-change handling and logout. Use generic credential errors and rate limits.
- Use the same college domain and origin for both portals. Logout ends the shared session across tabs; do not promise simultaneous VC/Dean sessions in one browser profile.

### 2.2 Scope, years and targets

- Seed the 45 numbered workbook KRAs with their exact activity text, NBA/NAAC references and department-specific targets.
- Preassign the workbook KRAs and targets for launch year 2026-27.
- Provide year options 2026-27, 2027-28 and 2028-29. Retain records created from launch onward.
- Do not automatically assign future-year targets without a VC action. Offer an explicit copy-to-next-year draft for VC review.
- Annual targets are fixed once assigned for that year. New-year targets may differ. No midyear editing or bimonthly target-change feature.
- Keep target strings intact, including percentages, policy descriptions, Yes, Nil and NA. Do not reinterpret NA/Nil as zero or automatically remove those assignments.
- Import definitions/targets only, not existing achievements, evidence, people or historical reports.
- Exclude additional research-publication, final-year-project and M.Tech target sections outside the numbered 45 KRAs.
- VC-created KRAs can use a supported template. A genuinely new report format requires a software update.

### 2.3 Reporting calendar

| Period | Range in academic year Y–Y+1 |
|---|---|
| 1 | July 1 to September 1, exclusive |
| 2 | September 1 to November 1, exclusive |
| 3 | November 1 to January 1, exclusive |
| 4 | January 1 to March 1, exclusive |
| 5 | March 1 to May 1, exclusive |
| 6 | May 1 to July 1, exclusive |

- Institutional timezone: `Asia/Kolkata`; store timezone-aware timestamps in UTC.
- Use `[opens_at, closes_at)` boundaries, including for reopen grants; do not use browser time for authorization.
- One submission per department + KRA assignment + reporting period.
- Multiple activities are repeatable records within one submission and one consolidated PDF.
- Closed periods are read-only unless the VC grants reopening. Draft and download access remain available for reading.
- An approved reopening grants exactly 72 hours from approval, only for that department, KRA and period.
- Rejection after the original deadline does not silently reopen submission. Instead, when the VC rejects or returns a submission and the period is already closed **or less than 72 hours remain before `closes_at`**, the review dialog shows "Grant 72 hours to resubmit", checked by default. If left checked, the same transaction creates a ReopenGrant from the decision time to decision time + 72 hours, recorded as VC-initiated; editing is allowed while either the period window or the grant is open. If unchecked, the Dean must request reopening as usual. (C1)
- A Dean may request reopening for a closed period even if they never saved a draft: the request creates the Submission row (status Draft, `edit_version = 0`) for that assignment and period, then attaches the request. Until the Dean's first draft save or evidence upload, that row displays as Not submitted everywhere, including when the request is pending or denied. (C2, C11)

## 3. KRA workspace and user experience

### 3.1 Report tab

- Desktop: left editor, right reactive document preview. Small screens: switchable Form/Preview views.
- Autofill department, academic year and reporting period; show annual target and current status.
- Section navigation, required-field indicators, inline errors, repeatable rows/activities and conditional inputs.
- Save Draft plus debounced autosave with visible Saving/Saved/Failed state; never imply an unsaved value was persisted.
- Report payload, achievement and remarks saves share one client-side save queue (one request in flight, sending the latest `edit_version`). Flush the queue before switching Report/Evidence/Achievement tabs or leaving the page. On 409, keep the local values, reload the server copy and show a conflict message; never discard typed input. (C3)
- Preserve incomplete drafts. Run strict required-field validation only on submission.
- Confirm removal of populated activities/rows; warn before leaving with unsaved changes.
- Live preview follows the selected report's layout and source branding. Include page navigation/zoom for final PDF preview.
- A final paginated PDF preview must be available before submission; long tables/text can change page count.

### 3.2 Evidence tab

- No report live preview in this tab.
- Upload PDFs/JPEG/PNG and add HTTPS Google Drive links. Proposed initial limits: 20 MB per file and 100 MB of **active** (not removed) evidence per submission, plus a 500 MB safety cap across all history of that submission; keep these configurable and confirm with server capacity. (C6)
- Evidence changes do not change `Submission.edit_version`; evidence is snapshotted into the revision manifest only at submission. (C3)
- Record label/category, original filename, size, type, upload date and optional description.
- Allow authorized preview/open and individual download. Removal only while the submission is editable.
- File preview/download is separate from report generation. Never append evidence automatically to the report PDF.
- Google Drive access remains governed by Drive permissions. Explain that the VC must be able to open the link; do not claim links have been verified merely because their syntax is valid.
- Do not fetch arbitrary Drive content on the server or implement a Drive integration in release 1.
- Requirements vary per KRA; define a reviewed minimum evidence set and conditional requirements. Nil submissions need no event evidence.

### 3.3 Achievement tab

- One achievement value plus progress/remarks per period. Preserve text as entered: numbers, percentages, NA and descriptive entries are valid when appropriate.
- Show the fixed annual target and all six period entries without changing the selected period accidentally.
- No automatic annual achievement totals, target-attainment percentages or cumulative aggregation in release 1.
- Record Nil activity separately from empty/not submitted. A Nil reason is required.
- Do not infer achievements from evidence count, event count or report text.

### 3.4 VC screens

- Dashboard: counts of assigned, draft/not submitted, submitted, rejected and approved submissions; upcoming/closed windows and pending reopening requests.
- Filters: academic year, period, department, KRA and status. Pagination, search, empty/error/loading states.
- Review: Report, Evidence and Achievement views plus revision history and review comments.
- Approve; Reject with mandatory reason; Return approved submission for correction with mandatory reason. When the period is closed or closes within 72 hours, the reject/return dialog includes the "Grant 72 hours to resubmit" option (C1).
- Status counts and filters treat `edit_version = 0` Draft rows with no active evidence as Not submitted (C11).
- Deferred (C10, optional after pilot): "Download all evidence as ZIP" per submission — uploaded files plus `external-links.txt` for Drive links, same scope checks as single downloads, streamed with a size cap.
- Reopening queue: department/KRA/period, request reason, approval/denial and expiry.
- KRA catalogue, future-year assignment/target setup, current-year read-only target view.
- Progress PDF: department, KRA, annual target, entered achievement and submission status; include selected filters and generation time. No invented performance scores.

### 3.5 Dean dashboard (C9)

- Assignment list for the selected year/period with status per KRA (Not submitted / Draft / Submitted / Rejected / Approved).
- When any active ReopenGrant exists for the Dean's department, show a prominent "Reopened KRAs — Action Required" banner at the top listing KRA, period and time left (for example "Expires in 48h 12m").
- The countdown is computed from the server's `expires_at` and server time sent with the response; the browser only displays it. Authorization still checks the grant on every request.
- Also show rejected submissions and their reasons, since there are no email/WhatsApp notifications in release 1.

## 4. State machine and deadlines

| Action | From | To | Conditions |
|---|---|---|---|
| Save/edit | Draft or Rejected | Same | Own department; open period or active grant |
| Submit/resubmit | Draft or Rejected | Submitted | Window open; validation passes; create immutable revision |
| Approve | Submitted | Approved | VC; action references current submitted revision |
| Reject | Submitted | Rejected | VC; reason required; if closed or closing within 72 hours, optional 72-hour grant in the same transaction (C1) |
| Return for correction | Approved | Rejected | VC; reason required; retain old approved revision; if closed or closing within 72 hours, optional 72-hour grant (C1) |
| Request reopen | None or Draft/Rejected | No status change (creates Draft row with `edit_version = 0` if missing; shown as Not submitted until first save or evidence upload) | Dean; period closed; no active grant; no pending request (C2, C11) |
| Reopen | Any eligible non-final editing case | No status change | VC grant scoped to department/KRA/period; does not unlock Submitted/Approved records by itself |

- Missing submission rows display Not submitted; do not create fake drafts just to populate dashboards. Rows are created only by a Dean action: opening/saving a draft or requesting reopening (C2).
- Submitted/Approved records are not editable by the Dean, even during reopening.
- A returned submission exported in its current state shows Pending approval; retain historical approved versions with their historical status clearly identified.
- Reject/return actions preserve previous report data, evidence references, target snapshot and review history.
- Prevent duplicate approvals/submissions with transactions, row locks and revision checks.
- One pending reopening request per submission; reject duplicates. Repeated grants are allowed only through a new explicit VC approval; never silently extend a grant.
- Nil submissions still pass through review. Generate a short Nil report bearing KRA, department, period, reason and approval state.

## 5. Templates: inventory and adaptation

### 5.1 Source package and reference-folder instructions

**For Claude Code:** The project owner will place the workbook and supplied report templates in the local `reference/` folders below. These are the source documents for understanding report content and layout. Verify their actual presence before claiming to have inspected them; this plan does not itself contain the source files.

```text
kiet-kra-portal/
  KIET_KRA_Claude_Code_Implementation_Plan.md
  reference/
    workbook/
      <original KRA tracker>.xlsx          # include if available
      <converted KRA tracker>.md
    templates/
      <original template filename>.pdf    # 30 supplied PDF files
      <original template filename>.docx   # optional originals, if available
      <original template filename>.xlsx   # optional originals, if available
```

The angle-bracket names are illustrative placeholders, not literal filenames. Keep each template's original filename so KRA numbers remain recognizable. The 30 PDFs include shared KRA formats and supplementary feedback forms; they do not correspond one-to-one to the 45 KRAs. Additional Word/Excel originals are alternate source versions, not new KRA assignments. Do not count the earlier standalone KRA 33 sample twice if a duplicate copy is present.

#### Required inspection before implementation

1. Open `kiet-kra-portal/` as the working project root. Read this plan and repository instructions first.
2. Enumerate `reference/workbook/` and `reference/templates/` recursively; report actual filenames, formats, unreadable files and missing expected sources. Do not rely on a filename alone to infer report contents.
3. Read the workbook definitions, department targets, period headings and instructions. Preserve department differences and distinguish the 45 numbered KRAs from excluded extra target sections.
4. Read all pages/sheets of every supplied template. Extract fields, required/optional information, tables, repeatable records, rating scales, conditional sections, evidence lists, signature areas and example content.
5. Render and inspect PDFs visually for branding, headings, column widths, orientation, pagination, footers and broken source exports. Text extraction alone is insufficient to assess layout.
6. Inspect optional DOCX/XLSX originals when present to clarify structure and formatting. Record discrepancies between originals and PDFs instead of silently choosing a version.
7. Create `docs/template-inventory.md`: original path, SHA-256 checksum, format, page/sheet count, proposed KRA mapping, source type (supplied/adapted/project-created), fields, repeatable sections, evidence requirements and layout issues.
8. Cross-check mappings against the workbook and the approved coverage map in section 5.2. Record shared templates, KRA 9a/9b variants, KRA 19a/19b supplementary forms and the known conflicting templates.
9. Create `docs/source-audit.md` summarizing actual coverage, missing formats, duplicate files, source inconsistencies and proposed adaptations. Record unresolved assumptions in `docs/decisions.md`.
10. Complete this source audit before coding application features. Continue using the already approved adaptations; ask only about genuinely unresolved material issues.

#### Source preservation and authority

- Keep everything in `reference/` unchanged. Store extracted text, thumbnails and trial renders in an ignored temporary working directory.
- This implementation plan governs the approved workflow, permissions and adaptations. The workbook governs KRA activity meanings and targets. Supplied templates govern report fields/layout except for explicitly approved corrections and adaptations.
- Never copy sample years, names, event IDs, positive outcome claims or example records into production data as actual achievements.
- The Markdown workbook splits some rows/columns into separate tables. Never align targets/achievements by unchecked row positions. Prefer original XLSX for target extraction; otherwise verify each department target against the conversion.
- Do not infer Excel formulas from displayed Markdown values, and do not implement automated achievement calculations.
- Source file names with spaces must be quoted correctly in shell commands. Resolve paths relative to the project root, not the terminal's incidental working directory.
- Original references are not runtime evidence. Store actual uploaded evidence and generated reports in protected persistent storage outside public static assets and outside git.
- ChatGPT attachment IDs, Library IDs and sandbox paths are not usable file references inside the user's Claude Code environment; the actual source files must be copied into these local folders.
- Do not claim every KRA has an official template: missing/adapted formats are explicitly covered in sections 5.2 and 5.3.

#### Suggested first instruction to Claude Code

> Read the implementation plan and inspect every file in `reference/`. Before writing application code, create the source audit and template inventory, mapping actual file contents to the 45 KRAs, required fields, layouts and evidence requirements. Preserve originals, follow the approved adaptations, and report any missing or contradictory source information. Then proceed through the implementation phases in order.

### 5.2 Coverage map

| KRA | Implementation |
|---|---|
| 1–3 | Shared course-report family; preserve distinct new-course/value-added/MOOC activity meaning |
| 4–6 | Programme/project/internship records adapted to student completion for each specific KRA |
| 7–10 | Consolidated surveys; retain supplied questions/layout; KRA 9 includes 9a and 9b variants |
| 11 | Bridge courses; programme, syllabus, assessment, outcomes and feedback |
| 12 | Awards report; structured award entries within the source's open details area |
| 13 | Faculty board/committee membership, meetings, contributions and outcomes |
| 14 | Project-created Yukthi registration report |
| 15 | Entrepreneurship table; include faculty identification as well as student/alumni IDs |
| 16 | Project-created innovation-ambassador report |
| 17 | Industry-supported training centre/lab records |
| 18 | MoU details plus actual activities under the MoU |
| 19 | Industrial-visit report; feedback source and PO/PSO matrix; supplementary summary data as needed |
| 20 | Faculty industry training; preserve more-than-a-week KRA wording |
| 21 | Competitive-training report adapted to workbook definition; exam qualification data only optional supporting information |
| 22 | Career-counselling activity table |
| 23 | Skill-development/employability programme report |
| 24 | Placement/higher-education conditional record fields; preserve workbook placement target meaning |
| 25–26 | Sports/cultural awards; retain team-award-counted-as-one wording |
| 27–30 | Event-organizing variants for sports, culture, technical/academic fests and club activities |
| 31 | Hackathon/ideathon records |
| 32 | Financial/non-financial alumni contributions with conditional payment fields |
| 33 | Alumni event reports; repeat activities within consolidated PDF |
| 34–35 | Project-created financial-support reports |
| 36–37 | Staff training / faculty development variants; retain applicable minimum-duration wording |
| 38 | Faculty development programmes attended |
| 39 | Infrastructure-grant report adapted to workbook; do not substitute research-funding metric |
| 40–42 | Project-created audit/inclusion/constitutional-awareness reports |
| 43 | Conference-organizing report adapted to workbook; do not substitute journal-publication metric |
| 44 | Boot camps and peer learning |
| 45 | Flagship events with SDG mapping; evidence remains separate |

- Do not reuse mismatched uploaded templates unchanged merely because their filename carries a KRA number.
- Seven wholly missing formats: 14, 16, 34, 35, 40, 41, 42. Label them as project-created in the inventory, not official supplied formats.
- Correct split logos/tables, unnecessary blank pages and approved copied wording. Document substantive wording changes.
- Do not silently change ambiguous labels (for example duplicated PSO1) without documenting the intended correction.
- Source template years/example event IDs are examples, not production records; use selected year and actual entered values.
- Preserve prescribed signature spaces where needed; the portal adds textual VC verification, not simulated signatures.

### 5.3 Missing-template minimum content

| KRA | Fields |
|---|---|
| 14 | Project/title, registration ID/date, faculty coordinator, student team, innovation area, status, evidence references |
| 16 | Ambassador name/ID/category, designation/programme, appointing/certifying body, training, certificate/date, contributions |
| 34 | Faculty ID/name, conference/workshop, organizer, dates, sanctioned amount, amount paid, payment date/reference, participation |
| 35 | Faculty ID/name, professional body, membership type/number/validity, fee, institutional support paid, reference |
| 40 | Audit scope/date/team, findings, recommendations, actions, responsible persons, progress, equity activities and outcomes |
| 41 | Activity/theme, date/venue, organizers, participants, inclusion objective, description, outcomes and feedback |
| 42 | Activity, constitutional values/rights/duties, resource persons, dates, student/staff participation and outcomes |

Every format includes department, year, period, target context, evidence checklist and current verification state. Capture payment records for the workbook's Rs. 5,000 annual-per-faculty condition in 34–35; do not reject an individual smaller payment automatically when annual aggregation may apply.

### 5.4 Survey handling

- KRAs 7–10: one Dean-entered consolidated report using college-prepared averages. No external surveys, respondent accounts or automated averaging.
- Accept decimal scores within the original question's scale; do not round to an integer silently. KRA 7 also has a 1–10 overall score.
- Preserve the original rating columns; show the exact consolidated average alongside/within the response area without misrepresenting it as an individual response.
- Personal respondent fields must support a clearly indicated consolidated context; do not force a fictitious person/email/phone. Document this as a necessary adaptation for team review.
- KRA 9: allow applicable 9a/9b sections in the same consolidated PDF; avoid duplicating submissions. Exactly-four-years classification is not determined by the supplied titles—leave variant choice to the college and flag this in help text.
- KRA 19b student feedback: proposed default is upload collected forms as evidence and enter a consolidated feedback summary; this was not explicitly settled for individual student response entry. Keep it an identified assumption for team review.
- Retain feedback action-taken, impact-analysis and BoS discussion requirements as summary sections/evidence where applicable. Record pending/not applicable truthfully.

## 6. Proposed stack and repository

Use a modular monolith, selected for maintainability and college hosting:

| Layer | Recommendation |
|---|---|
| Frontend | React + TypeScript + Vite; Tailwind CSS; React Hook Form; schema-driven controls |
| Backend | Django 5.2 LTS + Django REST Framework; service functions for business rules (C8) |
| Database | PostgreSQL |
| Authentication | Django server-side sessions, secure cookies and CSRF protection; same-origin UI/API |
| Report rendering | Versioned server HTML/CSS templates rendered by Django; PDF printed by a separate internal renderer process (Playwright Python + Chromium, fixed pool of 1–2 browsers, internal-only port) that Django calls with a timeout (C4) |
| Evidence storage | Private persistent filesystem on college server; metadata in PostgreSQL; storage abstraction for future migration |
| Deployment | Nginx + Gunicorn + Django + PostgreSQL; Docker Compose if college permits |
| Tests | Backend unit/integration tests; frontend component checks; Playwright browser workflows |

Use Django 5.2 LTS for the backend (C8). For everything else, select currently supported stable versions at implementation, verify compatibility, pin dependencies and commit lockfiles. Do not copy development documentation version numbers into dependencies without checking support.

```text
backend/
  config/                 # settings, URLs, environment validation
  apps/accounts/
  apps/catalogue/         # departments, years, periods, KRAs, assignments
  apps/submissions/       # drafts, revisions, validation, transitions
  apps/evidence/
  apps/reviews/           # reviews and reopening
  apps/reports/           # template registry, HTML rendering, exports
  apps/audit/
  templates/reports/      # versioned report layouts and shared partials
  tests/
renderer/                 # internal PDF renderer process (Playwright + Chromium pool), not public
frontend/
  src/api/
  src/auth/
  src/components/
  src/features/{vc,dean,report-builder,evidence,achievements}/
  src/routes/
reference/                # supplied source files; no production evidence
seed/                     # reviewed catalogue/targets, not credentials
infra/                    # Compose, Nginx, Dockerfiles, backup jobs
scripts/                  # setup, seed, provision, backup/restore
docs/                    # plan, assumptions, inventory, API, operations
```

No microservices, AI report writing, public signup, email/SMS integration, DOCX export, cryptographic signatures or automated scoring in release 1.

## 7. Data model and invariants

Use relational entities for institutional data, ownership, workflow and audit. Use validated JSON for template-specific form payloads; do not put the entire application in one JSON field.

| Entity | Essential fields/constraints |
|---|---|
| User | login identifier, name, password hash, role VC/DEAN, department, active, must-change-password; enforce one active Dean per department and one active VC |
| Department | unique code, full name, active |
| AcademicYear | unique label, start/end dates; never delete referenced years |
| ReportingPeriod | year, index 1–6, opens/closes; unique year/index |
| KRA | code/number, official title, NBA/NAAC refs, active |
| TemplateVersion | template key, version, schema, renderer version, source checksum, evidence rules; immutable when used |
| AnnualAssignment | department, KRA, year, target_text, template version, assigned_at; unique department/KRA/year; assigned target immutable |
| Submission | assignment, period, status, nil flag/reason, achievement text, remarks, draft payload, edit_version, current submitted revision; unique assignment/period |
| SubmissionRevision | immutable sequence, payload, achievement, target/title/template snapshots, submitter/time, evidence manifest/hash |
| Evidence | submission, `source_type` FILE/DRIVE_LINK, storage key (FILE) or Drive URL (DRIVE_LINK), category, label, original filename, MIME, bytes, checksum, uploader/time, removed flag. Filename/MIME/bytes/checksum/storage key are nullable but required by a check constraint when FILE; Drive URL required when DRIVE_LINK (C5) |
| ReviewDecision | revision, reviewer, approve/reject/return, reason, timestamp, reviewer-name snapshot, granted_reopen flag (C1) |
| ReopenRequest | submission (row created on request if missing, C2), reason, requester/time, pending/approved/denied, decision reason |
| ReopenGrant | submission, starts_at, expires_at, approving VC, source (request or review decision), nullable `request` FK and nullable `review_decision` FK; a check constraint requires exactly the one matching `source` (request → `request` set, `review_decision` null; review decision → the reverse); immutable grant history (C1) |
| GeneratedDocument | submission/revision, generation type, content hash, status snapshot, reviewer snapshot, renderer version, storage key |
| AuditEvent | actor, action, entity, old/new state or safe summary, timestamp, request ID |

- Use UUIDs for exposed identifiers, but never treat unguessability as authorization.
- Foreign-key deletion protections preserve history. Soft-deactivate users/KRAs; never cascade-delete approved records.
- Validate period belongs to assignment year. Select the authenticated Dean's department server-side.
- Save/edit uses optimistic concurrency (`edit_version`); stale requests return 409, not last-write-wins. Only draft payload, achievement, remarks and Nil fields bump `edit_version`; evidence add/remove does not (C3). New rows start at `edit_version = 0`; dashboards, filters and progress exports show `status = Draft AND edit_version = 0` **with no active evidence** as Not submitted (C11). A row with any active evidence shows as Draft even if the Report tab was never saved.
- Evidence quota: sum `bytes` over active (removed = false) FILE evidence for the 100 MB limit, and over all FILE evidence for the 500 MB history cap, inside the upload transaction (C6).
- Submit locks the row, checks current time and version, validates form/evidence, snapshots all content, sets Submitted and creates audit event atomically.
- Review acts on the exact revision; a stale VC tab cannot approve a superseded revision.
- Evidence referenced by a submitted revision cannot be physically deleted when the current draft removes it. Retain immutable historical files/manifests.
- Target text, report template and VC name snapshots prevent later catalogue/account changes from rewriting history.
- Generated PDFs are reproducible from retained snapshots and template versions; store approved PDFs as historical artifacts.

## 8. Template engine and PDF implementation

1. Build a versioned schema for each report: IDs, labels, data types, required/conditional rules, groups, repeatable tables/activities, defaults, limits, evidence categories and renderer mapping.
2. Expose schema read-only to the frontend. Backend is authoritative for validation; contract tests ensure frontend controls match it.
3. Supported controls: text, long text, decimal/integer, date, time, select, multi-select, boolean, ratings, repeatable objects/tables. Evidence is managed separately and linked by IDs.
4. Use bounded text lengths/row counts with clear messages; proposed starting cap 100 records per table and 20 activities, configurable after realistic testing. Never truncate silently.
5. Use escaped text/structured paragraphs; avoid user-authored HTML. No active scripts or arbitrary remote images in reports.
6. Render current draft payload to HTML on the backend after authorization and structural validation. Debounce preview requests around 750 ms after the user stops typing; cancel/ignore stale responses (C7).
7. Display returned HTML in a sandboxed iframe. Save the iframe's scroll position before each update and restore it after load so the preview does not jump to the top; DOM-diffing (e.g. morphdom) is optional if flashing remains a problem in testing (C7). Use the same HTML templates and print stylesheet for server PDF generation.
8. HTML preview is responsive and quick; a PDF preview verifies actual pagination. Do not promise the browser HTML alone has identical page breaks.
9. Chromium loads only server-controlled report HTML, local branding/fonts and approved internal resources. Block external network requests/file paths; no Drive fetching during rendering. Inline institutional logos, fonts and print stylesheets into the report HTML (Base64 `data:` URIs and inline `<style>`), so the renderer needs no network or file access and blocking cannot break branding. Abort every non-`data:` request in the renderer (C12).
10. Wait for fonts/assets; set page size/orientation per template, print backgrounds, safe margins and repeated table headers. Break long rows safely; avoid clipped cells and giant blank spaces.
11. Place Pending approval or Verified by VC - [name] through server-derived status, never a client flag. Draft/incomplete PDFs remain downloadable with Pending approval and clear empty placeholders.
12. Generate one PDF for all report activities; preserve activity boundaries/headings, common metadata and consistent footer/page numbering.
13. Cache by payload/revision + template + renderer + verification state. Approval/return invalidates current cached export without deleting historical copies.
14. Never launch Chromium inside Gunicorn workers: a per-process semaphore does not limit across forked workers, and each Chromium uses roughly 200–400 MB. Run one internal renderer process that keeps a fixed pool of 1–2 browser instances (the pool size is the global concurrency limit) and accepts server-generated HTML over an internal-only port. Django calls it with a timeout and returns a recoverable "PDF busy, try again" error rather than blocking or losing the draft. Add a background job queue only if measured load requires it (C4).
15. Verify portrait/landscape tables, long text, multiple activities, empty optional fields, Unicode names and decimal survey scores against reference documents.

## 9. API contract

Prefix `/api/v1`; use pagination and consistent error envelopes with code, message, field errors and request ID. Document in OpenAPI.

| Endpoint group | Operations |
|---|---|
| `/auth/` | CSRF bootstrap, separate Dean/VC login endpoints, logout, current user, change password |
| `/years/`, `/periods/` | Authorized catalogue reads |
| `/departments/` | VC reads all; Dean receives own department only |
| `/kras/` | Catalogue read; VC create/update nonhistorical metadata and deactivate |
| `/assignments/` | Scoped list/detail; VC future-year draft/copy/finalize; enforce fixed targets |
| `/templates/{version}/` | Schema read for authorized assignment |
| `/submissions/` | Scoped get-or-create draft; list/filter; no duplicate period records |
| `/submissions/{id}/draft/` | PATCH with expected edit_version |
| `/submissions/{id}/validate/` | Report field/evidence errors without submitting |
| `/submissions/{id}/preview/` | POST unsaved draft payload for HTML preview; no authoritative status supplied by client |
| `/submissions/{id}/export/` | Generate/download current report; authorized historical revision export separately |
| `/submissions/{id}/submit/` | Atomic submit/resubmit using expected version |
| `/submissions/{id}/evidence/` | Upload file/add Drive link/list/remove permitted draft reference |
| `/evidence/{id}/download/` | Scope check, protected download with safe filename |
| `/submissions/{id}/review/` | VC approve/reject/return with revision, reason and `grant_reopen` boolean (honoured only for reject/return when the period is closed or closes within 72 hours; ignored otherwise, C1) |
| `/submissions/{id}/reopen-requests/` | Dean request on an existing submission; VC review through request decision endpoint |
| `/assignments/{id}/periods/{period_id}/reopen-requests/` | Dean request when no submission exists yet; creates the Draft row and the request atomically (C2) |
| `/reopen-grants/active/` | Dean: own department's active grants with `expires_at` and server time, for the dashboard banner (C9) |
| `/reopen-requests/{id}/decision/` | VC approve creates 72-hour grant; deny records reason |
| `/progress/`, `/progress/export/` | VC filtered summary and PDF; derive counts from database |
| `/submissions/{id}/history/` | Authorized revision/review/grant history |

- No mutation through GET. Reject forbidden object references even if embedded in nested payloads.
- Return 401 for unauthenticated requests, 403/404 consistently for unauthorized objects, 409 for conflicts and structured validation errors for invalid inputs.
- Never allow generic PATCH to change status, reviewer, department, target or grant expiry.
- Export must not implicitly submit or approve.

## 10. Security, reliability and operations

- Same-origin HTTPS; secure HttpOnly session cookie, SameSite policy and CSRF on unsafe requests. No auth tokens in localStorage.
- Strong initial random passwords delivered securely; require change on first login. Operator reset command invalidates sessions; do not depend on unconfigured email.
- Rate-limit login and expensive upload/render endpoints. Passwords are hashed by the framework; never logged.
- Strict allowed hosts/trusted origins; production debug off; secrets supplied through environment files outside git.
- File signature/MIME and size validation, sanitized names, random storage keys; reject executable/SVG/HTML uploads. Quarantine and scan files if the college provides malware scanning; record availability honestly.
- Evidence directories must not be publicly served. Use authorized streaming or protected Nginx internal redirects.
- Sandbox PDFs/images when previewing; browser downloads use appropriate content disposition and no-sniff headers.
- Protect against SQL injection through ORM, stored XSS through escaped rendering, SSRF through external-request blocking, path traversal through storage keys.
- Transactional transitions, idempotent seeds, migration review and database constraints protect integrity.
- Log exceptions/request IDs/action metadata; never full report bodies, passwords, session cookies or unrestricted personal data.
- Health/liveness/readiness endpoints; monitor disk, DB availability, rendering failures, TLS and backup status.
- Database and private-file backups must be consistent and encrypted/protected. Proposed defaults: daily backup, off-server copy, 30 daily snapshots; college confirms retention and recovery objectives before deployment.
- No automatic deletion of institutional records until the college defines retention policy. Cleanup only unreferenced temporary uploads/render outputs using a documented safe job.
- Grants expire by timestamp check on every request; correctness must not depend on a scheduler running exactly at expiry.

## 11. Implementation phases and exit gates

### Phase 0 — Source audit and seed preparation

- [ ] Inventory all 30 PDFs and workbook; retain originals.
- [ ] Extract 45 KRAs, exact department targets and NBA/NAAC references into reviewed seed files.
- [ ] Verify department codes/full names. The materials use MBA/KSOM inconsistently; do not create duplicate departments. Obtain the college's canonical name before final seed.
- [ ] Create template schemas/coverage matrix, mark supplied/adapted/new formats, evidence rules and any unresolved institutional wording.
- [ ] Record proposed defaults and server prerequisites.
**Exit:** every KRA has a source or explicit design; no fabricated targets; seed reviewed against source.

### Phase 1 — Foundation and access control

- [ ] Initialize repository, dependency lockfiles, dev environment, formatting/type checks and CI.
- [ ] Create PostgreSQL schema/migrations, users, departments, years, periods and assignments.
- [ ] Add idempotent seed/provision commands, auth/password changes and scoped API querysets.
- [ ] Implement separate `/dean/login` and `/vc/login` pages, role-checked login endpoints, protected dashboards/navigation, year/period filters and Dean assignment list.
**Exit:** two test Deans cannot read/write/download each other's records; VC can access both; repeated seed does not duplicate or overwrite assigned targets.

### Phase 2 — Pilot complete workflow (KRA 33)

- [ ] Implement draft persistence, repeatable activities, one KRA 33 form and live HTML preview.
- [ ] Implement PDF generation, separate evidence, achievement and Nil mode.
- [ ] Add submit/reject/resubmit/approve, immutable revisions and verification labels.
- [ ] Add reopening request/72-hour grant (including request with no prior draft, C2), reject-after-close grant option (C1), dashboard reopen banner (C9) and period boundary tests.
- [ ] Stand up the internal PDF renderer process (C4) and the shared save queue with flush-on-tab-switch (C3).
- [ ] Visually compare filled PDF against source; test long data and multiple events.
**Exit:** one full Dean-to-VC workflow works end-to-end, including correction after a deadline; team accepts template fidelity/usability.

### Phase 3 — Prove remaining template families

- [ ] KRA 20 for wide repeatable tables; repair broken source pagination.
- [ ] KRA 7 for decimal averaged ratings and consolidated survey fields.
- [ ] KRA 32 for conditional financial/non-financial sections.
- [ ] Test several concurrent drafts/exports and server rendering constraints.
**Exit:** reusable renderer handles narrative, tables, surveys and conditional data without template-specific duplicated application logic.

### Phase 4 — Expand all 45 reports

- [ ] Add course family 1–3/11/23/36–37; feedback family 7–10/19b treatment.
- [ ] Add activity family 12/13/18/19/27–31/33/43–45.
- [ ] Add records family 4–6/15/17/20–22/24–26/32/38/39.
- [ ] Add new templates 14/16/34/35/40–42.
- [ ] Verify each mapping and evidence checklist; validate every output independently.
- [ ] Produce synthetic sample PDF for each KRA and record visual test results; never seed these samples into production.
**Exit:** catalogue has 45 working template mappings, no placeholder forms or unreviewed report exports.

### Phase 5 — VC administration and progress

- [ ] KRA creation with supported templates, department assignment and next-year targets/copy workflow.
- [ ] VC review filters, reopening inbox, histories and progress PDF export.
- [ ] Ensure annual target locks, archived-year reads and future-year handling.
**Exit:** VC can manage next-year assignments and get accurate filtered status summaries without modifying past records.

### Phase 6 — Hardening and acceptance

- [ ] Execute permission, deadline, revision, upload and export tests below.
- [ ] Check keyboard accessibility, mobile layout, labels, empty states and clear error handling.
- [ ] Run dependency checks, production config checks and measured concurrency tests.
- [ ] Hold team walkthrough using one VC and at least two Dean test accounts.
**Exit:** no critical data-isolation or workflow defects; documented acceptance signed off by project owner.

### Phase 7 — College deployment and handover

- [ ] Confirm OS/CPU/RAM/disk, Docker policy, ports/domain/TLS, backup destination, access method and college operator.
- [ ] Deploy staging first; execute migrations, seed and smoke tests.
- [ ] Configure protected persistent volumes, backups, monitoring and restart policies.
- [ ] Provision real accounts securely; exclude synthetic data and default credentials.
- [ ] Complete restore drill, rollback drill and production acceptance.
- [ ] Deliver Dean/VC guides, operator runbook, source repository and environment-variable reference.
**Exit:** authorized deployment works on actual college server and recovery steps are demonstrated.

## 12. Mandatory verification matrix

| Area | Required cases |
|---|---|
| Login portals | Correct-role login succeeds; opposite-role login rejected without session creation; direct cross-role dashboard/API denied; existing-session redirects and logout across tabs |
| Permissions | Dean A cannot list/read/modify/export Dean B submission or evidence by guessed IDs; nested foreign evidence blocked; inactive users denied |
| Calendar | Before opening, exact opening, exact closing, leap year dates, UTC/IST conversion, active/expired 72-hour grant, rejected-after-close |
| State | Incomplete draft saves; invalid submit fails; Submitted/Approved editing blocked; rejection reason required; return approved report retains prior history |
| Concurrency | Two tabs cause version conflict; double submit/approve does not duplicate revision; stale VC review rejected |
| Targets | Exact source values; year lock; next-year change allowed; old report snapshots unchanged |
| Report | All 45 mappings; many rows/events; long text; Unicode; empty optional data; no clipped tables; correct approval labels and reviewer snapshot |
| Surveys | Decimal average preserved; bounds per original scale; consolidated identity; both KRA 9 variants; no automatic averaging |
| Evidence | File limits/signatures, invalid links, protected downloads, removal rules, historical retention, no evidence embedded in report PDF |
| Nil | Reason required; no event/evidence requirement; normal review; distinguish Nil from missing submission |
| Progress | Correct scope/year/period filters; status counts; text achievements retained; no invented numeric aggregations |
| Reliability | Renderer unavailable/timeouts, database error, disk-full upload, failed autosave, restart with persistent files, safe retry |
| Recovery | Restore database plus evidence and verify hashes; previous approved PDF downloadable after recovery |
| v2.0 changes | Reject/return after close, or with under 72 hours left, with grant checked creates exactly one grant ending at decision + 72 hours, unchecked creates none, and more than 72 hours left shows no option (C1); reopen request with no prior submission creates one Draft row and one request, a second request is rejected (C2); that row shows as Not submitted while pending/denied and as Draft after first save or first evidence upload (C11); a grant with both or neither of `request`/`review_decision` set is rejected by the database (C1); PDF logos and fonts render with all renderer network/file requests blocked (C12); evidence upload during an in-flight autosave causes no 409 and no lost input (C3); 4+ simultaneous PDF exports never exceed the renderer pool and API stays responsive (C4); Drive link saves with null file fields, FILE row without checksum is rejected (C5); removed evidence does not count toward 100 MB, 500 MB history cap enforced (C6); preview keeps scroll position while editing a 50-row table (C7); dashboard banner shows active grants only and disappears at expiry (C9) |

Use meaningful integration tests and browser workflows, not tests that only repeat constants. Validate PDFs through text checks plus rendered-page visual review. Capture test commands/results in `docs/validation.md`.

## 13. Deployment runbook requirements

1. Confirm server prerequisites and choose Docker Compose or native systemd deployment; do not assume either is permitted.
2. Build pinned backend/frontend/browser images or environments. Serve compiled frontend and proxy `/api` on one origin.
3. Keep PostgreSQL and internal renderer services off the public network. Use persistent DB/media/generated-document volumes.
4. Set secrets, database URL, allowed hosts, CSRF origins, timezone, private-storage locations, upload limits and renderer limits.
5. Run framework production checks; review migration SQL, back up first, migrate, then seed catalogue idempotently.
6. Provision accounts with secure one-time credentials. Do not put passwords in terminal transcripts, commits or documentation.
7. Enable HTTPS and protection headers; test actual authorized and unauthorized downloads.
8. Verify every critical workflow using staging data; remove staging access/data from production.
9. Set backup jobs, off-server storage, disk alerts and service health checks; test restoration to an isolated environment.
10. Record release commit/image versions and migration state. Keep previous image/config; rollback application safely only with compatible schema, otherwise restore using a documented recovery procedure.
11. Document incident ownership, account reset, adding years/templates, restarting services, reviewing logs and restoring files.

## 14. Definition of done and explicit exclusions

Release is complete only when:

- Every numbered KRA has a reviewed form, correct mapping, live preview and readable consolidated PDF.
- Separate Dean/VC login portals and dashboards work; Dean isolation and VC authority are enforced for all API/file paths.
- Draft, Nil, review, correction, immutable approval history, deadlines and reopening work as specified.
- Annual targets are fixed, future-year setup works, existing achievements are not imported.
- PDFs show the correct verification text; evidence is downloaded separately.
- VC progress output reflects actual stored data and selected filters.
- Backups, recovery, deployment documentation and team acceptance are complete.

Excluded: extra workbook target sections, automatic achievement percentages/totals, individual survey collection/averaging, additional institutional roles, public signup, visual no-code template designer, AI-generated claims, DOCX export, Drive synchronization, digital certificates, email/WhatsApp notifications and mobile apps.

## 15. Handoff checklist for the project owner

- [ ] Give Claude Code this Markdown file, the workbook/Markdown conversion and all source PDFs.
- [ ] Confirm canonical department names and review extracted targets before production seeding.
- [ ] Review the new/adapted templates and consolidated-survey treatment during the pilot.
- [ ] Supply college server specifications before deployment architecture is finalized.
- [ ] Provide actual VC/Dean names and account identifiers through a private provisioning process.
- [ ] Nominate who accepts template output and who operates backups/server recovery.
- [x] Approve C1 (72-hour grant option on reject/return when closed or closing within 72 hours).
- [ ] Decide whether the deferred evidence ZIP download (C10) is wanted after the pilot.

## 16. Official implementation references

Consult the documentation for the selected supported versions at implementation time:

- Django deployment overview: https://docs.djangoproject.com/en/5.2/howto/deployment/
- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Django supported versions: https://www.djangoproject.com/download/#supported-versions
- Django REST Framework permissions: https://www.django-rest-framework.org/api-guide/permissions/
- Playwright Python PDF API: https://playwright.dev/python/docs/api/class-page#page-pdf
- PostgreSQL documentation: https://www.postgresql.org/docs/

These references inform technical implementation; the user-approved requirements in this plan remain the product authority.
