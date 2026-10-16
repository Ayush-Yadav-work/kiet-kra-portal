"""SYNTHETIC TEST DATA ONLY — fictitious names/events for tests and local visual checks. Never seed into production."""

CHECKLIST = ["Alumni Association/Chapter Details", "Activity Approval", "Event Notice/Invitation", "Event Brochure/Poster",
             "Alumni Registration List", "Attendance Sheet", "Alumni Profile/Details", "Photographs", "Activity Report",
             "Feedback", "Certificates/Recognition", "Website/News Coverage", "Outcome/Impact Evidence"]


def kra33_activity(i=1, rows=3, long_text=False):
    para = ("Synthetic description sentence for layout testing with Unicode names like Aarav Śarmā, Zoë Müller "
            "and Łukasz Ñúñez. ")
    return {
        "chapter_name": f"Test Alumni Chapter {i}",
        "event_name": f"Synthetic Alumni Meet {i}",
        "activity_type": "Alumni Meet",
        "date": "2026-09-1" + str(i % 10),
        "time": "10:00 AM – 1:00 PM",
        "venue_mode": "Seminar Hall (Offline)",
        "organized_by": "Test Department Alumni Cell",
        "alumni_coordinator": "Test Alumni Coordinator",
        "faculty_coordinator": "Test Faculty Coordinator",
        "alumni_count": 12,
        "student_count": 85,
        "objective": "Synthetic objective text for this test event.",
        "description": para * (40 if long_text else 3),
        "major_activities": ["Alumni–student interaction", "Career guidance and mentoring", "Alumni networking"],
        "major_other": "Synthetic other activity",
        "engagements": [
            {"alumni_name": f"Test Alumnus {r + 1}", "batch_programme": "2018 B.Tech",
             "organization": "Example Corp / Engineer", "nature": ["Mentoring", "Expert Talk", "Career Guidance"][r % 3],
             "date_activity": "15 Sep 2026", "students_benefited": 20 + r}
            for r in range(rows)
        ],
        "p_alumni": 12, "p_students": 85, "p_faculty": 6, "p_external": 2, "p_total": 105,
        "outcomes": "Synthetic outcome one\nSynthetic outcome two",
        "feedback": "Synthetic feedback summary.",
        "doc_checklist": {item: ("Yes" if n % 3 else "No") for n, item in enumerate(CHECKLIST)},
        "coordinator_name": "Test Faculty Coordinator",
        "report_date": "2026-09-20",
    }


def kra33_payload(events=1, rows=3, long_text=False):
    return {"activities": [kra33_activity(i + 1, rows, long_text) for i in range(events)]}


def kra20_payload(rows=5, long_text=False):
    out = []
    for i in range(rows):
        out.append({
            "faculty_name": f"Test Faculty {i + 1} Ñúñez-Śarmā", "employee_id": f"T{1000 + i}",
            "designation": "Assistant Professor", "organization": f"Example Industries Pvt Ltd Unit {i % 4 + 1}",
            "training_title": "Synthetic industrial training on embedded systems" + (" and IoT deployment practices" * 3 if long_text else ""),
            "start_date": "2026-09-01", "end_date": "2026-09-12", "duration": "12 days",
            "mode": "Offline" if i % 3 else "Online", "certificate_no": f"CERT-TEST-{i:03d}" if i % 4 else "",
            "mentor": "Test Mentor", "outcome": "Synthetic outcome: lab exercise redesigned." * (6 if long_text else 1),
        })
    return {"activities": [{"trainings": out}]}


def kra7_payload(long_text=False):
    para = "Synthetic consolidated text for layout testing. " * (40 if long_text else 2)
    return {"activities": [{
        "semester": "Odd semester", "subjects": "Synthetic Subject A; Synthetic Subject B" + ("; Synthetic Subject C" * 10 if long_text else ""),
        "collection_period": "1–15 October 2026", "eligible": 42, "respondents": 38,
        "consolidated_by": "Test Coordinator, IQAC Cell",
        "ratings": ["4.25", "3.80", "4", "4.05", "3.5", "4.71", "2.95", "4.10", "3.33", "1.05"],
        "overall_satisfaction": "7.85",
        "suggestions": "Synthetic suggestion one\nSynthetic suggestion two" + ("\n" + para if long_text else ""),
        "action_taken": para, "impact_analysis": "Pending — synthetic, review due next semester.",
        "bos_discussion": para, "report_date": "2026-10-20",
    }]}


def kra32_payload(rows=4, long_text=False):
    out = []
    types = ["Financial Contribution", "Equipment/Asset", "Financial Contribution", "Other Non-financial"]
    for i in range(rows):
        t = types[i % 4]
        row = {"association_name": "Synthetic KIET Alumni Association", "registration_no": "REG-TEST-001",
               "donor_name": f"Test Alumna {i + 1} Zoë Łukasz", "alumni_id": f"ALM-T{i:04d}",
               "contribution_date": "2026-09-2" + str(i % 9), "contribution_type": t,
               "purpose": "Synthetic scholarship fund" if t.startswith("Financial") else "Synthetic lab equipment",
               "utilization": "Synthetic utilization note." * (8 if long_text else 1), "evidence_ref": f"Receipt {i + 1}"}
        if t.startswith("Financial"):
            row.update(amount=["25000.00", "2500.5"][(i // 2) % 2], payment_mode=["NEFT", "UPI"][(i // 2) % 2],
                       receipt_no=f"RCPT-T{i:03d}", transaction_ref=f"TXN-SYN-{i:06d}")
        else:
            row["item_details"] = "2 synthetic oscilloscopes" + (" with accessories and manuals" * 4 if long_text else "")
        out.append(row)
    return {"activities": [{"contributions": out}]}


KRA11_DOCS = ["Approval/permission for conducting the course", "Course proposal/concept note", "Course syllabus/content",
              "Academic calendar/activity schedule", "Course timetable", "Resource person/faculty details",
              "Expert profile/CV, wherever applicable", "Attendance records", "Registration/enrolment records",
              "Assessment records", "Result/score sheet", "Student feedback", "Sample certificates",
              "Photographs with date and caption", "Geo-tagged photographs, wherever applicable", "Course completion report",
              "List of students who completed the course", "Any other relevant supporting document"]


def kra11_course(i=1, modules=4, long_text=False):
    extra = " covering synthetic worked examples and practice sets" * (4 if long_text else 0)
    return {
        "year_semester": "1st Year / Odd Semester", "faculty_coordinators": f"Test Coordinator {i}, Zoë Ñúñez",
        "hod": "Test Head of Department", "additional_objectives": "Synthetic extra objective" if i == 1 else "",
        "course_name": f"Synthetic Bridge Course {i}: Mathematics Foundations", "duration_hours": "30",
        "mode": ["Offline", "Online", "Hybrid"][i % 3], "resource_person": "Test Resource Person",
        "students_enrolled": 120, "students_completed": 112,
        "modules": [{"topic": f"Synthetic topic {m + 1}{extra}", "hours": "7.5"} for m in range(modules)],
        "learning_outcomes": "Synthetic outcome one\nSynthetic outcome two" + ("\nSynthetic long outcome" * 10 if long_text else ""),
        "assessment_method": "Synthetic quiz and assignment", "min_attendance": "75%", "passing_criteria": "40% aggregate",
        "certificate_authority": "Test Department", "certificates_issued": 110,
        "impact_indicators": ["Improvement in technical/professional skills", "Successful completion/certification rate"],
        "impact_details": "Synthetic impact note." * (30 if long_text else 1),
        "feedback_score": "4.35", "suggestions": "Synthetic suggestion A\nSynthetic suggestion B",
        "prepared_name": "Test Coordinator", "prepared_designation": "Assistant Professor", "prepared_date": "2026-10-05",
        "approved_name": "", "approved_designation": "", "approved_date": "",
        "supporting_documents": {d: ("Yes" if n % 5 else "No") for n, d in enumerate(KRA11_DOCS)},
    }


def kra11_payload(courses=2, modules=4, long_text=False):
    return {"activities": [kra11_course(i + 1, modules, long_text) for i in range(courses)]}


KRA23_DOCS = ["Approval/permission for conducting the course", "Proposal/concept note", "Course syllabus/content",
              "Academic calendar/activity schedule", "Timetable", "Resource person/faculty details",
              "Expert profile/CV, wherever applicable", "Attendance records", "Registration/enrolment records",
              "Assessment records", "Result/score sheet", "Student feedback", "Sample certificates",
              "Photographs with date and caption", "Geo-tagged photographs, wherever applicable", "Course completion report",
              "List of students who completed the course", "Any other relevant supporting document"]


def kra23_programme(i=1, programs=2, modules=4, long_text=False):
    extra = " with synthetic case studies and pitch practice" * (4 if long_text else 0)
    return {
        "programme_title": f"Synthetic Entrepreneurship Bootcamp {i}", "year_semester": "3rd Year / Odd Semester",
        "faculty_coordinators": f"Test Coordinator {i}, Śarmā Łukasz", "hod": "Test Head of Department",
        "objectives": ["To develop an entrepreneurial mind-set among students.",
                       "To enhance entrepreneurial and employability skills."],
        "other_objectives": "Synthetic additional objective" if i == 1 else "",
        "programs": [{"program_name": f"Synthetic Module Batch {p + 1}{extra}", "duration_hours": "12.5",
                      "mode": ["Offline", "Online", "Hybrid"][p % 3], "resource_agency": "Example Incubation Agency",
                      "students_enrolled": 60, "students_completed": 55} for p in range(programs)],
        "modules": [{"topic": f"Synthetic topic {m + 1}{extra}", "hours": "3"} for m in range(modules)],
        "learning_outcomes": "Synthetic outcome one\nSynthetic outcome two" + ("\nSynthetic long outcome" * 10 if long_text else ""),
        "assessment_method": "Synthetic business-plan pitch", "min_attendance": "80%", "passing_criteria": "Pitch submitted",
        "certificate_authority": "Test Incubation Cell", "certificates_issued": 52,
        "impact_indicators": ["Improvement in employability skills"],
        "impact_details": "Synthetic impact note." * (30 if long_text else 1),
        "feedback_score": "4.6", "suggestions": "Synthetic suggestion A",
        "prepared_name": "Test Coordinator", "prepared_designation": "Associate Professor", "prepared_date": "2026-10-08",
        "approved_name": "", "approved_designation": "", "approved_date": "",
        "supporting_documents": {d: ("Yes" if n % 4 else "No") for n, d in enumerate(KRA23_DOCS)},
    }


def kra23_payload(programmes=1, programs=2, modules=4, long_text=False):
    return {"activities": [kra23_programme(i + 1, programs, modules, long_text) for i in range(programmes)]}


def kra13_course(kra, i=1, modules=4, long_text=False):
    extra = " with synthetic lab exercises and reading" * (4 if long_text else 0)
    c = {
        "year_semester": "2nd Year / Even Semester", "faculty_coordinators": f"Test Coordinator {i}, Zoë Łukasz",
        "hod": "Test Head of Department",
        "objectives": ["To supplement the knowledge acquired through the regular curriculum."],
        "other_objectives": "Synthetic extra objective" if i == 1 else "",
        "course_name": f"Synthetic KRA{kra} Course {i}", "duration_hours": "30", "mode": ["Offline", "Online", "Hybrid"][i % 3],
        "resource_agency": "Test Resource Agency", "students_enrolled": 80, "students_completed": 72,
        "modules": [{"topic": f"Synthetic topic {m + 1}{extra}", "hours": "7.5"} for m in range(modules)],
        "learning_outcomes": "Synthetic outcome one\nSynthetic outcome two" + ("\nSynthetic long outcome" * 10 if long_text else ""),
        "assessment_method": "Synthetic quiz", "min_attendance": "75%", "passing_criteria": "40% aggregate",
        "certificate_authority": "Test Department", "certificates_issued": 70,
        "impact_indicators": ["Industry certification obtained"], "impact_details": "Synthetic impact note." * (30 if long_text else 1),
        "feedback_score": "4.1", "suggestions": "Synthetic suggestion A",
        "prepared_name": "Test Coordinator", "prepared_designation": "Assistant Professor", "prepared_date": "2026-10-09",
        "approved_name": "", "approved_designation": "", "approved_date": "",
        "supporting_documents": {d: ("Yes" if n % 3 else "No") for n, d in enumerate(KRA11_DOCS)},  # same 18 items as KRA 1-3 source
    }
    if kra == 1:
        c.update(course_code=f"TST{100 + i}", approval_ref="Synthetic BoS item 4.2")
    if kra == 3:
        c.update(platform="SWAYAM")
    return c


def kra13_payload(kra, courses=1, modules=4, long_text=False):
    return {"activities": [kra13_course(kra, i + 1, modules, long_text) for i in range(courses)]}
