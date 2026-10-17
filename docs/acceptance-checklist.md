# Team acceptance checklist (Phase 6E walkthrough)

For the project owner and college team. **All boxes are left for the team to tick**; automated tests do not count as acceptance.
Use synthetic or test accounts on a non-production copy: one VC and the Deans of two departments (below "Dean A" and "Dean B").
Record the date, the people present, and any issue (with KRA, page and steps) at the end.

## 1. Access and separation
- [ ] VC signs in only at `/vc/login`; Deans only at `/dean/login` (wrong portal refuses the credentials).
- [ ] Dean A sees only Dean A's department (dashboard, reports, evidence); Dean B likewise.
- [ ] Dean pages cannot open VC pages (assignments, KRAs, progress, review).

## 2. Submission, rejection, resubmission, approval (one KRA per Dean)
- [ ] Dean A opens a KRA for the open period, fills the Report tab (add/remove a repeatable row or event), sees autosave ("Saved") and the live preview.
- [ ] Dean A adds evidence (a file and a Drive link) and the Achievement text; *Submit* lists anything missing; submits successfully.
- [ ] VC finds the report on the progress page (filters), opens *Review*, rejects with a reason.
- [ ] Dean A sees the reason, corrects, resubmits; VC approves; the exported PDF shows "Verified by VC – …".
- [ ] VC *Return for correction* keeps the approved revision in History.
- [ ] Dean B submits a **Nil** report for another KRA (reason required, no evidence) and the VC approves it.
- [ ] Reopening: Dean B requests reopening of a closed period; VC approves; the 72-hour banner appears; editing closes when it expires.
- [ ] VC exports the progress PDF and a report PDF; both open and match the screen.

## 3. Assignments (VC)
- [ ] Copy a year into next-year drafts, edit a target, finalize; finalized targets cannot be changed.
- [ ] In the current year a **new** department/KRA pair can be added and finalized; existing targets stay unchanged.

## 4. Usability spot checks
- [ ] Keyboard only: sign in, open a report, switch tabs (arrow keys), fill a field, save, submit.
- [ ] Phone width (or 200% browser zoom): dashboard and report workspace usable without sideways page scrolling (wide tables scroll inside their box).
- [ ] Error messages are understandable (try submitting an incomplete report and uploading an unsupported file).

## 5. Review of all 45 report formats (institutional acceptance)
For each KRA, compare the form and the PDF with the source template/college expectations, and record **Accepted** or the change needed.
Adapted (21, 39, 43) and project-created (14, 16, 27–30, 34, 35, 40–42) formats need particular attention. Open college decisions
are marked **college** in `docs/decisions.md` (for example minimum evidence sets, which are proposals until decided).

| KRAs | Accepted | Notes / changes needed |
|---|---|---|
| 1, 2, 3 | [ ] | |
| 4, 5, 6 | [ ] | |
| 7 | [ ] | |
| 8, 9, 10 | [ ] | |
| 11 | [ ] | |
| 12 | [ ] | |
| 13 | [ ] | |
| 14 | [ ] | |
| 15 | [ ] | |
| 16 | [ ] | |
| 17 | [ ] | |
| 18 | [ ] | |
| 19 | [ ] | |
| 20 | [ ] | |
| 21 | [ ] | |
| 22 | [ ] | |
| 23 | [ ] | |
| 24 | [ ] | |
| 25, 26 | [ ] | |
| 27, 28, 29, 30 | [ ] | |
| 31 | [ ] | |
| 32 | [ ] | |
| 33 (pilot; owner-accepted 2026-10-17, institutional review still needed) | [ ] | |
| 34, 35 | [ ] | |
| 36, 37 | [ ] | |
| 38 | [ ] | |
| 39 | [ ] | |
| 40, 41, 42 | [ ] | |
| 43 | [ ] | |
| 44 | [ ] | |
| 45 | [ ] | |

## Sign-off
- [ ] Walkthrough completed — date: ______ participants: ______________________
- [ ] Open issues recorded (or "none")
- [ ] Project owner sign-off: ______________________
