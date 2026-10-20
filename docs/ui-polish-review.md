# UI polish review — overlapping text and hidden selection panel

Status: fixed (2026-10-20); committed together with the login update below (2026-10-21). Bug references: `reference/ui/bugs/` (2 screenshots, both
opened). Presentation only: no API, permission, filter or workflow change; report previews and PDFs untouched (portal CSS
does not reach the preview iframe or server-rendered PDFs).

## Reproduced defects → root cause → fix

| # | Defect (route, reference) | Root cause | Fix |
|---|---|---|---|
| 1 | `/vc/announcements` (~1507 px, `…11.02.19 PM.jpeg`): the body excerpt under each title runs across the State/Audience/Read columns; wrapped audience lists draw on top of it | The excerpt used `truncate` (one line, `nowrap`) inside a flex item without `min-w-0`, so the item never shrank and the line overflowed its table cell; the cell's `max-w-md` has no effect in automatic table layout | Title column gets a share (`w-[36%] min-w-64`), the flex item `min-w-0 break-words`, the excerpt wraps to **two lines** (`line-clamp-2`); the audience text sits in its own shrinkable span; the pin icon cannot shrink; the table's local minimum width rises to 880 px (scrolls inside its panel on narrow screens) |
| 2 | `/vc/analytics` (~1520 px, `…11.04.34 PM.jpeg`): the open **Departments** list is drawn underneath the summary cards | Not a z-index value problem: `PageHero` had `isolation: isolate`, which made the whole hero (and the filter panel inside it) one layer at z-auto. Later siblings that are positioned (the cards — `.panel` is `position: relative`) are painted after it, so the list's `z-10` could never rise above them | Removed `isolate`; the decorative band is `z-0` and the hero content wrappers `relative z-[1]`, so anything opened inside the hero stays above later page content |
| 2b | Same list near the bottom of the window / at 200 % zoom could run off-screen | Fixed `max-h-64`, always below the trigger | On open and on scroll/resize the list measures the space below and above its trigger: it opens upward when there is more room above and caps its height to the space available (120–320 px), scrolling internally (`overscroll-contain`). It stays attached (absolutely positioned on its trigger) |
| 3 | At 1507/1520 px the hero band stopped at the 1440 px content width, leaving uneven grey margins (visible in both screenshots) | The band was sized to the content container | Band spans the full window (`w-screen`, centred); the content keeps the container width; the shell's existing `overflow-x: clip` prevents page overflow |
| 4 | Found while checking other screens: card labels ("Total announcements") ran past their card edge on phones | Text spans inside flex rows without `min-w-0` | Shrinkable label wrappers in `StatCard`, analytics metric cards, the VC "Pending reopen requests" card, KRA info cards and announcement totals; announcement totals stack one per row below 420 px |

Keyboard and dismissal (unchanged behaviour, now covered by a test): the summary is the focusable trigger, options are
native checkboxes (Tab, Space), Escape and outside click close the list, Escape returns focus to the trigger. Option rows
were polished: 36 px minimum height, checkbox top-aligned for wrapped long names, a highlighted selected state.

## Polish pass (affected screens only)

- Announcements: the single "Show" select moved from its own panel into the list panel's header; the header "Read
  (current version)" became "Read" with the meaning in the panel description (it stacked three lines high at 1024 px).
- Dean dashboard: the report table keeps a 900 px minimum width (Activity column ≥ 16 rem) and scrolls inside its panel on
  tablets instead of squeezing text and splitting the "Start report" button over two lines. Phones keep the card layout.

## Changed files

- `frontend/src/components/page.tsx` — PageHero stacking (no `isolate`), full-width band.
- `frontend/src/components/ui.tsx` — StatCard label wrapper can shrink.
- `frontend/src/features/vc/Analytics.tsx` — viewport-aware department list, option rows, metric card labels.
- `frontend/src/features/announcements/VCAnnouncements.tsx` — cell wrapping, column shares, filter placement, totals grid.
- `frontend/src/features/dean/DeanDashboard.tsx`, `features/vc/VCDashboard.tsx`, `features/vc/AdminKRAs.tsx` — local table
  minimum width / shrinkable card labels.
- `e2e/test_browser.py` — new regression test `test_ui_polish_table_cells_contain_text_and_department_list_is_on_top`.

## Validation (actual)

| Check | Result |
|---|---|
| Reproduction before the fix (isolated stack, synthetic announcements with long text and 11-department audiences) | Defect 1: text measured outside its cell; defect 2: department list under the cards (screenshots below) |
| New regression test on the **original** code (fixes stashed, then restored) | **FAILED** as expected (text outside its cell) |
| New regression test on the fixed code | OK |
| `npx tsc -b`, `npm run build` | OK |
| `python e2e/run_isolated.py` (full browser suite, both roles) | **Ran 30 tests, OK** (run before the final phone-grid tweak; the regression test and the capture run were repeated after it: OK) |
| Capture run: 8 screens (VC dashboard, assignments, KRAs, announcements, analytics, reopening requests, Dean dashboard, Dean announcements) × 7 viewports | 56 measurements: **0 px page overflow** and **0 elements outside their table cell** on every one |

The regression test checks, at 1507×710 and 1520×710 (the screenshots), 1440×900, 1024×768, 768×1024, 375×812 and
720×450 (a 1440×900 desktop at 200 % zoom): no element inside an announcements table cell extends beyond its cell; no text
extends beyond its panel (outside deliberate local scroll areas) on Announcements and Analytics; the department list is
within the viewport, its first and last options are the topmost element at their position (so visible and clickable),
Space on a focused option selects it (URL changes) while the list stays open, Escape closes it and returns focus to the
trigger; also with the trigger scrolled near the bottom of the viewport; no page-level horizontal overflow.

Screenshots (git-ignored): `.work/ui-polish/before-*.png` and `.work/ui-polish/after-*.png`, named
`<screen>-<width>.png` for widths 1507, 1520, 1440, 1024, 768, 375 and 720 (200 % zoom). Opened and compared: before/after
analytics department list at 1520 and 720, before/after announcements at 1507, after announcements at 1024 and 375, after
Dean dashboard at 768, after analytics list at 375.

Not executed: real browser zoom (emulated by halving the CSS viewport at 1440×900), non-Chromium browsers, screen readers.

## Remaining limitations

- The department list is the only floating panel in the portal; there is no shared popover component, so the
  viewport-fitting logic lives in Analytics. A shared component is worthwhile if more menus appear.
- At very small heights (e.g. 720×450) the list opens upward over the page heading; it scrolls internally and closes with
  Escape/outside click.
- Wide tables (VC/Dean reports, announcements, analytics slots) scroll inside their panels on tablets by design.

## Manual review checklist

1. `/vc/announcements` with long notices: excerpts stay under their titles (two lines), audiences wrap in their column.
2. `/vc/analytics`: open Departments at your usual window size, near the bottom of the window, and at 200 % zoom; the list
   is on top, fits on screen, scrolls; Tab/Space selects; Esc and clicking outside close it.
3. Phone width: announcement totals and analytics cards keep their labels inside the cards.
4. Dean dashboard on a tablet: the report table scrolls sideways inside its panel; status cards still filter.
5. Report workspace preview and an exported PDF look as before.

## Login pages — `reference/ui/redesign-v2/login-reference.png` (2026-10-21)

The reference first supplied as `login-reference.jpeg` was a copy of the analytics bug screenshot; the owner replaced it
with `login-reference.png` (byte-identical to the earlier "KIET KRA Tracker Login Portal.png", 1672×941), which this
section matches. Applies to `/dean/login`, `/vc/login`, `/` and `/change-password` (shared `LoginLayout`); styles are
local to `auth/LoginPage.tsx`, so dashboards, reports and PDFs are unaffected.

Changes (`frontend/src/auth/LoginPage.tsx`):
- Composition: full-width layout with 5.7 % side margins as in the reference (was capped at 1600 px), title column left,
  548 px card right; stacked on phones/tablets.
- Background: the clean campus photograph with a lighter wash — hazy top-left behind the title, clear centre, soft
  blue-white on the right, faint orange/blue corner tints; an opaque patch hides the small logo printed in the photo's corner.
- Logo: official logo without the white plate; `mix-blend-multiply` removes the PNG's white background on the sky.
- Title "KRA Tracker" at the reference scale (104 px at ≥1280 px) in navy and the reference orange, orange rule,
  letter-spaced "Key Result Area Portal" and "Track. Review. Lead.".
- Card: 28 px radius, reference padding and shadow; "Welcome Back" / "Sign in to KRA Tracker"; Dean/VC toggle (bright
  orange active segment, "VC" with screen-reader text "Vice Chancellor"); labelled 58 px fields with icons, password
  show/hide; 62 px "Sign In →" button; divider and "For KIET leadership access.".
- Behaviour: the Sign In button is no longer disabled while fields are empty — submitting names each missing field
  ("Enter your username." / "Enter your password."), marks it `aria-invalid` and focuses it. Server errors, loading state,
  autofill attributes, Enter submission and the wrong-role guard are unchanged.

Deviations: "Username" instead of "Institutional Email" (accounts sign in with usernames); no "Remember me" / "Forgot
password?" (no backend support); the photograph's own composition differs from the reference artwork (the reference moves
the buildings and tower), so the building's sign sits behind the subtitle under the wash; the reference's blurred
foreground foliage is not reproduced.

Validation (isolated stack, synthetic `demo.*` accounts):

| Check | Result |
|---|---|
| New test `test_login_pages_required_fields_keyboard_and_roles` (both role pages, required-field messages and focus, Enter submission, show/hide password, invalid password → alert and no session, valid keyboard sign-in, 375 px no overflow) | OK |
| Existing `test_portals_reject_wrong_role` (wrong-role login, cross-role URL) | OK |
| `npx tsc -b`, `npm run build` | OK |
| `python e2e/run_isolated.py` (full suite, incl. the overlap/selection-panel regression test above) | **Ran 31 tests, OK** |
| Login captures `/dean/login`, `/vc/login` at 1672×941 (reference), 1440×900, 768×1024, 375×812 | 0 px page overflow on all 8 |

Screenshots (git-ignored): `.work/ui-login/login-{dean,vc}-{1672,1440,768,375}.png`, plus
`login-dean-1440-required.png`, `-invalid.png`, `-focus.png` and `login-landing-1440.png`. Opened and compared with the
reference: Dean 1672, VC 1440, VC 768, Dean 375, Dean 1440 invalid-password state.

## Login refinement — complete image, no blur, compact card (2026-10-21)

- **Blur cause**: no CSS `filter`/`backdrop-filter` was involved. The photo was a JPEG re-encode of the 1672×941 PNG,
  scaled with `background-size: cover` (cropped, and upscaled past its native size on wide/high-DPI screens) under a
  full-photo white wash that read as haze. The supplied original itself is only 1672×941 and its fine detail (e.g. the
  recruiter board) is soft in the source; CSS cannot add detail that is not there.
- **Fix**: the original PNG (`frontend/src/assets/login-background.png`, replaces the JPEG) is an `<img>` in a box with
  the photo's own aspect ratio, never wider than 1672 px, on a solid `#E3EEF9` — complete, undistorted, never upscaled. The
  full-photo wash is gone; only two local overlays remain (an opaque patch over the logo printed in the photo's corner, and
  a light haze plus text halo behind the title). From 1280 px the title and card overlay the photo as in the reference;
  below that title, photo and card stack.
- **Compact card**: 548 → 440 px wide (−20 %), about 692 → 549 px tall (−21 %); padding, toggle (58 → 50 px), fields
  (58 → 50 px), button (62 → 54 px) and type reduced; no `transform`/`zoom`.

Measured in the browser (both `/dean/login` and `/vc/login`, normal and required-field states): photo box fully inside the
page at 1366×768 (1365×768), 1440×900 (1440×810), 1672×941 (1672×941), 768 (704×396) and 375 (343×193); rendered ratio
1.777 = 1672:941; 0 elements with a CSS filter; no horizontal overflow. Checks: `npx tsc -b`, `npm run build` OK; full
isolated browser suite **31 OK** (incl. login required-field/keyboard/role and wrong-role tests). Screenshots:
`.work/ui-login-v4/login-{dean,vc}-{1366,1440,1672,768,375}.png`, `login-vc-<width>-required.png`,
`login-dean-1366-invalid.png` (inspected: 1366 normal and invalid, 1440 required, 768, 375). Note: the PNG is 2.7 MB
(the original is used as instructed); a high-quality WebP/JPEG could cut this if load time matters.

## Login — full-page background restored (2026-10-21)

Owner feedback: with the contained photo the image looked small, with empty side bands on wide screens, and phones/tablets
showed no background. The original PNG now fills the whole page at every size (`object-cover`, anchored to the top so the
sky, buildings and tower stay in view); title and compact card sit over it on desktop and stack over it on phones/tablets.
Kept: original PNG (no JPEG), no CSS filter, local overlays only, 440 px card. Measured: the photo covers the full page
on `/dean/login`, `/vc/login` and `/` at 1535×728, 1366×768, 1440×900, 1920×1080, 1024×768, 768×1024 and 375×812
(also with field errors), 0 filters, no horizontal overflow. Browser suite 31 OK. Screenshots: `.work/ui-login-v5/`.
Trade-off: filling wide screens crops a little of the photo's top or bottom and scales it above 1672 px on large monitors.
