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


BUILDERS = {VARIANTS[k]["key"]: (lambda k=k: course_family_schema(k)) for k in VARIANTS}
