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


def kra3637_programme(kra, i=1, participants=3, modules=4, hours="32", long_text=False):
    extra = " covering synthetic patent filing and prior-art search practice" * (4 if long_text else 0)
    p = {
        "programme_title": f"Synthetic {'FDP on IPR and Innovation' if kra == 37 else 'Office Procedures Training'} {i}",
        "duration_hours": hours, "dates": "12–16 October 2026", "organized_by": "Test Department",
        "mode": ["Offline", "Online", "Hybrid"][i % 3],
        "target_group": "Faculty members" if kra == 37 else "Administrative and non-teaching staff",
        "participants_count": participants, "coordinator": f"Test Coordinator {i}, Zoë Łukasz",
        "resource_persons": "Test Resource Person A\nTest Resource Person B",
        "introduction": "Synthetic introduction for layout testing." * (20 if long_text else 2),
        "other_objectives": "Synthetic objective written by the Dean" + ("\nAnother synthetic objective" if kra == 36 else ""),
        "participants": [{"name": f"Test Participant {n + 1} Śarmā", "department": "Test Department",
                          "designation": "Assistant Professor" if kra == 37 else "Office Assistant",
                          "attendance": "Full (5/5 days)", "certificate": f"Issued, No. TST-{n:03d}" if n % 4 else ""}
                         for n in range(participants)],
        "modules": [{"topic": f"Synthetic module {m + 1}{extra}", "hours": "8"} for m in range(modules)],
        "other_outcomes": "Synthetic outcome recorded by the Dean",
        "assessment_method": "Synthetic quiz", "min_attendance": "80%", "passing_criteria": "Attendance and quiz",
        "certificate_authority": "Test Department", "certificates_issued": participants,
        "formats": ["Expert lectures", "Case studies"], "impact_details": "Synthetic impact note." * (25 if long_text else 1),
        "prepared_name": "Test Coordinator", "prepared_designation": "Associate Professor", "prepared_date": "2026-10-17",
        "approved_name": "", "approved_designation": "", "approved_date": "",
        "supporting_documents": {},
    }
    if kra == 37:
        p.update(focus_areas=["Intellectual Property Rights (IPR)"],
                 objectives=["To strengthen research, innovation and consultancy capabilities."],
                 outcomes=["Develop research and innovation capabilities."])
    return p


def kra3637_payload(kra, programmes=1, participants=3, modules=4, hours="32", long_text=False):
    return {"activities": [kra3637_programme(kra, i + 1, participants, modules, hours, long_text) for i in range(programmes)]}


def kra8_10_payload(kra, long_text=False):
    para = "Synthetic consolidated text for layout testing. " * (40 if long_text else 2)
    return {"activities": [{
        "collection_period": "1–15 October 2026", "consolidated_by": "Test Coordinator, IQAC Cell",
        "surveyed": 20, "respondents": 14, "organizations": "Example Industries Pvt Ltd\nSample Systems Ltd (synthetic)",
        "designations": "", "relationships": ["Employer of Graduates", "Recruiter"] if kra == 8 else ["Academic Expert"],
        "ratings": ["4.25", "3.80", "4", "4.05", "3.5", "4.71", "2.95", "4.10", "3.33", "1.05", "5", "4.00"],
        "suggestions": "Synthetic suggestion one\nSynthetic suggestion two" + ("\n" + para if long_text else ""),
        "action_taken": para, "impact_analysis": "Pending — synthetic, review due next semester.",
        "bos_discussion": para, "report_date": "2026-10-20",
    }]}


def kra9_payload(variants=("9a", "9b"), long_text=False):
    from apps.reports.families import VARIANT_9A, VARIANT_9B
    para = "Synthetic consolidated text for layout testing. " * (40 if long_text else 2)
    act = {"variants": [{"9a": VARIANT_9A, "9b": VARIANT_9B}[v] for v in variants],
           "collection_period": "1–15 October 2026", "consolidated_by": "Test Coordinator, Alumni Cell",
           "action_taken": para, "impact_analysis": "Pending — synthetic.", "bos_discussion": para, "report_date": "2026-10-20"}
    for code, base in (("9a", "4"), ("9b", "3")):
        act.update({f"v{code}_surveyed": 30, f"v{code}_respondents": 22, f"v{code}_passing_years": "2016–2020" if code == "9a" else "2022–2024",
                    f"v{code}_status": ["Pvt. sector", "Higher Education"], f"v{code}_expect_technology": f"Synthetic {code} technology expectation",
                    f"v{code}_expect_platform": "", f"v{code}_expect_others": "",
                    f"v{code}_ratings": [f"{base}.{n}5" for n in range(10)],
                    f"v{code}_suggestions": f"Synthetic {code} suggestion" + ("\n" + para if long_text else "")})
    return {"activities": [act]}


def kra19_visit(i=1, matrix_rows=4, long_text=False, sparse_matrix=False):
    para = "Synthetic observation for layout testing." * (25 if long_text else 2)
    matrix = []
    for r in range(matrix_rows):
        row = {"outcome": f"Synthetic learning outcome {r + 1}" + (" about automation lines and quality systems" * 3 if long_text else "")}
        for po in range(1, 13):
            row[f"po{po}"] = "" if (sparse_matrix and po % 3) else ["3", "2", "1", "H", "M"][(r + po) % 5]
        row["pso1_a"], row["pso1_b"] = ("2", "") if r % 2 else ("", "3")
        matrix.append(row)
    return {
        "visit_date": f"2026-09-{10 + i:02d}", "year_semester": "3rd Year / Odd Semester",
        "faculty_coordinators": f"Test Coordinator {i}, Zoë Łukasz", "hod": "Test Head of Department",
        "industry_name": f"Example Manufacturing Plant {i} (synthetic)", "students_participated": 58, "students_eligible": 64,
        "industry_profile": "Synthetic profile of the industry.\n" + para,
        "experts": [{"name": f"Test Expert {e + 1}", "designation": "Plant Engineer", "topics": "Industrial automation, Career opportunities"}
                    for e in range(2)],
        "objectives": "Synthetic objective one\nSynthetic objective two",
        "technical_overview": "Synthetic technical overview. " + para,
        "departments_visited": [{"department": f"Synthetic Assembly Shop {d + 1}", "purpose": "Synthetic purpose",
                                 "activities": "Synthetic activities", "machinery": "Synthetic CNC line" if d % 2 == 0 else "",
                                 "principles": "", "observations": ("Synthetic observation. " + para)[:790]} for d in range(3 if long_text else 2)],  # within the 800-char limit
        "equipment": "Synthetic equipment list", "quality_safety": "Synthetic PPE and inspection practices observed",
        "environmental": "Not observed",
        "learning_outcomes": "Synthetic learning outcome 1\nSynthetic learning outcome 2",
        "courses": [{"course_name": "Synthetic Manufacturing Processes", "course_code": "TST301", "year_semester": "3rd / V"}],
        "lo_matrix": matrix,
        "gaps": [{"gap": "Theory-Practice Gap (synthetic)", "solution": "Observed live production line (synthetic)"}],
        "suggestions": "Synthetic suggestion", "conclusion": "Synthetic conclusion. " + para,
        "coordinator_remarks": "Synthetic remark", "coordinator_name": "Test Coordinator",
        "feedback_responses": 40,
        "feedback_ratings": ["4.20", "4", "3.85", "4.10", "3.9", "4.05", "4.30", "3.75", "4.5", "4.25"],
        "feedback_summary": "Synthetic consolidated feedback summary.",
        "annexures": {"Industrial Visit Approval": "Yes", "Attendance Record": "Yes", "Student’s Feedback": "Yes"},
    }


def kra19_payload(visits=1, matrix_rows=4, long_text=False, sparse_matrix=False):
    return {"activities": [kra19_visit(i + 1, matrix_rows, long_text, sparse_matrix) for i in range(visits)]}


KRA18_EVIDENCE = ['ev_signed_mou', 'ev_notice', 'ev_schedule', 'ev_attendance', 'ev_photographs', 'ev_report', 'ev_expert_profile', 'ev_feedback', 'ev_certificates', 'ev_web_link', 'ev_outcome']


def kra18_activity(m=1, i=1, long_text=False):
    para = "Synthetic description sentence for layout testing. " * (30 if long_text else 3)
    row = {"title": f"Synthetic MoU activity {m}.{i}", "activity_date": f"2026-09-{10 + i:02d}", "duration": "3 hours",
           "activity_type": "Other" if i == 3 else ["Expert Talk", "Workshop", "Training", "Joint Research"][i % 4],
           "activity_type_other": "Synthetic hackathon" if i == 3 else "", "venue": "Seminar Hall (synthetic)",
           "mode": "Offline", "target_participants": "Students / Faculty", "programme_branch": "B.Tech ECE",
           "participants": 40 + i, "resource_person": f"Test Expert {m}.{i}", "rp_designation": "Senior Engineer, Example Labs (synthetic)",
           "key_topics": "Synthetic topic A\nSynthetic topic B", "objective": "Synthetic objective of the MoU activity. " + para[:200],
           "description": para, "outcomes": "Synthetic outcome one\nSynthetic outcome two" + ("\nSynthetic further outcome" * 8 if long_text else "")}
    row.update({k: ("Yes" if n % 3 else "No") for n, k in enumerate(KRA18_EVIDENCE)})
    row["ev_web_link"] = ""  # unanswered item prints a dash
    return row


def kra18_mou(m=1, activities=2, long_text=False):
    return {"org_name": f"Example Research Organization {m} (synthetic)", "org_type": "Research Organization",
            "mou_ref": f"SYN/MOU/{m:03d}", "signing_date": "2025-07-01", "validity": "5 years, up to 30 Jun 2030",
            "coord_institution": "Test Coordinator (KIET)", "coord_organization": f"Test Partner Coordinator {m}",
            "mou_activities": [kra18_activity(m, i + 1, long_text) for i in range(activities)]}


def kra18_payload(mous=1, activities=2, long_text=False):
    return {"activities": [kra18_mou(m + 1, activities, long_text) for m in range(mous)]}


def kra17_centre(i=1, long_text=False):
    return {"centre_name": f"Synthetic IoT Training Centre {i}", "industry_partner": f"Example Industry Partner {i} (synthetic)",
            "nature": ["Joint Lab", "Training Centre", "Centre of Excellence (CoE)"][i % 3], "date_established": "2026-08-20",
            "mou_date": "" if i % 4 == 0 else "2026-07-15", "mou_validity": "" if i % 4 == 0 else "5 years",
            "location": f"Block A, Room {200 + i}",
            "facilities": "Synthetic workstations, development kits, oscilloscopes" + (", additional synthetic equipment" * 12 if long_text else ""),
            "purpose": "Synthetic embedded systems training" + (" for final-year projects and certification" * 4 if long_text else ""),
            "faculty_coordinator": f"Test Faculty {i}", "industry_coordinator": f"Test Industry Coordinator {i}", "status": "Active"}


def kra17_payload(centres=2, long_text=False):
    return {"activities": [{"centres": [kra17_centre(i + 1, long_text) for i in range(centres)]}]}


KRA13IAB_CONTRIBUTIONS = ["Participation in Board/Committee Meeting", "Curriculum / Syllabus Review", "Industry/Professional Expert Inputs",
                       "Review of Student Projects / Training", "Internship / Placement Facilitation", "Guest Lecture / Expert Talk / Workshop",
                       "Research / Consultancy / Collaborative Activity", "Any Other Contribution"]


def kra13iab_membership(i=1, contributions=3, meetings=2, long_text=False):
    extra = " Synthetic additional detail for layout testing." * (12 if long_text else 0)
    return {
        "faculty_name": f"Test Faculty {i}", "designation": "Associate Professor", "employee_id": f"T{1000 + i}",
        "organization": f"Example Industry Council {i} (synthetic)", "committee_type": "Other" if i % 3 == 0 else "Industry Advisory Board",
        "committee_type_other": "Government committee (synthetic)" if i % 3 == 0 else "",
        "committee_name": f"Synthetic Advisory Board {i}", "appointment_date": "2025-06-01", "tenure_from": "2025-07-01",
        "tenure_to": "" if i % 2 == 0 else "2027-06-30", "membership_nature": "Expert Member",
        "appointing_authority": "Example Industry Council (synthetic)", "committee_org": "", "chairperson": "Test Chairperson, Director (synthetic)",
        "purpose": "Synthetic advisory purpose." + extra, "domain": "Embedded systems", "website": "",
        "objectives": ["To obtain industry/professional inputs for curriculum development and academic improvement."],
        "other_objectives": "Synthetic additional objective",
        "contributions": [{"activity": KRA13IAB_CONTRIBUTIONS[n % 8], "period": "Aug 2026",
                           "contribution": f"Synthetic contribution {n + 1}." + extra} for n in range(contributions)],
        "meetings": [{"meeting_date": f"2026-0{8 + n % 2}-1{n % 9}", "meeting_ref": f"SYN-M{n + 1}", "agenda": "Synthetic agenda." + extra,
                      "contribution": "Synthetic inputs given." + extra, "evidence": "Minutes / Attendance"} for n in range(meetings)],
        "impact_students": "Synthetic student impact.", "impact_curriculum": "Synthetic curriculum impact.",
        "impact_industry": "Not applicable", "impact_research": "Not applicable", "impact_quality": "Synthetic quality impact." + extra,
        "documents": {"Appointment / Nomination / Invitation Letter": "Yes", "Minutes of Meeting": "Yes", "Membership Certificate, if applicable": "No"},
        "other_documents": "",
        "total_period": "2 years (2025–2027)", "meetings_attended": meetings, "major_activities": "Synthetic activities." + extra,
        "recommendations": "Synthetic recommendations.", "major_outcomes": "Synthetic outcomes.", "student_beneficiaries": "",
        "orgs_involved": "Example Industry Council (synthetic)", "hod_name": "", "hod_designation": "",
    }


def kra13iab_payload(members=1, contributions=3, meetings=2, long_text=False):
    return {"activities": [kra13iab_membership(i + 1, contributions, meetings, long_text) for i in range(members)]}
