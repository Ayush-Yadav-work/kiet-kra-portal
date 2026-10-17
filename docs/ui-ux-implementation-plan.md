# KIET KRA Portal — UI/UX implementation plan

Version 1.0 · 17 October 2026 · Proposed design, pending owner visual review

## 1. Placement and authority

Save this file as `kiet-kra-portal/docs/ui-ux-implementation-plan.md`, alongside `docs/implementation-plan.md`.

This is a presentation and interaction extension between Phase 6C and Phase 6D. It does not replace the v2 implementation plan, business rules or recorded decisions. Explicit owner decisions take precedence. Link this document from the main plan and progress log when beginning UI-0; preserve historical entries.

Implement one bounded phase at a time. Complete its checks, present the result and stop for owner review before the next phase. Do not implement the entire document in one session. Commit/push only when the owner instructs; deployment is outside this plan.

## 2. Starting point and objective

Reported baseline: all 45 KRA templates implemented; Phase 6C plus its focused follow-up completed. Last reviewed evidence: 506 backend tests at Phase 6B, 26 isolated browser tests and a successful frontend build after the 6C follow-up. These are reported results, not checks performed while authoring this plan. Verify current Git state and current docs before editing; preserve any uncommitted work.

Objective: a professional KIET reporting portal that helps Deans complete reports and the college-wide VC review them efficiently. Use clear hierarchy, restrained colour, readable forms and helpful feedback. Familiar college branding should coexist with a task-focused application layout.

Out of scope: new business features, schema/API redesign, automatic achievement calculations, new permissions, template-policy decisions, deployment infrastructure and PDF redesign. Existing template-introduction wording issues and outstanding college decisions remain tracked separately.

## 3. KIET-inspired design foundation

Source: https://www.kiet.edu/ and its linked stylesheets inspected on 17 October 2026. Values below were found in website CSS; they are not asserted to be a formally approved brand manual. Supporting application colours are proposals.

| Token / purpose | Value | Origin / use |
| --- | --- | --- |
| Brand primary | `#1B4568` | Website `--kiet-color-primary`; brand/nav emphasis |
| Action primary | `#085290` | Website `--color-primary`; primary actions and links |
| Brand accent | `#F15B20` | Website secondary; restrained accents |
| Accent light | `#FC743E` | Website accent; decoration only until contrast verified |
| Heading | `#0C2D47` | Website heading colour |
| Body text | `#2C2B2B` | Website body colour |
| Canvas | `#EAF0F2` | Website background; application canvas |
| Subtle surface | `#F0F4F5` | Website light surface |
| Surface | `#FFFFFF` | Cards, forms, tables |
| Muted text / control border | `#62748E` | Proposed, carried from prior contrast fix; verify each background |
| Success | `#166534` on `#F0FDF4` | Proposed approved/success state |
| Warning | `#92400E` on `#FFFBEB` | Proposed attention/deadline state |
| Error | `#B91C1C` on `#FEF2F2` | Proposed rejected/error state |

Measure actual computed colour pairs after implementation. Use at least 4.5:1 for normal text and 3:1 for large text and applicable non-text controls. Do not assume orange with white text passes. Blue with white text is the default primary button direction. Use pale borders for decoration only; essential input boundaries need adequate contrast.

Define semantic CSS variables in the existing global style mechanism: brand, action, canvas, surface, heading, text, muted, border, focus and status states. Map existing Tailwind/shared components to them; avoid spreading raw hex codes across screens. Inspect the installed Tailwind version before choosing configuration syntax.

Typography: retain the current readable UI font initially. Poppins is a possible heading option inspired by the website, subject to UI-0 comparison; do not introduce external font requests unnecessarily. Use approximately 16px body/input text, 14px compact table text and 24–30px page headings. Report fonts remain unchanged.

Use an 8px-based spacing rhythm with 4px increments where needed; approximately 8px control radii and 12px card radii. Prefer modest shadows and clear borders. Buttons should have consistent heights, typically 40–44px, with comfortable touch targets.

Use the existing icon library. Icon-only actions require accessible names. Use the original approved KIET logo at its proper aspect ratio; do not recreate or recolour it. If a required asset is missing, record that and use a text placeholder in previews rather than inventing a logo.

## 4. Protected behaviour

- Exactly one college-wide VC; department-scoped Deans; existing routes and backend authorization.
- Separate Dean/VC login routes and fixed-role login behaviour. No public registration.
- Academic-year/period filtering, annual immutable targets and exact target/achievement text.
- Save queue, dirty/unsaved state, conflict handling, stale-response protection and explicit reload behaviour.
- Submission/revision history, rejection reasons, Nil reports and scoped 72-hour grants.
- Report, Evidence and Achievement tabs; evidence downloaded separately; preview only in its appropriate workspace context.
- Conditional field retention/clearing rules; hiding a field must not change stored data.
- Original preview/PDF layouts, fonts, logos, labels and pagination.
- Phase 6C accessibility improvements and private-storage/test isolation.

Scope theme styles to the application shell. Avoid global selectors that leak into report HTML, iframe documents or server-rendered PDF templates. Reuse existing data and endpoints; new summaries requiring unavailable data are deferred rather than fabricated.

## 5. UI-0 — inventory and visual direction

### Work

1. Read repository instructions and current phase/validation docs. Record baseline commit, dirty files and affected frontend paths.
2. Inventory routes, shared components, styles, icons, branding assets and tests. Locate actual files; names such as Shell, SchemaForm, Workspace and ReviewPage are clues, not guaranteed paths.
3. Capture current login, Dean dashboard, VC progress and workspace views using synthetic data in an isolated environment. Keep screenshots local to project review artifacts, free of real records/secrets.
4. Prepare a concise proposed login and Dean-dashboard visual preview, plus button/input/status examples. Use existing tooling and no real business mutations. Any temporary preview route must remain development-only and be removed before release.
5. Explain navigation and spacing choices; confirm branding assets. Owner reviews the proposed direction before UI-1.

### Deliverable and exit

Record inventory, design decisions, preview paths and remaining questions in `docs/ui-ux-review.md`. Reuse one document for later phase review notes. Exit: owner accepts the visual direction. No broad application restyling during UI-0.

## 6. UI-1 — shared components, shell and login

### Work

- Implement semantic tokens and shared button variants: primary, secondary, quiet and destructive. Provide hover, focus, disabled, loading and error states.
- Standardize fields, labels, help text, validation messages, cards, status badges and alert patterns. Preserve accessible names and error associations.
- Implement the approved application shell. Proposed direction: compact desktop sidebar, restrained header and mobile navigation drawer. Keep navigation limited to existing authorized destinations. Drawer keyboard focus, Escape and focus return must work.
- Show department/role and year/period context without introducing a second conflicting filter state.
- Login landing, if the root route supports it: original logo, “KRA Reporting Portal”, two role choices linking to existing login routes. Keep each role's form concise, with existing validation, password visibility where supported and login/loading errors.
- Optional campus imagery is limited to login and requires owner approval of the asset. Use restrained saturation/overlay without making text hard to read. Do not place decorative campus backgrounds behind working forms/tables.
- Keep password-change and logout flows intact. Avoid global autosave or navigation remounts caused by shell restructuring.

### Exit

Both roles can sign in through their existing portals and navigate by keyboard/mobile. Wrong-role credentials remain rejected. Shared components have measured contrast and visible focus. Owner reviews desktop/mobile login and shell screenshots before UI-2.

## 7. UI-2 — dashboards, filters and tables

### Dean dashboard

- Clear department title, academic year and reporting period.
- Prominent existing reopening countdown and rejection feedback.
- Make available next actions legible: continue draft, view submitted report or correct rejection. Do not change status rules.
- Present existing counts only; no achievement percentages, rankings or invented totals.
- Consistent report list/table with KRA, exact target, status and one clear row action. Long text should wrap or be expandable; essential information must remain accessible.

### VC progress

- Group existing filters clearly; preserve selected values, URL state and back-navigation behaviour.
- Status cards may select the existing status filter. Explicitly explain that summary counts apply other filters but exclude the selected status filter.
- Readable submission/achievement source labels, Nil badges, review actions and export feedback.
- Preserve pagination and export of all matching rows. Clearly distinguish table page size from export coverage.

### Shared patterns

Use table-local horizontal scrolling or readable mobile cards, stable loading skeletons only for actual loading, useful empty states and clear filter reset. Maintain row identity, request cancellation/stale guards and keyboard reachability. Hover feedback must not be the only way to discover actions.

### Exit

Filtering, rapid year/period changes, pagination, review/back and PDF export pass existing tests. No cross-department data exposure or changed count semantics. Owner reviews both role dashboards before UI-3.

## 8. UI-3 — workspace, evidence, achievement and VC administration

### Report workspace

- Compact report header showing KRA, status, period and exact target with wrapping/expansion for long text.
- Clear Report/Evidence/Achievement tabs with existing keyboard semantics and error indicators.
- Desktop editor/preview split; phone Form/Preview toggle with accessible state. Keep preview scroll preservation and avoid editor remounts.
- Improve section spacing and repeatable-row/event controls. Keep active event selection and typed values through rendering and async responses.
- Position save status, validate, submit and PDF actions consistently. Sticky controls are optional only when they do not obscure focused inputs, errors or mobile content.

### Evidence and achievement

- Clearly distinguish uploaded files and Drive links. Show available metadata, upload feedback and existing protected download/remove actions.
- Use an accessible file picker; drag-and-drop is optional and only if existing upload behaviour can be reused without expanding scope. Never invent percentage progress when byte progress is unavailable.
- Keep evidence limits and errors visible. Pending, failed and successful uploads must look different.
- Group achievement and remarks fields clearly; preserve exact values, Nil behaviour and existing period handling.

### VC review, reopening and management

- Clearly separate submitted report, evidence and achievement; preserve exact revision/history context.
- Make approve/reject/return actions distinct. Keep mandatory reasons and current reopening options unchanged.
- Improve assignment/KRA forms and finalization summary using shared components. Preserve immutable assigned targets, existing confirmations and compatible-template selection.
- Reuse existing inline regions/native confirmations unless a replacement is specifically justified and fully accessible.

### Exit

Complete isolated Dean-to-VC workflow plus Nil and reopening checks. Verify inactive values, optimistic conflicts, evidence uploads and rejected resubmissions still behave correctly. Compare representative report HTML/PDF output with the baseline; theme changes should produce no report-layout differences.

## 9. Interaction and motion rules

Use short 120–180ms colour/opacity transitions, clear pressed states and stable feedback. Respect `prefers-reduced-motion`. Avoid animated counters, autoplay content, moving backgrounds, parallax, continuous pulses and decorative loading delays.

Use inline errors for actionable failures; retain existing persistent conflict/unsaved warnings. Toasts may supplement but never replace essential errors or state. Announce save/upload status without repetitive screen-reader chatter. Do not label data “Saved” before server acknowledgement.

## 10. Verification and review gates

| Check | Required evidence |
| --- | --- |
| Development safety | Disposable test database, synthetic users and isolated media; preserve working data |
| Build | Existing TypeScript/frontend build passes after frontend changes |
| Behaviour | Focused regressions during work; full isolated browser suite once after shared-component changes in each phase |
| Backend | Relevant tests if backend changes are truly necessary; avoid backend changes for restyling |
| Responsive | Approximately 1440/1280 desktop, 768 tablet, 375 phone, and 320px reflow spot check |
| Zoom | Actual browser zoom at 200%, documented method; narrow viewport is not represented as browser zoom |
| Keyboard | Navigation, tab controls, fields, dialogs/drawers, repeatable rows, errors and focus return |
| Contrast | Computed foreground/background measurements for default, focus, hover, error and status states |
| Accessibility | Useful labels/live regions, no colour-only meaning; screen-reader spot check recorded or explicitly pending |
| Data safety | No loss on tab switching, section hiding, save conflicts, delayed responses or navigation |
| Reports | Representative preview/PDF comparisons show branding restyle did not alter report templates |
| Owner review | Before/after screenshots and an explicit recorded decision at each phase boundary |

Update `docs/progress.md`, `docs/validation.md` and `docs/ui-ux-review.md` with actual results. Keep existing test counts as historical baselines; never claim reruns or human acceptance that did not occur. If a check cannot be performed, record the limitation and concrete manual steps.

## 11. Completion and return to Phase 6D

UI work is complete when UI-1 through UI-3 are reviewed, the regression suite/build pass, key screens are usable on mobile/keyboard, contrast is measured and no unresolved critical workflow regression remains. Track minor issues with owners rather than silently dropping them.

Institutional acceptance of all 45 report formats remains a separate gate. Real browser zoom/screen-reader checks remain pending until performed. College-server security/configuration, shared throttling, upload scanning, backups and deployment remain Phase 6D/7 work.

After UI acceptance, resume Phase 6D against the updated frontend baseline. Do not deploy solely because the interface looks complete.

## 12. First Claude Code prompt — UI-0 only

```text
Read docs/ui-ux-implementation-plan.md, repository instructions and current progress/decisions. Execute UI-0 ONLY: inventory the current frontend, verify Git state, inspect shared components/assets, and prepare a login + Dean-dashboard visual direction with shared control examples.

Use the KIET palette and protected-behaviour rules in the plan. Preserve all existing work. Use isolated synthetic data. Do not change application business logic, report/PDF templates or working data. Do not start UI-1, commit, push or deploy.

Record actual component paths, proposed tokens/layouts, preview locations and questions in docs/ui-ux-review.md. Use existing preview tooling; any temporary preview must be development-only. Show the concrete proposed designs for owner review, then stop. If a required logo/photo is absent, identify it and use a labelled placeholder rather than inventing it.

Inspect narrowly, reuse existing components and omit repetitive narration. Do not sacrifice correctness or accessibility for token savings.
```
