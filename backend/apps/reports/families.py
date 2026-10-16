"""Template families: one reviewed definition rendered by one template, configured per KRA.

The course-report family covers KRAs 1, 2 and 3, which share the supplied "KRA 1-3 Report Format" (D-036).
Each KRA still gets its own TemplateVersion (key/version), assignment and submissions; the built schema is
stored on the TemplateVersion, so later edits here never change a version already in use (plan 7).
"""
import copy

SOURCE_1_3 = "reference/templates/KRA 1-3 Report Format.docx (2).pdf"
CHECKSUM_1_3 = "d04a5f0a26c3750cbc7a544661a7cb872a8721652177becfde3764a77ea09284"

OBJECTIVES = ["To supplement the knowledge acquired through the regular curriculum.",
              "To provide exposure to emerging technologies and industry practices.",
              "To develop employability and professional skills.",
              "To promote interdisciplinary and experiential learning."]
IMPACT = ["Improvement in technical/professional skills", "Improvement in employability skills", "Industry certification obtained",
          "Successful completion/certification rate", "Internship opportunities", "Placement support/outcomes",
          "Student projects developed", "Participation in competitions/hackathons"]
DOCS = ["Approval/permission for conducting the course", "Course proposal/concept note", "Course syllabus/content",
        "Academic calendar/activity schedule", "Course timetable", "Resource person/faculty details",
        "Expert profile/CV, wherever applicable", "Attendance records", "Registration/enrolment records",
        "Assessment records", "Result/score sheet", "Student feedback", "Sample certificates",
        "Photographs with date and caption", "Geo-tagged photographs, wherever applicable", "Course completion report",
        "List of students who completed the course", "Any other relevant supporting document"]
EVIDENCE = ["Approval/permission for conducting the course", "Course proposal/concept note", "Course syllabus/content",
            "Academic calendar/activity schedule", "Course timetable", "Resource person/faculty details", "Expert profile/CV",
            "Attendance records", "Registration/enrolment records", "Assessment records", "Result/score sheet",
            "Student feedback", "Sample certificates", "Photographs with date and caption", "Geo-tagged photographs",
            "Course completion report", "List of students who completed the course", "Other"]

# Per-KRA configuration. `term` replaces "Value Added Courses" in the source's section headings only where the
# KRA is not about value-added courses (KRA 2 keeps the source wording verbatim).
VARIANTS = {
    1: {"key": "kra1", "term": "New Courses", "doc_unit": "New Course",
        "meaning": "KRA 1 — new courses introduced. Enrolment/completion are optional: a course may be introduced before it is first offered.",
        "extra_before": [
            {"id": "course_code", "label": "Course Code", "type": "text", "required": True, "max_length": 40},
        ],
        "extra_after": [
            {"id": "approval_ref", "label": "Approval reference (BoS/Academic Council, optional)", "type": "text", "required": False, "max_length": 200},
        ],
        "students_required": False},
    2: {"key": "kra2", "term": "Value Added Courses", "doc_unit": "VAC/Add-on Course",
        "meaning": "KRA 2 — value-added courses in which students enrolled and successfully completed.",
        "extra_before": [], "extra_after": [], "students_required": True},
    3: {"key": "kra3", "term": "Online Courses (MOOCs)", "doc_unit": "Online Course (MOOC)",
        "meaning": "KRA 3 — online courses of MOOCs, SWAYAM / e_Pathshala / NPTE / Global Certification.",
        "extra_before": [],
        "extra_after": [
            {"id": "platform", "label": "Platform / Certifying Body", "type": "text", "required": True, "max_length": 150,
             "suggestions": ["SWAYAM", "e_Pathshala", "NPTE", "Global Certification"],
             "help": "As named by the course provider; suggestions repeat the workbook wording only."},
        ],
        "students_required": True},
}


def course_family_schema(kra):
    v = VARIANTS[kra]
    stu = v["students_required"]
    details = (
        [{"id": "course_name", "label": "Course Name", "type": "text", "required": True, "max_length": 200, "col": "Course Name"}]
        + [dict(f, col=f["label"].split(" (")[0]) for f in v["extra_before"]]
        + [{"id": "duration_hours", "label": "Duration (Hours)", "type": "decimal", "required": True, "min": 0.5, "max": 1000,
            "decimal_places": 1, "col": "Duration (Hours)"},
           {"id": "mode", "label": "Mode", "type": "select", "required": True, "options": ["Offline", "Online", "Hybrid"],
            "col": "Mode Offline/ Online/ Hybrid"},
           {"id": "resource_agency", "label": "Resource Person/ Agency", "type": "text", "required": True, "max_length": 200,
            "col": "Resource Person/ Agency"}]
        + [dict(f, col=f["label"].split(" (")[0]) for f in v["extra_after"] if f["id"] == "platform"]
        + [{"id": "students_enrolled", "label": "No. of Students Enrolled", "type": "integer", "required": stu, "min": 0,
            "max": 100000, "col": "No. of Students Enrolled"},
           {"id": "students_completed", "label": "No. of Students Completed", "type": "integer", "required": stu, "min": 0,
            "max": 100000, "col": "No. of Students Completed"}]
    )
    extra_fields = [f for f in v["extra_after"] if f["id"] != "platform"]
    term = v["term"]
    schema = {
        "key": v["key"], "version": 1,
        "title": f"REPORT ON VALUE ADDED COURSES, ADD-ON COURSES AND MOOCs — {term}",
        "family": {"name": "course_1_3", "kra": kra, "term": term, "doc_unit": v["doc_unit"], "meaning": v["meaning"],
                   "detail_columns": [{"id": f["id"], "label": f["col"]} for f in details]},
        "renderer": "reports/course_family_v1.html",
        "source": SOURCE_1_3, "source_checksum": CHECKSUM_1_3,
        "page": {"format": "Letter", "landscape": False, "style": "report"},
        "activity": {"label": "Course", "min": 1, "max": 20},
        "rules": [{"type": "lte", "a": "students_completed", "b": "students_enrolled",
                   "message": "Students completed cannot exceed students enrolled."}],
        "sections": [
            {"id": "header", "title": "Course header",
             "intro": f"{v['meaning']} Department and academic year are filled from this report; the Introduction paragraph is printed as in the source.",
             "fields": [
                 {"id": "year_semester", "label": "Academic Session / Year/ Semester (year of study and semester)", "type": "text",
                  "required": True, "max_length": 80, "placeholder": "e.g. 2nd Year / Even Semester"},
                 {"id": "faculty_coordinators", "label": "Faculty Coordinator(s)", "type": "text", "required": True, "max_length": 300},
                 {"id": "hod", "label": "Head of the Department", "type": "text", "required": True, "max_length": 150}]},
            {"id": "objectives", "title": f"Objectives of {term}",
             "intro": "Tick the source objectives that applied to this course and add any others; only ticked/added objectives are printed.",
             "fields": [
                 {"id": "objectives", "label": "Objectives (from the source template)", "type": "multiselect", "required": False,
                  "options": OBJECTIVES},
                 {"id": "other_objectives", "label": "Other objectives (optional, one per line)", "type": "longtext",
                  "required": False, "max_length": 2000}]},
            {"id": "course", "title": f"Detail of {term}",
             "fields": [{k: val for k, val in f.items() if k != "col"} for f in details] + extra_fields},
            {"id": "syllabus", "title": "Course Content/Syllabus",
             "fields": [{"id": "modules", "label": "Modules", "type": "table", "required": True, "min_rows": 1, "max_rows": 100,
                         "columns": [
                             {"id": "topic", "label": "Topic", "type": "text", "required": True, "max_length": 300, "width": "62%"},
                             {"id": "hours", "label": "No. of Hours", "type": "decimal", "required": True, "min": 0.5, "max": 500,
                              "decimal_places": 1, "width": "26%"}]}]},
            {"id": "outcomes", "title": "Learning Outcomes",
             "fields": [{"id": "learning_outcomes", "label": "After successful completion of the course, students will be able to: (one per line)",
                         "type": "longtext", "required": True, "max_length": 4000}]},
            {"id": "assessment", "title": "Assessment and Certification",
             "fields": [
                 {"id": "assessment_method", "label": "Assessment Method", "type": "text", "required": True, "max_length": 300},
                 {"id": "min_attendance", "label": "Minimum Attendance Requirement", "type": "text", "required": True, "max_length": 120},
                 {"id": "passing_criteria", "label": "Passing/Completion Criteria", "type": "text", "required": True, "max_length": 300},
                 {"id": "certificate_authority", "label": "Certificate Issuing Authority", "type": "text", "required": True, "max_length": 200},
                 {"id": "certificates_issued", "label": "Number of Certificates Issued", "type": "integer", "required": True, "min": 0, "max": 100000}]},
            {"id": "impact", "title": "OUTCOME AND IMPACT",
             "fields": [
                 {"id": "impact_indicators", "label": "Suggested Impact Indicators — tick those actually observed", "type": "multiselect",
                  "required": False, "options": IMPACT},
                 {"id": "impact_details", "label": "Impact details (optional)", "type": "longtext", "required": False, "max_length": 3000},
                 {"id": "feedback_score", "label": "Student Feedback Summary: Overall Feedback Score (out of 5)", "type": "decimal",
                  "required": False, "min": 0, "max": 5, "decimal_places": 2,
                  "help": "Leave blank if no feedback score was collected; the report then shows the blank line from the source."},
                 {"id": "suggestions", "label": "Major Suggestions Received (one per line)", "type": "longtext", "required": False, "max_length": 3000}]},
            {"id": "signoff", "title": "Prepared By / Approved By",
             "intro": "Signature lines stay blank for wet signatures; the portal adds only the textual VC verification.",
             "fields": [
                 {"id": "prepared_name", "label": "Prepared By — Name", "type": "text", "required": False, "max_length": 150},
                 {"id": "prepared_designation", "label": "Prepared By — Designation", "type": "text", "required": False, "max_length": 150},
                 {"id": "prepared_date", "label": "Prepared By — Date", "type": "date", "required": False},
                 {"id": "approved_name", "label": "Approved By — Name", "type": "text", "required": False, "max_length": 150},
                 {"id": "approved_designation", "label": "Approved By — Designation", "type": "text", "required": False, "max_length": 150},
                 {"id": "approved_date", "label": "Approved By — Date", "type": "date", "required": False}]},
            {"id": "documents", "title": "List of Supporting Documents",
             "intro": f"The following documents shall be maintained for each {v['doc_unit']}. Mark whether each is maintained; upload files in the Evidence tab.",
             "fields": [{"id": "supporting_documents", "label": "Supporting documents maintained", "type": "checklist",
                         "required": False, "items": DOCS}]},
        ],
        "evidence": {"categories": EVIDENCE, "required": [],
                     "note": "No minimum evidence set has been agreed for KRAs 1–3 (docs/decisions.md D-036); categories follow the source list."},
    }
    return copy.deepcopy(schema)


# ---------------------------------------------------------------------------------------------------------------
# FDP/STP family: KRAs 36 and 37 share "KRA 36-37 Report on FDP and STP" (D-037). Workbook definitions win over the
# template's faculty wording: KRA 36 (staff/non-teaching administrative training) uses STP/staff labels and gets no
# faculty-specific objective/outcome claims; KRA 37 (FDP on I&E, IPR etc.) keeps the source FDP wording and the
# workbook's minimum 30 hours, enforced at submission only (drafts and Nil are unaffected).
SOURCE_36_37 = "reference/templates/KRA 36-37 Report on FDP and STP.docx.pdf"
CHECKSUM_36_37 = "1949715561474523500cc2697fd1ee66f00793f3a87eafe7496b0496db7597a2"
FDP_OBJECTIVES = ["To enhance teaching, learning and assessment competencies.",
                  "To familiarize faculty members with emerging technologies and current developments in their respective domains.",
                  "To promote innovative and learner-centric teaching methodologies.",
                  "To strengthen research, innovation and consultancy capabilities.",
                  "To enhance digital and technology-enabled teaching skills.",
                  "To promote Outcome Based Education (OBE) and effective assessment practices.",
                  "To encourage interdisciplinary learning and professional development.",
                  "To facilitate knowledge sharing and interaction with academic and industry experts."]
FDP_OUTCOMES = ["Apply innovative and effective teaching-learning methodologies.", "Enhance their subject/domain knowledge.",
                "Use relevant digital tools and technologies in teaching and learning.", "Improve assessment and evaluation practices.",
                "Integrate practical and experiential learning approaches.", "Develop research and innovation capabilities.",
                "Apply the knowledge gained in academic and institutional activities."]
FORMATS = ["Expert lectures", "Interactive technical sessions", "Demonstrations and hands-on activities", "Case studies",
           "Group discussions", "Practical exercises", "Experience sharing", "Question-and-answer sessions"]
FDP_DOCS = ["FDP brochure/notice", "Programme schedule", "Resource person profile", "Attendance sheet", "Photographs/screenshots",
            "Participant feedback", "Assessment/quiz records", "Certificates", "Presentation/training material",
            "Programme completion report"]

FDP_VARIANTS = {
    36: {"key": "kra36", "abbr": "STP", "people": "Staff", "person": "Staff Member",
         "meaning": "KRA 36 — administrative training programmes organized for staff and non-teaching staff.",
         "objectives": [], "outcomes": [], "min_hours": None, "focus": False,
         "target_placeholder": "e.g. Administrative and non-teaching staff",
         "docs": ["STP brochure/notice"] + FDP_DOCS[1:]},
    37: {"key": "kra37", "abbr": "FDP", "people": "Faculty", "person": "Faculty",
         "meaning": "KRA 37 — faculty development programmes organized on I&E, IPR etc. (minimum 30 hours).",
         "objectives": FDP_OBJECTIVES, "outcomes": FDP_OUTCOMES, "min_hours": 30, "focus": True,
         "target_placeholder": "e.g. Faculty members of engineering departments", "docs": FDP_DOCS},
}


def _ticks(fid, label, options):
    """Source statements become tick boxes, never pre-asserted claims; absent when the KRA has no source list."""
    return [{"id": fid, "label": label, "type": "multiselect", "required": True, "options": options}] if options else []


def fdp_stp_schema(kra):
    v = FDP_VARIANTS[kra]
    abbr, has_lists = v["abbr"], bool(v["objectives"])
    hours = {"id": "duration_hours", "label": "Duration (hours)", "type": "decimal", "required": True, "decimal_places": 1,
             "min": v["min_hours"] or 0.5, "max": 1000,
             "help": "Total contact hours." + (" KRA 37 counts programmes of at least 30 hours; checked when you submit."
                                               if v["min_hours"] else "")}
    if v["min_hours"]:
        hours["range_message"] = f"KRA 37 requires a programme of at least {v['min_hours']} hours (workbook: min 30 hours)."
    particulars = [
        {"id": "programme_title", "label": f"Title of the {abbr}", "type": "text", "required": True, "max_length": 250},
        hours,
        {"id": "dates", "label": "Dates / schedule (optional)", "type": "text", "required": False, "max_length": 120,
         "placeholder": "e.g. 12–16 October 2026"},
        {"id": "organized_by", "label": "Organized by", "type": "text", "required": True, "max_length": 200},
        {"id": "mode", "label": "Mode", "type": "select", "required": True, "options": ["Offline", "Online", "Hybrid"]},
        {"id": "target_group", "label": "Target Group", "type": "text", "required": True, "max_length": 200,
         "placeholder": v["target_placeholder"]},
        {"id": "participants_count", "label": "No. of Participants", "type": "integer", "required": True, "min": 0, "max": 100000},
        {"id": "coordinator", "label": "Programme Coordinator", "type": "text", "required": True, "max_length": 200},
        {"id": "resource_persons", "label": "Resource Person(s)", "type": "longtext", "required": True, "max_length": 1500},
    ]
    if v["focus"]:
        particulars.insert(1, {"id": "focus_areas", "label": "Focus area (workbook: I&E, IPR etc.)", "type": "multiselect",
                               "required": True, "help": "Tick all that apply; describe any other area in the title or introduction.",
                               "options": ["Innovation & Entrepreneurship (I&E)", "Intellectual Property Rights (IPR)",
                                           "Other related area"]})
    other = lambda fid, noun, max_length: {
        "id": fid, "label": f"Other {noun} (optional, one per line)" if has_lists else f"{noun.capitalize()} (one per line)",
        "type": "longtext", "required": not has_lists, "max_length": max_length}
    schema = {
        "key": v["key"], "version": 1,
        "title": f"REPORT ON FACULTY DEVELOPMENT PROGRAMME (FDP)/ REPORT ON STAFF TRAINING PROGRAMME (STP) — {abbr}",
        "family": {"name": "fdp_stp", "kra": kra, "abbr": abbr, "people": v["people"], "person": v["person"],
                   "meaning": v["meaning"], "focus": v["focus"]},
        "renderer": "reports/fdp_stp_v1.html",
        "source": SOURCE_36_37, "source_checksum": CHECKSUM_36_37,
        "page": {"format": "Letter", "landscape": False, "style": "report"},
        "activity": {"label": "Programme", "min": 1, "max": 20},
        "sections": [
            {"id": "particulars", "title": f"{abbr} particulars", "intro": v["meaning"], "fields": particulars},
            {"id": "introduction", "title": "Introduction",
             "fields": [{"id": "introduction", "label": "Introduction", "type": "longtext", "required": True, "max_length": 4000}]},
            {"id": "objectives", "title": "Objectives",
             "intro": f'Printed as "The {abbr} was organized with the following objectives:".'
                      + (" Tick the source objectives that applied and add any others." if has_lists else ""),
             "fields": _ticks("objectives", "Objectives (from the source template)", v["objectives"])
                       + [other("other_objectives", "objectives", 2000)]},
            {"id": "participation", "title": f"{v['people']} Participation",
             "fields": [{"id": "participants", "label": f"{v['people']} participants", "type": "table", "required": True,
                         "min_rows": 1, "max_rows": 100, "editor": "cards",
                         "columns": [
                             {"id": "name", "label": f"Name of {v['person']}", "type": "text", "required": True, "max_length": 150, "width": "24%"},
                             {"id": "department", "label": "Department", "type": "text", "required": True, "max_length": 150, "width": "17%"},
                             {"id": "designation", "label": "Designation", "type": "text", "required": True, "max_length": 120, "width": "16%"},
                             {"id": "attendance", "label": "Attendance/Participation", "type": "text", "required": True,
                              "max_length": 120, "width": "19%", "placeholder": "e.g. Full (5/5 days)"},
                             {"id": "certificate", "label": "Certificate", "type": "text", "required": False, "max_length": 120,
                              "width": "16%", "placeholder": "e.g. Issued, No. TST-01",
                              "help": "Leave blank if no certificate was issued."}]}]},
            {"id": "syllabus", "title": f"{abbr} Content/Syllabus",
             "fields": [{"id": "modules", "label": "Modules", "type": "table", "required": True, "min_rows": 1, "max_rows": 100,
                         "columns": [
                             {"id": "topic", "label": "Topic", "type": "text", "required": True, "max_length": 300, "width": "62%"},
                             {"id": "hours", "label": "No. of Hours", "type": "decimal", "required": True, "min": 0.5, "max": 500,
                              "decimal_places": 1, "width": "26%"}]}]},
            {"id": "outcomes", "title": "Learning Outcomes",
             "intro": f'Printed as "After completion of the {abbr}, participants were able to:". Record only what participants achieved.',
             "fields": _ticks("outcomes", "Outcomes (from the source template)", v["outcomes"])
                       + [other("other_outcomes", "learning outcomes", 3000)]},
            {"id": "assessment", "title": "Assessment and Certification",
             "fields": [
                 {"id": "assessment_method", "label": "Assessment Method", "type": "text", "required": True, "max_length": 300},
                 {"id": "min_attendance", "label": "Minimum Attendance Requirement", "type": "text", "required": True, "max_length": 120},
                 {"id": "passing_criteria", "label": "Passing/Completion Criteria", "type": "text", "required": True, "max_length": 300},
                 {"id": "certificate_authority", "label": "Certificate Issuing Authority", "type": "text", "required": True, "max_length": 200},
                 {"id": "certificates_issued", "label": "Number of Certificates Issued", "type": "integer", "required": True,
                  "min": 0, "max": 100000}]},
            {"id": "impact", "title": "OUTCOME AND IMPACT",
             "intro": 'Printed as "The programme included:" — tick only the session formats that actually took place.',
             "fields": [
                 {"id": "formats", "label": "The programme included", "type": "multiselect", "required": True, "options": FORMATS},
                 {"id": "impact_details", "label": "Outcome and impact details (optional)", "type": "longtext", "required": False,
                  "max_length": 3000}]},
            {"id": "signoff", "title": "Prepared By / Approved By",
             "intro": "Signature lines stay blank for wet signatures; the portal adds only the textual VC verification.",
             "fields": [
                 {"id": "prepared_name", "label": "Prepared By — Name", "type": "text", "required": False, "max_length": 150},
                 {"id": "prepared_designation", "label": "Prepared By — Designation", "type": "text", "required": False, "max_length": 150},
                 {"id": "prepared_date", "label": "Prepared By — Date", "type": "date", "required": False},
                 {"id": "approved_name", "label": "Approved By — Name", "type": "text", "required": False, "max_length": 150},
                 {"id": "approved_designation", "label": "Approved By — Designation", "type": "text", "required": False, "max_length": 150},
                 {"id": "approved_date", "label": "Approved By — Date", "type": "date", "required": False}]},
            {"id": "documents", "title": "Documentary Evidence",
             "intro": "The following documents may be maintained as evidence. Mark whether each is maintained; upload files in the Evidence tab.",
             "fields": [{"id": "supporting_documents", "label": "Documents maintained", "type": "checklist", "required": False,
                         "items": v["docs"]}]},
        ],
        "evidence": {"categories": v["docs"] + ["Other"], "required": [],
                     "note": "No minimum evidence set has been agreed for KRAs 36–37 (docs/decisions.md D-037); categories follow the source list."},
    }
    return copy.deepcopy(schema)


# ---------------------------------------------------------------------------------------------------------------
# Consolidated survey family: KRA 8 (employer/industry), KRA 9 (alumni 9a/9b) and KRA 10 (academic expert) (D-038).
# The Dean enters college-prepared averages (plan 5.4); decimals are handled exactly as for KRA 7 (strings, never
# rounded, precision/range checked at submission). Question texts are the sources' own, in source order.
# Personal respondent fields are shown as consolidated or "Not applicable" — never invented.
CURRICULUM_QUESTIONS = [
    "The curriculum is relevant to current industry requirements.",
    "The curriculum adequately covers emerging technologies and industry trends.",
    "The curriculum provides adequate opportunities for developing technical/professional skills.",
    "The curriculum promotes problem-solving and analytical thinking abilities.",
    "The curriculum effectively develops communication and interpersonal skills.",
    "The curriculum provides adequate practical, laboratory, and experiential learning.",
    "The curriculum adequately integrates industry-oriented projects, internships, and real-world applications.",
    "The curriculum incorporates multidisciplinary/interdisciplinary learning.",
    "The curriculum adequately addresses employability and workplace readiness.",
    "The curriculum encourages innovation, creativity, entrepreneurship, and professional competence.",
    "The knowledge and skills acquired through the curriculum meet the expectations of employers.",
    "Overall, the curriculum is effective in preparing students for professional careers.",
]
ALUMNI_9A_QUESTIONS = [
    "The extent to which the curriculum is meeting the industrial/professional needs",
    "How do you rate your acquired knowledge is useful in your domain and is interrelated with the other domains",
    "How good are the opportunities you got to pursue research renowned national/international institutes (like IITs/NITs/etc.)",
    "Rate your ability in designing a product or give services with the acquired knowledge during your course",
    "To what extent you are updated with the evolving trends, tools and technology in your area of specialization",
    "Your involvement and participation in the outreach activities for serving the needy and society at large",
    "How far you could explore the entrepreneurship opportunities in the area of your specialization",
    "How far your experience in different teams during study in the institute is useful in the current profession.",
    "How do you rate the acquired managerial and communication skills help your professional growth",
    "Willingness to contribute towards development of the Institute",
]
ALUMNI_9B_QUESTIONS = [
    "Curriculum and syllabus content were appropriate for placement, competitive exams and higher education.",
    "Curriculum accommodates courses with experiential learning.",
    "Encouragement for usage of current technology and modern tools during degree course in the department.",
    "Infrastructure facilities namely library, labs, other campus facilities and overall teaching learning ambience.",
    "All the academic processes of the institute are transparent.",
    "Training and Placement cell provides ample campus placement opportunities.",
    "Role of Internship/training/skill development opportunities provided at the institute towards placement and professional growth.",
    "Impact of academic and other professional activities in developing leadership, teamwork and managerial skills.",
    "Institute offers sufficient scholarships to meritorious and deserving students.",
    "Your willingness to contribute towards development of the Institute",
]
SCALE = {"scale": [1, 2, 3, 4, 5], "decimal_places": 2,
         "scale_labels": ["Poor (1)", "Satisfactory (2)", "Good (3)", "Very Good (4)", "Excellent (5)"]}
RELATIONSHIPS_8 = ["Employer of Graduates", "Industry Partner", "Recruiter", "Industry Expert", "Alumni Employer", "Other"]
ALUMNI_STATUS = ["Higher Education", "Govt. Sector", "Pvt. sector", "Independent", "Self venture", "Other"]
ALUMNI_SUGGESTIONS = ("Suggestions if Any: Please make any additional comments or suggestions, which you think would help "
                      "strengthen our programs for the preparation of graduates. Any course to be added in the new curriculum. "
                      "Suggest any software tool to be added which is related to Industry sector.")
VARIANT_9A = "9a — Alumni with more than 4 years professional experience"
VARIANT_9B = "9b — Alumni with less than 4 years professional experience"
SURVEY_SOURCES = {
    8: ("reference/templates/KRA 8 Curriculum Feedback (Employer and Industry).docx.pdf",
        "ff05f8bd702726eafa2417857d3e702216b84ae85548139af49bc6c54bd62228"),
    9: ("reference/templates/KRA 9a - Alumni Feedback Survey Form (more than 4 Years).docx.pdf; "
        "reference/templates/KRA 9b - Alumni Feedback Survey Form(Less than 4 Years).docx.pdf",
        "108e4dad2398720470993dab9e6983c86884937582d43d227c3c666cbf4809e2"),  # 9a; both listed in source_checksums
    10: ("reference/templates/KRA 10 Curriculum Feedback (Academic Expert).docx.pdf",
         "2725a5c0aa310e5c90dab7a27d44ccc3471ce7b7815372f37dc2dc8b383ac2ed"),
}
SURVEY_EVIDENCE = ["Consolidated Feedback Analysis", "Collected Feedback Forms/Responses", "Action Taken Report",
                   "Impact Analysis", "BoS Minutes", "Other"]


def _counts(prefix, who, when=None):
    out = [{"id": f"{prefix}surveyed", "label": f"Number of {who} surveyed", "type": "integer", "required": True,
            "min": 0, "max": 100000},
           {"id": f"{prefix}respondents", "label": f"Number of {who} who responded", "type": "integer", "required": True,
            "min": 0, "max": 100000, "help": "Entered as counted; the portal does not calculate percentages."}]
    if when:
        for f in out:
            f["when"] = when
    return out


def _analysis_sections():
    return [
        {"id": "analysis", "title": "Feedback analysis (workbook instruction 8)",
         "intro": 'Record what has actually happened. If an item is not yet done, write "Pending" (with the expected date) or "Not applicable" and why.',
         "fields": [
             {"id": "action_taken", "label": "a) Action Taken", "type": "longtext", "required": True, "max_length": 6000,
              "guidance": "Workbook: mention the actions/initiatives taken based on the survey feedback."},
             {"id": "impact_analysis", "label": "b) Impact Analysis", "type": "longtext", "required": True, "max_length": 6000,
              "guidance": "Workbook: analyse the impact/effectiveness of the actions taken based on the survey feedback."},
             {"id": "bos_discussion", "label": "c) Discussion in BoS", "type": "longtext", "required": True, "max_length": 6000,
              "guidance": "Workbook: key points discussed/reviewed in the Board of Studies (BoS) and the recommendations/decisions taken."}]},
        {"id": "signoff", "title": "Sign-off",
         "fields": [{"id": "report_date", "label": "Date", "type": "date", "required": False}]},
    ]


def survey_schema(kra):
    common = [{"id": "collection_period", "label": "Feedback collection period", "type": "text", "required": True,
               "max_length": 120, "placeholder": "e.g. 1–15 October 2026"},
              {"id": "consolidated_by", "label": "Consolidated by (name & designation)", "type": "text", "required": True,
               "max_length": 150}]
    if kra in (8, 10):
        rel = (["Academic Expert"] if kra == 10 else []) + RELATIONSHIPS_8
        who = "employers/industry respondents" if kra == 8 else "academic experts"
        sections = [
            {"id": "details", "title": "Details Required (consolidated)",
             "intro": "One consolidated report of college-prepared results, not an individual response. Respondent name and "
                      "email/contact are shown as consolidated / not applicable.",
             "fields": common + _counts("", who) + [
                 {"id": "organizations", "label": "Name of Organization(s) represented", "type": "longtext", "required": True, "max_length": 3000},
                 {"id": "designations", "label": "Respondent designations (summary, optional)", "type": "text", "required": False, "max_length": 300},
                 {"id": "relationships", "label": "Relationship with the Institution — tick the categories represented among respondents",
                  "type": "multiselect", "required": True, "options": rel}]},
            {"id": "survey", "title": "Feedback Survey Form",
             "fields": [dict({"id": "ratings", "label": "Consolidated average per statement", "type": "ratings", "required": True,
                              "items": CURRICULUM_QUESTIONS}, **SCALE)]},
            {"id": "suggestions", "title": "Suggestions if Any",
             "fields": [{"id": "suggestions", "label": "Consolidated suggestions received", "type": "longtext", "required": False, "max_length": 6000}]},
        ]
        rules = [{"type": "lte", "a": "respondents", "b": "surveyed", "message": "Respondents cannot exceed the number surveyed."}]
        title = "Curriculum Feedback Survey Form"
    else:
        sections = [
            {"id": "variants", "title": "Alumni survey variant(s)",
             "intro": "Select the variant(s) the college collected this period. The college decides which alumni belong to each "
                      "variant (the source titles do not classify exactly four years). Data of a deselected variant stays in the "
                      "draft but is not submitted or printed. Scores of the two variants are never combined.",
             "fields": [{"id": "variants", "label": "Variants included in this report", "type": "multiselect", "required": True,
                         "options": [VARIANT_9A, VARIANT_9B]}] + common}]
        rules = []
        for code, variant, questions, more in (("9a", VARIANT_9A, ALUMNI_9A_QUESTIONS, "more"), ("9b", VARIANT_9B, ALUMNI_9B_QUESTIONS, "less")):
            when = {"field": "variants", "contains": variant}
            pre = f"v{code}_"
            fields = _counts(pre, "alumni", when) + [
                {"id": f"{pre}passing_years", "label": "Passing Year(s) represented (optional)", "type": "text", "required": False,
                 "max_length": 120, "when": when, "placeholder": "e.g. 2016–2020"},
                {"id": f"{pre}status", "label": "Current Status categories represented (optional)", "type": "multiselect",
                 "required": False, "options": ALUMNI_STATUS, "when": when},
                {"id": f"{pre}expect_technology", "label": "Industry expectations from student — Technology (consolidated, optional)",
                 "type": "longtext", "required": False, "max_length": 2000, "when": when},
                {"id": f"{pre}expect_platform", "label": "Industry expectations from student — Platform (consolidated, optional)",
                 "type": "longtext", "required": False, "max_length": 2000, "when": when},
                {"id": f"{pre}expect_others", "label": "Industry expectations from student — Others (consolidated, optional)",
                 "type": "longtext", "required": False, "max_length": 2000, "when": when},
                dict({"id": f"{pre}ratings", "label": "Consolidated average per statement", "type": "ratings", "required": True,
                      "items": questions, "when": when}, **SCALE),
                {"id": f"{pre}suggestions", "label": "Consolidated suggestions received", "type": "longtext", "required": False,
                 "max_length": 6000, "when": when, "help": ALUMNI_SUGGESTIONS},
            ]
            sections.append({"id": f"alumni_{code}", "title": f"KRA {code}: Alumni Survey Form (for alumni having {more} than 4 years professional experience)",
                             "intro": f"Used only when {code} is selected above.", "fields": fields})
            rules.append({"type": "lte", "a": f"{pre}respondents", "b": f"{pre}surveyed", "when": when,
                          "message": "Respondents cannot exceed the number surveyed."})
        title = "Alumni Survey Form"
    source, checksum = SURVEY_SOURCES[kra]
    schema = {
        "key": f"kra{kra}", "version": 1, "title": f"{title} — consolidated (KRA {kra})",
        "family": {"name": "survey", "kra": kra},
        "renderer": "reports/survey_family_v1.html",
        "source": source, "source_checksum": checksum,
        **({"source_checksums": {"9a": checksum, "9b": "cb414a11e3137e5b3b7a89c1c94130b8ccf6f7efbad369b43f0487ed5f07751d"}}
           if kra == 9 else {}),
        "page": {"format": "Letter", "landscape": False, "style": "survey"},
        "activity": {"label": "Report", "min": 1, "max": 1},
        "rules": rules,
        "sections": sections + _analysis_sections(),
        "evidence": {"categories": SURVEY_EVIDENCE, "required": [],
                     "note": "No minimum evidence set has been agreed for KRAs 8–10 (docs/decisions.md D-038). Upload BoS minutes once available."},
    }
    return copy.deepcopy(schema)


NA = "Not applicable (consolidated report)"


def _ratings_rows(items, values):
    values = values if isinstance(values, list) else []
    return [(n + 1, item, values[n] if n < len(values) and values[n] is not None else "") for n, item in enumerate(items)]


def _respondents(act, pre, who):
    r, s = act.get(f"{pre}respondents"), act.get(f"{pre}surveyed")
    show = lambda v: "__" if v in (None, "") else v
    return f"Consolidated response of {show(r)} of {show(s)} {who} surveyed"


def survey_parts(schema, act, snap):
    """Display data for survey_family_v1.html: one part per survey form (KRA 9: only selected variants, 9a before 9b)."""
    kra = schema["family"]["kra"]
    dept = snap["department"]["name"]
    if kra in (8, 10):
        rel = act.get("relationships") or []
        options = next(f for s in schema["sections"] for f in s["fields"] if f["id"] == "relationships")["options"]
        parts = [{
            "title": "Curriculum Feedback Survey Form", "subtitle": "", "details_heading": "Details Required",
            "who": "respondent",
            "details": [("Name of Organization", act.get("organizations", ""), False),
                        ("Name Respondent", _respondents(act, "", "respondents"), False),
                        ("Designation", act.get("designations") or NA, not act.get("designations")),
                        ("Email/Contact Number", NA, True)],
            "relationships": [(o, o in rel) for o in options],
            "grid_heading": "Feedback Survey Form", "grid_first": "Tick Any<br>Grading from 1 to 5",
            "items": _ratings_rows(CURRICULUM_QUESTIONS, act.get("ratings")),
            "suggestions_label": "Suggestions if Any:", "suggestions": act.get("suggestions", ""),
            "respondents": act.get("respondents"),
        }]
    else:
        parts = []
        chosen = act.get("variants") or []
        for code, variant, questions, more in (("9a", VARIANT_9A, ALUMNI_9A_QUESTIONS, "more"), ("9b", VARIANT_9B, ALUMNI_9B_QUESTIONS, "less")):
            if variant not in chosen:
                continue
            pre = f"v{code}_"
            status = act.get(f"{pre}status") or []
            parts.append({
                "title": "Alumni Survey Form", "code": code,
                "subtitle": f"(For Alumni having {more} than 4 Years Professional Experience after Passing Degree Course)",
                "details_heading": "ALUMNI PROFILE", "who": "alumni",
                "details": [("Name of Alumnus/ Alumna", _respondents(act, pre, "alumni"), False),
                            ("Age", NA, True), ("Gender", NA, True), ("Department of Study", dept, False),
                            ("Passing Year", act.get(f"{pre}passing_years") or "Not entered", not act.get(f"{pre}passing_years")),
                            ("Mobile Number", NA, True), ("Email ID", NA, True),
                            ("Current Status (Choose one of the suitable option)",
                             ", ".join(s for s in ALUMNI_STATUS if s in status) or "Not entered", not status),
                            ("Current Position & Company Name", NA, True)],
                "experience_na": True,
                "expectations": [("Technology", act.get(f"{pre}expect_technology", "")),
                                 ("Platform", act.get(f"{pre}expect_platform", "")),
                                 ("Others", act.get(f"{pre}expect_others", ""))],
                "grid_heading": "ALUMNI FEEDBACK FORM", "grid_first": "Tick Any Grading<br>from 1 to 5",
                "items": _ratings_rows(questions, act.get(f"{pre}ratings")),
                "suggestions_label": ALUMNI_SUGGESTIONS, "suggestions": act.get(f"{pre}suggestions", ""),
                "respondents": act.get(f"{pre}respondents"),
            })
    return {"survey_parts": parts}


PREPARERS = {"survey": survey_parts}


BUILDERS = {VARIANTS[k]["key"]: (lambda k=k: course_family_schema(k)) for k in VARIANTS}
BUILDERS.update({FDP_VARIANTS[k]["key"]: (lambda k=k: fdp_stp_schema(k)) for k in FDP_VARIANTS})
BUILDERS.update({f"kra{k}": (lambda k=k: survey_schema(k)) for k in (8, 9, 10)})
