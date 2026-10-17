# UI/UX review notes

Companion to [`ui-ux-implementation-plan.md`](ui-ux-implementation-plan.md). One document for all UI phase reviews; newest phase last.

## UI-0 — inventory and visual direction (2026-10-17) — revision 3 approved by the owner

**Baseline:** branch `phase2-kra33-pilot`, HEAD `0f12a59` (Phase 6C follow-up), equal to `origin/phase2-kra33-pilot` at the last fetch.
Dirty files at start: `KIET_KRA_PROJECT_HANDOVER.md` (untracked, handover) and `ui-ux-implementation-plan.md` (untracked, at the
repository root; moved to `docs/` as the plan itself instructs). No application code, styles, routes, templates, database or uploads
were changed in UI-0.

### 1. Inventory (actual paths)

| Area | Files | Notes / constraints |
|---|---|---|
| Routes | `frontend/src/App.tsx` | `/` inline `Landing` (two role cards), `/dean/login`, `/vc/login`, `/change-password`; `/dean/dashboard`, `/dean/kra/:assignmentId/:periodId`; `/vc/dashboard`, `/vc/review/:submissionId`, `/vc/reopen-requests`, `/vc/assignments`, `/vc/kras`. React Router 7 (`createBrowserRouter`). |
| Shell and guards | `frontend/src/components/ui.tsx` (`Shell`, `RequireRole`) | Top header only (portal name, role text, VC links, Change password, Sign out). Also holds `StatusBadge`, `ErrorBox`, `Loading`, `useServerClock`/`timeLeft` (C9 countdown), `tabKeys` (6C). |
| Login | `frontend/src/auth/LoginPage.tsx`, `AuthContext.tsx`, `ChangePassword.tsx` | Fixed-role forms; show/hide password (`aria-pressed`); wrong-portal notice; rate-limit message comes from the server. |
| Dean dashboard | `frontend/src/features/dean/DeanDashboard.tsx` | `usePeriods`, `YearPeriodPicker` (URL `year`/`period`), `ReopenBanner` (`/reopen-grants/active/`), rejected list, assignments table with one *Open* action. Data per row: KRA number/activity, exact `target_text`, `display_status`, `is_nil`, latest decision (rejected only), template presence. |
| VC pages | `frontend/src/features/vc/VCDashboard.tsx`, `ReviewPage.tsx`, `ReopenQueue.tsx`, `AdminAssignments.tsx`, `AdminKRAs.tsx` | Progress filters in URL; export; review tabs (6C). |
| Workspace | `frontend/src/features/report-builder/Workspace.tsx`, `SchemaForm.tsx`, `Preview.tsx`, `saveQueue.ts`; `features/evidence/EvidenceTab.tsx`; `features/achievements/AchievementTab.tsx` | Protected behaviour (plan §4): save queue, conflicts, stale guards, tabs, conditional retention. Preview is a sandboxed iframe of server HTML — theme must not leak into it. |
| Styles | `frontend/src/index.css` | Tailwind **4.3** (`@import "tailwindcss"`, `@utility btn/btn-primary/btn-secondary/btn-danger/input/label/card`). No `tailwind.config`; tokens would go in `@theme`/CSS variables in this file (UI-1). Colours today: Tailwind blue/slate/amber/red/green. Font: Tailwind default system sans stack. |
| Icons | — | **No icon library is installed** (`package.json`: react, react-dom, react-hook-form, react-router-dom only). Previews use text labels and simple CSS markers; adding a library would be an owner decision (open choice 4). |
| Branding assets | `backend/apps/reports/assets/kiet-logo.png` (974×360, opaque PNG, white background) | Extracted from the college-supplied KRA 33 template (D-010) and used in report headers. No SVG or transparent version and no campus photo exists in the repository. `frontend/public/` holds only `favicon.svg`. |
| Preview / test tooling | `e2e/run_isolated.py` + `e2e/test_browser.py` (Playwright, disposable `<db>_e2e`, `.work/e2e/private`), `npm run build`, Playwright in `.venv` | Used here for current-state screenshots (temporary test method, removed) and for rendering/measuring the static previews. |

### 2. Previews (static, isolated)

Open directly in a browser (no server needed; links in them are inert):

- `docs/ui-preview/login.html` — role choice + Dean sign-in form with error, loading and rate-limit states.
- `docs/ui-preview/dean-dashboard.html` — shell, context, deadline, reopen and rejection feedback, status counts, report list, component/state examples.
- `docs/ui-preview/preview.css` — the proposed tokens and components (preview only).

They live under `docs/`, are plain HTML/CSS with no build step, reference the logo by relative path, and are **not** imported by
`frontend/` — the live portal and its production bundle are unaffected. Delete or keep them as design records after review.

Screenshots (git-ignored, local review artifacts, synthetic data only):

| Proposed | Current (live app, isolated runner, demo data) |
|---|---|
| `.work/ui-review/proposed/login-desktop.png`, `login-mobile-375.png`, `login-focus.png` | `.work/ui-review/current/landing-desktop.png`, `dean-login-desktop.png` |
| `.work/ui-review/proposed/dean-dashboard-desktop.png`, `dean-dashboard-mobile-375.png`, `dean-dashboard-focus.png` | `.work/ui-review/current/dean-dashboard-desktop.png`, `dean-dashboard-mobile-375.png` |
| — | `.work/ui-review/current/workspace-kra33-desktop.png`, `vc-progress-desktop.png` |

### 3. Design direction

- **Login:** one card on the `#EAF0F2` canvas; left panel with the original logo (unaltered, correct aspect ratio), "KRA Reporting Portal", a plain description and who-does-what; a single 4 px KIET-orange rule is the only orange. Right panel: two large role choices (Dean, Vice Chancellor) leading to the existing `/dean/login` and `/vc/login`. The sign-in form keeps the current fields, show/hide and messages; errors sit under the field (`aria-describedby`) with an icon + text.
- **Dean dashboard:** desktop sidebar (white, logo, product name, *My KRA reports*, *Change password*, user and *Sign out* at the foot — only existing destinations) with the active item in brand blue `#1B4568`; phone: top bar with logo and *Menu* (drawer behaviour belongs to UI-1). Page header: department (eyebrow), "KRA reports", year and period selects (the existing URL-backed picker). A window strip states open/closed and the closing time from server data. The existing reopen banner (warning) and rejection list (error) move to the top with one explicit action each. Status counts are the existing rows counted by status — no percentages or rankings. The list keeps KRA, activity, exact target and status, with one action whose wording follows the existing status ("Start report", "Continue draft", "View submitted", "Correct and resubmit", "View"); on phones rows become labelled cards.
- **Spacing/shape:** 8 px rhythm (4 px steps), 16 px body and inputs, 14 px tables, 24–28 px page title; 8 px control radius, 12 px card radius; 42 px controls (36 px compact in tables); subtle shadow plus a light divider border.
- **Feedback:** focus = 3 px `#085290` outline with 2 px offset everywhere; status badges always carry text (dot + label), Nil is a separate outlined tag; alerts use a 5 px left bar + heading + text; loading is a static skeleton plus "Loading…" text (no animation); colour transitions 150 ms only when reduced motion is not requested.

### 3b. Revision 3 — owner reference images (2026-10-17) — supersedes §3 and §3a

References: `reference/ui/login-reference.png`, `reference/ui/dean-dashboard-reference.png` (owner-provided; untracked). They replace the
earlier direction, including the sidebar proposal. Previews rebuilt in real HTML/CSS at the same paths (`docs/ui-preview/login.html`,
`dean-dashboard.html`, `preview.css`); screenshots regenerated in `.work/ui-review/proposed/`.

**Login (follows the reference composition):** full-page background, centred white card, original logo, "KRA Reporting Portal" between
rules, "Sign in" heading with one line of guidance, Dean / Vice Chancellor segmented selector, username and password fields with icons,
show-password toggle, full-width orange sign-in button, one-line access note.
**Dean dashboard (follows the reference layout):** horizontal header (logo, product name, nav with underline, initials avatar, name/role,
Sign out); title + department row with year/period filters aligned right; open-window line; six compact summary cards; one
"Needs your attention" section; "P2 Reports" table with count legend, status pills, details and one action per row.

**Deviations from the references (intentional) and why:**

| Reference shows | Preview does | Reason |
|---|---|---|
| Campus photograph behind the card | Owner-supplied `reference/ui/login-background.png` (1672×941) as a CSS background: `cover`, anchored top-left on desktop (keeps the photo's own logo watermark and the water tower whole), 62%/bottom on phones (building and greenery below the card); slight desaturation (`saturate(.85)`) and a 22% navy overlay; no blur | Supplied 2026-10-17 after revision 3; the placeholder is removed |
| Logo with "Empowering Minds. Enabling Skills." banner; header logo "Engineering Values" | The logo PNG we have, unaltered | The tagline/variants are not in the available asset; not recreated |
| "KRA Tracker Portal" | "KRA Reporting Portal" | Current product name in the app and plan; owner may choose |
| "Institutional Email" field | "Username" | Login uses usernames; email login is not implemented |
| "Forgot Password?" link | Omitted | No password-reset feature exists (accounts are reset by the administrator) |
| Orange `#F15B20` button with white text | `#C8461A` (KIET orange, darker) | White on `#F15B20` measures 3.36:1; `#C8461A` measures **4.83:1** |
| "VC" in the selector | "Vice Chancellor" | Clearer; fits at 375 px with icons hidden on phones |
| Selector toggles one form | Two links to the existing `/dean/login` and `/vc/login` routes, current one marked `aria-current` | Keeps the separate fixed-role logins |
| Nav: Dashboard, My KRA Reports, Change Password | Dashboard, Change password | "My KRA Reports" is the same page as the dashboard today; no duplicate destination |
| Header photo avatar, dark slanted corner | Initials avatar; no decorative corner | No photos stored; decoration omitted |
| Cards: Total, Draft, Submitted, **Returned**, Approved, **Needs attention**; counts did not reconcile | Assigned 45 = Not submitted 30 + Draft 9 + Submitted 4 + Rejected 1 + Approved 1 | Existing statuses only (a VC "Return" also results in Rejected); "needs attention" is a separate list, not a workflow total |
| "View … reports" links on cards | Omitted | The Dean dashboard has no status filter; adding one would be a new feature |
| Attention row "Deadline 15 Oct 2026, 11:05" for the returned item | "Period closes 1 Nov 2026, 00:00 IST"; the 15 Oct time is shown as when it was rejected | 15 Oct is the decision time, not a deadline; reopened item shows "Reopening ends" (grant expiry) |
| "View all pending" link | Omitted | No such page |
| Sort arrows on every column; "Page 1 of 7" | No sort controls; footer says all 45 rows show on one page | Sorting and pagination do not exist on the Dean dashboard |
| "Last Update" column with dates for every row | "Details": rejection date/time (available), "Awaiting VC review", "Approved by the VC", "Not yet submitted", "—" | The dashboard API has no last-updated time per row (only the latest decision for Rejected rows); adding it would be a backend change |
| Rows ordered by urgency | KRA order | Current order; urgent items are in the attention section |
| Phone layout not provided | Designed for 375 px: wrapped header nav, stacked filters, 2-column cards, stacked attention items, table rows as cards (legend hidden; cards carry counts) | Requested mobile adaptation |

**Missing assets:** official logo files (SVG/transparent PNG) and the tagline version if wanted. Campus photograph supplied 2026-10-17;
it carries its own KIET logo watermark (top-left), visible on desktop next to the card logo. **Owner choices:** product name ("KRA Reporting Portal" vs "KRA Tracker Portal"); keep the orange sign-in button at `#C8461A`.

**Checks (revision 3):** login and dashboard at 1440 px and 375 px — no console errors, 0 px horizontal overflow, logo loads, **0
contrast failures**. Lowest measured pairs: control border on page canvas 4.23 (≥ 3), control border on white 4.76, white on the orange
button 4.83, muted text on white 5.95. Visible 3 px focus outline (`#085290`) retained; icons are `aria-hidden` with text labels; the
password toggle has an accessible name and `aria-pressed`. Real 200% zoom and screen readers remain unverified.

### 3a. Revision 2 (2026-10-17, after owner feedback) — supersedes §3 where they differ

The earlier acceptance was withdrawn as accidental; the previews were refined (same palette and tokens), not replaced.

- **Login:** one compact card — logo, "KRA Reporting Portal", two role rows (Dean / Vice Chancellor, one line each). Removed the eyebrow, introduction paragraph, feature list and the second decorative panel. The role form is a plain card: title, fields, show/hide, inline error ("Error: …" text, not colour alone), Sign in, "Choose a different role". Loading and rate-limit states moved to a small labelled reference card.
- **Dean dashboard:** the sidebar became a slim top bar (logo, product name, *My KRA reports*, *Change password*, name/role, *Sign out*) — only existing destinations; on phones the links wrap under the logo (no fake menu button). Hierarchy by type and alignment: "KRA reports" title, department beneath, year/period selects aligned right, one line for the open window and closing time.
- **Notices:** the separate reopen and rejection banners became one proportionate "Needs your attention (n)" list with one secondary action per item.
- **Status summary:** the five count cards became one inline count line in the list header (counts of existing rows only).
- **Table:** rows needing action first; the next action is the only primary button on actionable rows (Correct and resubmit, Continue draft); Start report is secondary; View is a link. Status labels are small rectangles (4 px radius) instead of pills; the table text is 15 px.
- **Content:** activities and annual targets are the workbook's ECE text, shown exactly (including a long KRA 43 target); statuses, dates, names and reasons remain synthetic and labelled.
- **Shape:** control radius 6 px, card radius 8 px, no shadows on cards, orange limited to a 3 px rule on the login cards.
- **Checks (revision 2):** login and dashboard at 1440 px and 375 px — no console errors, 0 px horizontal overflow, logo loads, **0 contrast failures**; lowest pairs: control border on canvas 4.14, control border on white 4.76, muted text on canvas 5.17, error text on its tint 5.86. Screenshots were regenerated under the same paths (§2). Real 200% zoom and screen readers remain unverified.

### 4. Proposed tokens (measured)

| Token | Value | Use | Measured contrast |
|---|---|---|---|
| `--brand` | `#1B4568` | active navigation, brand rules | white on it 10.01; on canvas 8.70 |
| `--action` | `#085290` | primary buttons, links, focus | white on it 8.02; on white 8.02; on canvas 6.96 |
| `--accent` | `#F15B20` | 4 px decorative rules only | 3.36 vs white — **not** for text or behind white text |
| `#FC743E` (accent light) | not used | — | 2.72 vs white |
| `--heading` | `#0C2D47` | headings, labels | 12.31 on canvas |
| `--text` | `#2C2B2B` | body | 14.12 on white; 12.27 on canvas |
| `--muted` | `#55657A` (proposed; darker than the plan's `#62748E`) | hints, secondary text, placeholders | 5.95 on white; 5.17 on canvas — `#62748E` gives only **4.14** on the canvas |
| `--border-strong` | `#62748E` | input/select/secondary-button boundaries | 4.76 on white; 4.14 on canvas; 4.30 on `#F0F4F5` (≥ 3) |
| `--border` | `#D3DDE3` | decorative card dividers only | — |
| `--canvas` / `--surface-subtle` / `--surface` | `#EAF0F2` / `#F0F4F5` / `#FFFFFF` | page / panels / cards | — |
| Status OK / warning / error / info / neutral | `#166534` on `#F0FDF4` · `#92400E` on `#FFFBEB` · `#B91C1C` on `#FEF2F2` · `#085290` on `#EAF2FA` · `#334155` on `#F1F5F9` | badges, alerts | 6.81 · 6.84 · 5.91 · 7.09 · 9.45 |
| Disabled button | `#5D6B7C` on `#E2E8ED` | inactive controls (exempt) | 4.40 |

**Measured on the rendered previews** (computed colours through a canvas, alpha composited over the real background; text 4.5 / large 3,
placeholders 4.5, control boundaries 3): login and dashboard at 1440 px and 375 px — **0 failures**; lowest pairs: input boundary on
canvas 4.14, on the error alert 4.35, on `#F0F4F5` 4.30; muted text on canvas 5.17. Focus outline `#085290`: 8.02 vs white, 6.96 vs
canvas, 7.24 vs `#F0F4F5` (offset 2 px, so it sits on these surfaces, not on the brand-blue active item). Console errors: none. Horizontal
overflow: 0 px at 1440 and 375. Images: logo loads on all four.
**Not measured:** hover states beyond colour values listed, real 200% browser zoom (not drivable in automated Chromium — see Phase 6C
follow-up), screen readers.

### 5. Component mapping (for UI-1; nothing changed yet)

| Preview element | Current implementation to adapt |
|---|---|
| `.btn-primary/-secondary/-quiet/-danger`, sizes | `@utility btn*` in `index.css` (add quiet; heights 42/36 px) |
| `.input/.select`, `.label`, `.hint`, `.field-error` | `@utility input/label`; `FieldError` and `Req` in `SchemaForm.tsx`; login form in `LoginPage.tsx` |
| `.badge` variants, `.tag-nil` | `StatusBadge` in `components/ui.tsx` (+ Nil text in dashboards) |
| `.alert-*` | `ErrorBox` (ui.tsx), `ReopenBanner` and rejected list (`DeanDashboard.tsx`), reopen/closed notes in `Workspace.tsx` |
| sidebar / topbar | `Shell` in `components/ui.tsx` (keep links; add drawer with focus/Escape/return in UI-1) |
| window strip, status counts, report list/cards | `DeanDashboard.tsx` (period data from `usePeriods`, rows from `/assignments/`) |
| login card + role choices | `Landing` in `App.tsx`, `LoginPage.tsx` |
| tokens | CSS variables / Tailwind `@theme` in `index.css`, scoped to the app shell (never the preview iframe or PDF templates) |

### 6. Open choices for the owner

1. **Logo asset:** the only copy is the PNG extracted from the KRA 33 template (white background, 974×360). Please confirm it may be used in the portal UI, or supply the official logo (ideally SVG/transparent PNG) — it is used here unaltered.
2. **Navigation:** horizontal header per the owner's reference (revision 3); the sidebar proposal is withdrawn. VC links (progress, reopening, assignments, KRAs) would sit in the same header.
3. **Heading font:** system UI font kept (no external requests). Poppins (as on kiet.edu) is optional; it would need to be self-hosted.
4. **Icons:** none installed; text-only actions are proposed. An icon library would be a new dependency.
5. **Status counts on the Dean dashboard:** shown as one inline line of counts of the existing list (revision 2); confirm they are wanted.
6. **Muted text colour:** `#55657A` proposed instead of `#62748E` so secondary text passes on the canvas.
7. **Campus photo:** supplied (`reference/ui/login-background.png`) and used in the login preview; confirm it is approved for the live portal and whether its built-in logo watermark is acceptable.
8. **Landing copy:** "KIET Deemed to be University" / "KRA Reporting Portal" and the three explanatory lines — please confirm or edit.

### Owner decision

- [x] Login background treatment (campus photo, overlay, crops at 1920/1440/1366/375 px) approved by the owner, 2026-10-17. This is a partial decision; the overall UI-0 direction stays open.

- [x] Visual direction accepted for UI-1: the reference-based revision 3 login and Dean-dashboard previews, including the campus background — approved by the project owner, 2026-10-17. (An earlier acceptance recorded the same day was withdrawn as accidental and is superseded by this one.) Open choices in §6 not explicitly answered keep the preview's choices.

## UI-1 — shared components, shell and login (2026-10-17) — implemented, awaiting owner review

**Changed files:** `frontend/src/index.css` (tokens, shared utilities, focus), `frontend/src/components/ui.tsx` (header shell, status
badge, error box, loading), `frontend/src/components/icons.tsx` (new, inline icons), `frontend/src/auth/LoginPage.tsx` (layout, role
selector, landing, login form), `frontend/src/auth/ChangePassword.tsx` (same layout, error association), `frontend/src/App.tsx` (landing
import), `frontend/src/features/dean/DeanDashboard.tsx` (year/period picker labels above full-width selects on phones — needed because
16 px inputs overflowed 375 px by 1–10 px), new assets `frontend/src/assets/kiet-logo.png`, `frontend/src/assets/login-background.jpg`.
No backend, API, permission, report template or PDF change.

**What is live now:** the approved login on `/`, `/dean/login`, `/vc/login` and `/change-password`; the header on every signed-in page;
shared buttons, inputs, labels, cards, status badges and the error box everywhere they were already used. Dashboard bodies are still the
pre-UI-2 layouts restyled only through the shared components.

**Behaviour kept:** separate fixed-role login endpoints (the selector is two links to the existing routes; wrong-role credentials are
still refused — `test_portals_reject_wrong_role` passes); username (not email) login; the Sign in button stays disabled until both fields
are filled (shown in faded orange); signed-in-elsewhere notice with "Return to my portal"/"Sign out"; must-change-password redirect;
logout from the header; no password-reset link (none exists). Preview banners, sample credentials and demonstration error cards are not
in the live UI; errors appear only when the server returns one.

**Accessibility/contrast (measured in the live app, isolated runner):** no failures on any captured screen; lowest pairs: control border
on the canvas 4.23, control border on white 4.76, white on the orange Sign in button 4.83, muted text 5.95. Inputs keep visible labels
for screen readers (`sr-only` "Username"/"Password" with icons and placeholders, as in the approved design); the password toggle has
`aria-label` + `aria-pressed`; login errors are `role="alert"` and linked to both fields; the logo home link is named "KIET KRA Reporting
Portal — home". Header: single row from 1280 px; below that the links wrap to a second row (no hidden links, no horizontal scrolling) —
the plan's drawer is not used because the approved preview wraps. Phase 6C tests (tabs, accessible names, markers, 375 px) pass.

**Scoping:** tokens and base styles live in the app stylesheet only; the report preview is a separate sandboxed iframe document and PDFs
are rendered server-side, so neither inherits them (preview/export browser tests pass unchanged).

**Screenshots (synthetic demo data, isolated runner):** `.work/ui-review/ui1/` — `landing-*`, `dean-login-*`, `vc-login-desktop`,
`vc-login-focus`, `change-password-*`, `dean-dashboard-*`, `vc-dashboard-*` (`-desktop` 1440 px, `-mobile` 375 px), `vc-header-768/1280/1440`.

**Known/console:** the signed-out `/api/v1/auth/me/` check logs a 401 in the browser console on public pages (existing behaviour, not
an error). Not verified: real 200% browser zoom, screen readers.

### Owner decision (UI-1)

- [x] UI-1 accepted by the project owner after local review, 2026-10-17. UI-2 not started.

## UI-2 — dashboards, filters and report tables (2026-10-17) — accepted by the owner

**Changed files:** `frontend/src/features/dean/DeanDashboard.tsx` (rebuilt body; year/period picker widths), `frontend/src/features/vc/VCDashboard.tsx`
(presentation only — URL filters, stale guard, export and back state unchanged), `frontend/src/components/ui.tsx` (`StatCard`),
`frontend/src/components/icons.tsx` (card/attention/export icons), `frontend/src/index.css` (phone card layout for `.report-table`),
`e2e/test_browser.py` (new UI-2 test; 6C contrast test waits for the colour transition). Docs: progress, validation, this file.

**Dean dashboard (reference structure):** title + department, year/period filters right; window line ("P2 is open · Submissions close … ·
N days left", or closed/not-yet-open); cards Assigned / Not submitted / Draft / Submitted / Rejected / Approved from the loaded rows (they
always reconcile); "Needs your attention (n)" lists Rejected reports of the selected period (title says *Rejected* or *Returned for
correction* from the latest decision, reason and decision time, deadline = reopening expiry if a grant exists, else the period close, else
"Period closed — request reopening from the report") and active reopening grants for any period (deadline = grant expiry; "Current
status" from the grant); a note says these are also counted in the status totals. Table: KRA, activity, exact target (wrapped), status
(+ Nil), details (Rejected/Returned date + reviewer, "Awaiting VC review", "Approved by the VC", "Not yet submitted", "—"), one action
("Start report", "Continue draft", "Correct & resubmit", or "Open report" when the window is closed and no grant; "View" for
submitted/approved; "Template pending" without a template).

**VC dashboard:** same title row; cards toggle the status filter (`aria-pressed`) and a line explains that counts apply every filter
except Status; labelled filter bar with Clear filters and the primary Export PDF (busy text "Preparing PDF…", errors in the alert box)
plus "The PDF contains every row matching these filters, not only this page"; table with achievement source labels ("Submitted revision N ·
date", "Unsubmitted draft — not reviewed", "Edited after submission; not resubmitted"); Review (primary, Submitted rows) or View &
history; "N rows · page x of y" with Previous/Next.

**Deviations from the reference (data/feature limits):** no "Returned" card (a VC Return results in Rejected — wording comes from the
decision instead); no "Needs attention" card (a list, not a workflow total); no "View … reports" links on Dean cards (the Dean dashboard
has no status filter); no "View all pending" link; no sort arrows; no pagination on the Dean list (all assigned KRAs on one page, in KRA
order); no "Last update" dates except the rejection/return decision time (the dashboard API does not return per-row update times);
reopening deadline shown only where a grant exists.

**Localhost review steps:** start the dev services (README), sign in as a Dean → check the cards add up to Assigned, change the period
(P1/P2), open a report from the table; as the VC reject a submitted report → back as the Dean the item appears under "Needs your
attention"; as the VC click a status card (table filters, counts stay), use Clear filters, page with Next, export a PDF, open Review and
use "← Progress" to return to the same filters; repeat at phone width (browser devtools 375 px).

**Screenshots:** `.work/ui-review/ui2/` — `dean-desktop(-top)`, `dean-mobile(-top)`, `vc-desktop(-top)`, `vc-desktop-rejected`,
`vc-desktop-ece-draft`, `vc-mobile(-top)` (synthetic demo data from the isolated runner, including one rejection and one reopening).

### Owner decision (UI-2)

- [x] UI-2 accepted by the project owner after local review, 2026-10-17. UI-3 not started.

