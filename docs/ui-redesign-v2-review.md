# UI redesign v2 — review notes

Status: implemented, **uncommitted for visual review** (2026-10-20). References: `reference/ui/redesign-v2/` (11 images, all
opened). Presentation only: no backend, schema, route, permission or API change.

## Reference → route mapping

| Reference image | Route(s) / role | Used as |
|---|---|---|
| `KIET KRA Tracker Login Portal.png` | `/`, `/dean/login`, `/vc/login` (also `/change-password`, same layout) | Login layout |
| `login page background image.png` | login background | Byte-identical to the existing `src/assets/login-background.jpg` source; kept |
| `Background image.png` | page hero band (Dean/VC dashboards, Analytics, Annual assignments) | Converted to `src/assets/campus-banner.jpg` (2103×748, JPEG q78, 421 KB), decorative |
| `KIET KRA Reporting Dashboard (1).png` | `/vc/dashboard` (VC) | VC dashboard; its pattern is also applied to `/dean/dashboard` (no Dean-specific reference exists) |
| `KIET KRA Reporting Portal Dashboard.png` | `/vc/kras` (VC) | KRA catalogue (despite its file name, the screen is "Installed KRAs") |
| `KIET Annual Assignments Dashboard.png` | `/vc/assignments` (VC) | Annual assignments |
| `KIET University Announcements Dashboard.png` | `/vc/announcements` (VC); style carried to `/vc/announcements/:id`, `/dean/announcements` | Announcements |
| `University KRA Analytics Dashboard.png` | `/vc/analytics` (VC) | **Primary** analytics layout (cards, matrix, department progress, report slots) |
| `KIET University Analytics Dashboard (1).png` | `/vc/analytics` | Alternative; its "Submission status overview" bar chart is used in the left analytics panel |
| `KIET University Analytics Dashboard.png` | `/vc/analytics` | Alternative; matrix legend and slot table styling only |
| `KIET KRA Analytics Dashboard.png` | — | Not used: dark navy header, a different institution name ("KIET Group of Institutions") and a faculty user conflict with the white horizontal header used by every other reference |

The four analytics images are alternatives for one screen, not separate screens. The header differs slightly between
references (one row vs two rows); the two-row version (brand + user on top, navigation below) is used for both roles,
because it is the majority pattern and fits seven VC links.

## What changed

Shared (`frontend/src`):
- `index.css` — lighter page canvas, `panel` surface (rounded, soft shadow, positioned so screen-reader-only text cannot
  widen the page), `thead-soft` table headers, softer `card`. Tokens otherwise unchanged (contrast-vetted in UI-1).
- `components/page.tsx` (new) — `PageHero` (title band with the campus photo faded in on the right), `Panel`,
  `DeptChip`, numbered `Pager`, `EmptyState`, `IconSelect` (labelled select with icon).
- `components/ui.tsx` — two-row header for both roles (logo │ "KRA Reporting Portal" … initials, name/role, Sign out
  with icon; horizontal nav with icons, orange active underline, sideways scroll on phones); `StatCard` gains an optional
  share (% and bar) and the reference icons; nav icons (Analytics chart, KRAs layers).
- `components/icons.tsx` — 20 more inline icons (no icon library).
- `assets/campus-banner.jpg` (new).

Screens:
- Login (`auth/LoginPage.tsx`): full-bleed campus photo, official logo on a white plate, "KRA Tracker / Key Result Area
  Portal / Track. Review. Lead." hero, sign-in card ("Welcome back", Dean/Vice Chancellor toggle, visible Username and
  Password labels, orange Sign in). Stacks on phones.
- Dean dashboard: hero with year/period card, status cards with shares (still filter buttons, `aria-pressed`, URL
  `status`, counts unchanged), panels for notices/attention/report table.
- VC dashboard: hero, seven cards in one row at ≥1280 px, icon filters, navy Export PDF, "Department-wise KRA status" panel
  with department chips and numbered pages (the "N rows · page X of Y" text is kept).
- Analytics: hero with the filter panel inside, five bucket cards (% of expected), "Submission status overview" (rate,
  "X of Y reports approved", bar chart of all seven buckets), "Department progress" list (+ comparison table for ≥2
  departments), period trend, colour-graded Department × KRA matrix with legend, report slots with status pills and
  numbered pages. Department list closes on outside click / Escape.
- Annual assignments: hero with year/KRA selects, year card with Draft/Removed/Finalised chips, icon buttons, pill filter
  tabs with icons, upper-case table headers, per-row **Allocate** button on unallocated rows, numbered pages.
- KRAs: three summary cards, search (KRA, activity, NBA/NAAC, format), coloured format pills by template family.
- Announcements (VC list): icon heading, New announcement, four totals cards, filter panel, table with pinned marker,
  body excerpt, state pill, audience, read count, Open action, numbered pages. Editor, Dean inbox, reopening queue,
  bulk/pending panels: same surfaces and heading style.

Unchanged by design: report workspace, review page, report previews (iframe documents) and PDFs (server-rendered) —
portal CSS does not reach them.

## Deviations (justified)

- **Product name**: header keeps "KRA Reporting Portal"; the login hero uses the reference's "KRA Tracker" wording and the
  card says "Sign in to the KRA Reporting Portal".
- **Login fields**: "Username" instead of "Institutional Email" (accounts sign in with usernames); no "Remember me" /
  "Forgot password?" (no backend support; not invented). Role toggle reads "Vice Chancellor" instead of "VC".
- **Orange**: buttons and the active role use the existing accessible orange `#C8461A` (white text 4.8:1) rather than the
  brighter reference orange (3.4:1).
- **Login photo**: the supplied photograph has a small logo printed in its corner; a white wash softens it so only the
  official logo reads.
- **KRA catalogue**: no NBA/NAAC or format dropdowns and no "View format" button — search covers filtering, and there is no
  blank-format viewer to open. Cards state facts (installed count, developer-managed) rather than "central validation".
- **Announcements**: cards show Total / Published (active) / Drafts / Withdrawn from API totals (Pinned and "departments
  reached" would need every row); no Audience/Search filters (the API filters by state only); no row "…" menu.
- **Analytics**: Scope and Reporting period stay separate selects (the API models scope and period separately); no
  "Recent activity" panel (no such data source); Announce button keeps its full label.
- **Dean dashboard**: no reference exists; it follows the VC dashboard pattern.
- **Assignments**: no kebab menu; the reference's "In preparation" chip is shown as the year state under the year.

## Behaviour fixes found while restyling

- Annual assignments pagination: Next/Previous never changed page (the page parameter was deleted right after being set).
- Pages with wide tables could widen the whole page on phones/tablets through absolutely positioned screen-reader text;
  panels now contain it.

## Validation (actual)

| Check | Result |
|---|---|
| `npx tsc -b`, `npm run build` | OK (bundle 530 kB; existing >500 kB warning) |
| `python e2e/run_isolated.py` (isolated DB, Django, Vite, renderer, worker) | **Ran 29 tests, OK** (after the fixes below) |
| Screenshot capture of 13 screens × 1440 / 1536 / 768 / 375 px on the isolated stack | 52 captures, **0 px page overflow** on every one |
| Backend suite | Not rerun — no backend file changed |

First full browser run: 2 failures, both caused by the redesign and fixed in code or by updating a selector for the new
markup (assertions unchanged in substance):
- UI-2 test parsed every number in the Dean card region; the cards now show shares ("12.5%"), so the parser ignores
  percentages and decimals (it still requires Assigned = sum of the five statuses = table rows). The Dean card locator
  accepts the optional share after the label.
- Phase 1 test: the new empty state was a second `role=status` region (removed — empty states are not live regions); the
  open department list covered the Export buttons in the new layout (the list now closes on outside click / Escape, and the
  test closes it before exporting, as a user would).

Screenshots (git-ignored): `.work/ui-redesign-v2/<screen>-<width>.png`; 1440 px also `-full.png`; 768/375 px also
`-top.png` (first viewport). Screens: `login-landing`, `login-dean`, `login-vc`, `dean-dashboard`,
`dean-dashboard-filtered` (zero-match state), `dean-announcements`, `vc-dashboard`, `vc-analytics`, `vc-assignments`,
`vc-kras`, `vc-announcements`, `vc-announcement-new`, `vc-reopen`. Opened and compared against the references: login,
Dean/VC dashboards, analytics, assignments, KRAs, announcements at 1440/1536, VC dashboard at 768, Dean dashboard,
analytics, assignments and login at 375.

Not verified: real screen readers, browser zoom at 200 %, Safari/Firefox (Chromium only), keyboard focus order beyond the
existing tests, printed pages.

## Manual review checklist

1. Log in as Dean and as VC at your normal screen size; compare with the references.
2. Dean dashboard: click each status card and Assigned; change period; check the zero-match message.
3. VC dashboard: status cards, filters, numbered pages, Quick preview and bulk approval still work.
4. Analytics: change scope/KRA/departments; open and close the department list (click outside, Esc); export PDF/CSV; the
   matrix colours and the "X of Y reports approved" line.
5. Annual assignments: Copy previous year setup, per-row Allocate, filter tabs, pages 1→2, finalise flow.
6. KRAs: search by number and by word.
7. Announcements: totals, Open a notice, New announcement, Dean inbox and unread badge.
8. Phone (375 px) and tablet (768 px): header nav scrolls sideways, no page-level sideways scrolling.
9. Report workspace, preview and an exported PDF look exactly as before.
