# Source audit (Phase 0)

Date: 2026-10-16. Plan used: `KIET_KRA_Claude_Code_Implementation_Plan (2).md` v2.0 (copied to `docs/implementation-plan.md`).
Repository instructions: none (`README.md` is a one-line title; no `AGENTS.md`/`CLAUDE.md`).

## 1. What was supplied

- `reference/workbook/original-tracker.xlsx` — 14 sheets: `Instructions` + 13 department sheets
  (CSE, CSE (AI), CSE (AIML), IT, CS, CSIT, EEE, ECE, ME, KSOM, MCA, KSOP, ASH).
- `reference/workbook/converted-tracker.md` — Markdown conversion of the same workbook.
- `reference/templates/` — 30 PDFs (no DOCX/XLSX originals). Full list, checksums and mapping: `docs/template-inventory.md`.

All files were readable. Originals are untouched; derived material is in git-ignored `.work/`.

## 2. Workbook findings

| Topic | Finding | Handling |
|---|---|---|
| KRA definitions | `Instructions` rows 14–60 hold all 45 KRAs with NBA/NAAC refs and report-format names | Canonical activity text taken from `Instructions`, byte-for-byte (double spaces and NBSPs kept) |
| Activity text per sheet | 12 sheets match `Instructions` exactly; ASH has whitespace-normalised copies (KRA 1, 2, 3, 25, 26, 38, 39) | No semantic difference; `Instructions` wins (D-005) |
| Targets | 13 × 45 = 585 department targets, column E of each sheet | Extracted from XLSX (`scripts/extract_seed.py`) and cross-checked cell-by-cell against the Markdown: 0 mismatches |
| Target values | Mixed strings (`"50% student/Year"`, `"As per policy"`, `"Yes"`, `"NA"`, `"01 per year"`) and numbers stored as floats (`3.0`) with General format | Strings kept intact; integral floats shown as Excel General shows them (`3`). NA/Nil/Yes never reinterpreted (D-004) |
| Achievement columns | Many sheets already contain achievement text in the July–Aug 2026 column (e.g. "3 courses are ready") | **Not imported** (plan 2.2). Seed holds definitions/targets only |
| Formula columns | `Achievement %` formulas hard-code divisors that sometimes differ from column E (e.g. CSE KRA 9: target 40, formula `/44`; KRA 26: 10 vs 13; KRA 39: 1050119 vs 860050) | Irrelevant to release 1 (no automatic aggregation, plan 3.3); recorded here only |
| Extra sections | Rows below KRA 45: Research Publication / SCIE / Q1&Q2 / Scopus / Final-Year Project / M.Tech targets | Excluded (plan 2.2) |
| Department naming | Sheet tab `KSOM` but sheet title "MBA – KRA Achievement Tracker"; Markdown uses "MBA" | One department, code `KSOM`; full name proposed, **needs college confirmation** (D-003) |
| Department full names | Workbook gives codes only | Proposed expansions in seed, flagged for confirmation (D-003) |
| NAAC refs | KRA 25/26 show `5.3 1` (likely `5.3.1`); KRA 43–45 have none | Kept verbatim; flagged, not corrected |
| Sheet layout | `CSE (AI)` header is on row 5 instead of row 4 | Extraction keys on "KRA n:" text, not row positions |
| Report-format references | `Instructions` names DOCX/XLSX originals; KRA 40 row points at `KRA 43 - Templates.xlsx` | Only PDFs supplied; KRA 40 treated as missing format (plan 5.2) |
| Summary templates | `KRA 1-3 Template.xlsx`, `KRA 12 Data Template…xlsx`, `KRA 19 Summary…2026-27.xlsx` referenced, not supplied | Not needed for pilot; listed as missing |
| Survey instruction | Instruction 8: Action Taken / Impact Analysis / Discussion in BoS for feedback KRAs | Summary sections for KRAs 7–10 (Phase 4) |

## 3. Template coverage vs plan 5.2

- Supplied and usable (with documented fixes): 1–3, 7, 8, 9 (9a/9b), 10, 11, 12, 13, 18, 19 (19a + 19b), 22, 23, 25–26, 31, 32, 33, 36–37, 44, 45.
- Supplied but adapted: 4–6 (split per KRA), 15 (+faculty ID), 17, 20, 24, 27–30 (event-organising variants), 38.
- Mismatched supplied templates, must be adapted, never reused unchanged: **21** (GATE qualifiers vs training conducted),
  **39** (research funding vs infrastructure grants), **43** (journal papers vs Scopus conference organised).
- Wholly missing, project-created: **14, 16, 34, 35, 40, 41, 42** (minimum content per plan 5.3).
- Broken source exports (logo/table split across pages): 15, 17, 20, 22, 31, 32, 38. Unnecessary blank/overflow pages: 9a p3, 9b p3, 10 p3, 33 p4.
- Ambiguous labels: KRA 19a PO/PSO matrix has `PSO1` twice (D-012). Copied "VAC/Add-on Course" wording in 11 and 23 supporting-document lists.
- Example content that must never become production data: years 2023-24…2026-27 in XLSX templates, event IDs `HCK-25-01`, `IDE-25-01`,
  `HCK-24-01`, sample rows ("Career Counselling Session", "B.Tech CSE"), pre-filled "Available"/"Active" statuses.

Every KRA therefore has either a source or an explicit design basis (plan 5.3). Phase 0 exit criteria are met, subject to
the open items below.

## 4. Open items needing the college (do not block local development)

1. Canonical department full names, especially KSOM vs MBA (D-003).
2. KRA 33 minimum evidence set (proposed in D-013) and Nil/evidence policy review during the pilot.
3. KRA 19b individual-response handling (plan 5.4 assumption) — Phase 4.
4. KRA 9 four-year boundary classification — Phase 4 help text.
5. Server specifications, storage limits (20/100/500 MB defaults), backup destination — Phase 7.
