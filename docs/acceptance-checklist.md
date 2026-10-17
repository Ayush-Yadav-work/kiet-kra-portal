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
For each KRA, compare the form and the PDF with the source template/college expectations and record the result. **Status values:**
Accepted / Changes needed / Not reviewed. Adapted (21, 39, 43) and project-created formats need particular attention. Open college
decisions are marked **college** in `docs/decisions.md` (for example minimum evidence sets, which remain proposals until decided).
Nothing below is pre-filled: automated tests and the owner's pilot acceptance do not count as institutional acceptance.

| KRA | Activity (from the workbook) | Format | Institutionally accepted | Status | Reviewer | Date / notes |
|---|---|---|---|---|---|---|
| 1 | Number of new courses introduced | Supplied (course family) | [ ] | | | |
| 2 | Number of value-added courses where the students of the institution ha… | Supplied (course family) | [ ] | | | |
| 3 | Number of online courses of MOOCs, SWAYAM / e_Pathshala/ NPTE/ Global … | Supplied (course family) | [ ] | | | |
| 4 | Percentage of Students that have completed the field projects. | Supplied (field projects) | [ ] | | | |
| 5 | Percentage of Students that have completed research projects. | Supplied (field projects) | [ ] | | | |
| 6 | Percentage of students that have completed internships. | Supplied (field projects) | [ ] | | | |
| 7 | Number of Teachers give Structured feedback for curriculum | Supplied (survey) | [ ] | | | |
| 8 | Number of employers give structured feedback for curriculum. | Supplied (consolidated surveys) | [ ] | | | |
| 9 | Number of alumni give structured feedback for curriculum. | Supplied (consolidated surveys) | [ ] | | | |
| 10 | Number of academic experts (outside) give structured feedback for curr… | Supplied (consolidated surveys) | [ ] | | | |
| 11 | Bridge courses conducted | Supplied | [ ] | | | |
| 12 | Number of awards received for research/ innovations by Faculty/Student… | Supplied | [ ] | | | |
| 13 | No. of faculty to become members of industry advisory boards/Think tan… | Supplied | [ ] | | | |
| 14 | No of Yukthi Registration - Faculty with Students | Project-created | [ ] | | | |
| 15 | No of Entrepreneur (can be a Faculty/Alumni/ Student) | Supplied | [ ] | | | |
| 16 | No of innovation ambassadors | Project-created | [ ] | | | |
| 17 | Training centers / labs established in collaboration with Industries | Supplied | [ ] | | | |
| 18 | Signed Functional MoU with Industry/Res. Organization | Supplied | [ ] | | | |
| 19 | No. of industrial visits arranged for students | Supplied | [ ] | | | |
| 20 | No of faculty to be trained in industry for more than a week | Supplied | [ ] | | | |
| 21 | Competitive Training (GATE, NET, GMAT etc.,) conducted | Adapted | [ ] | | | |
| 22 | No. of Career counselling activities conducted | Supplied | [ ] | | | |
| 23 | Skill development & employability - training organized related to Entr… | Supplied | [ ] | | | |
| 24 | Students placement in % | Supplied | [ ] | | | |
| 25 | Number of students won awards/medals for outstanding performance in sp… | Supplied (award sheet) | [ ] | | | |
| 26 | Number of students won awards/medals for outstanding performance in cu… | Supplied (award sheet) | [ ] | | | |
| 27 | The institution conducts /organizes sports competitions/Events | Project-created (event family) | [ ] | | | |
| 28 | The institution conducts /organizes cultural competitions/ Events | Project-created (event family) | [ ] | | | |
| 29 | The institution conducts /organizes technical fests, Academic fests | Project-created (event family) | [ ] | | | |
| 30 | The institution conducts /organizes, any other events through active c… | Project-created (event family) | [ ] | | | |
| 31 | No of Hackathon or ideathon Organized (State Level/National Level) | Supplied | [ ] | | | |
| 32 | Total Amount of alumni contribution during the to the institution thro… | Supplied | [ ] | | | |
| 33 | Alumni chapter, Meet and Engagement in university activities/events or… | Supplied (pilot) | [ ] | | | |
| 34 | Number of teachers provided with financial support to attend conferenc… | Project-created | [ ] | | | |
| 35 | Number of teachers provided membership fee of professional bodies year… | Project-created | [ ] | | | |
| 36 | No of administrative training programs organized for staff and non-tea… | Supplied (FDP/STP family) | [ ] | | | |
| 37 | Faculty development programs organized on I&E, IPR etc. (min 30 hours) | Supplied (FDP/STP family) | [ ] | | | |
| 38 | Total number of teachers who have undergone online/ face-to-face Facul… | Supplied | [ ] | | | |
| 39 | Total Grants received from government and non-government bodies and ph… | Adapted | [ ] | | | |
| 40 | Institution has initiated Gender audit and measure for the promotion o… | Project-created | [ ] | | | |
| 41 | Number of activities organized by the university for providing an incl… | Project-created | [ ] | | | |
| 42 | Number of activities organized for Sensitization of students and emplo… | Project-created | [ ] | | | |
| 43 | Scopus ConferenceOrganized by the Department | Adapted | [ ] | | | |
| 44 | BOOT Camps & Peer Learning Activities | Supplied | [ ] | | | |
| 45 | National &International Flagship Event | Supplied | [ ] | | | |

**Owner acceptance of the KRA 33 pilot (separate from the above):** accepted by the project owner on 2026-10-17 for template
fidelity/usability of the pilot (recorded in `docs/progress.md`, Phase 2). KRA 33 still needs institutional review in the table above.

## 6. Scripted checks done vs human checks pending
Completed by automated/scripted checks (see `docs/validation.md`; not a substitute for the human checks):
- Permissions, deadlines, revisions, concurrency (Phase 6A); PDF/failure recovery and local load (Phase 6B); scripted accessibility
  audit, keyboard tabs, accessible names, required markers, inactive-field retention, 375 px header, measured contrast of shared
  controls (Phase 6C).

Pending — to be done by people (tick when done):
- [ ] Screen-reader pass (NVDA or JAWS on Windows, and/or VoiceOver) through sign-in, a report (tabs, a table row, an error), evidence upload and the VC review.
- [ ] Real browser zoom at 200% (Ctrl/Cmd + "+") on the Dean dashboard, a report workspace and the VC progress page: no lost content or controls; only wide tables scroll sideways.
- [ ] Phone check on a real device (about 375 px wide).
- [ ] Full end-to-end walkthrough (sections 1–4) with one VC and two Deans.
- [ ] Institutional review of all 45 formats (section 5).

## Sign-off
- [ ] Walkthrough completed — date: ______ participants: ______________________
- [ ] Open issues recorded (or "none")
- [ ] Project owner sign-off: ______________________
