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


def kra15_entrepreneur(i=1, long_text=False):
    category = ["Student", "Alumni", "Faculty"][i % 3]
    student = category != "Faculty"
    return {"name": f"Test Entrepreneur {i} Zoë", "category": category, "member_id": f"SYN{2200 + i}" if student else f"T{1000 + i}",
            "programme": "B.Tech ECE" if student else "", "batch": "2022–2026" if student else "", "gender": ["Female", "Male", "Other"][i % 3],
            "enterprise": f"Synthetic Ventures {i}" + (" Private Limited for embedded and IoT product engineering" if long_text else ""),
            "sector": "IoT / Embedded" + (" systems for agriculture and healthcare" if long_text else ""),
            "founder_role": "Founder" if i % 2 else "Co-Founder", "year_established": 2024 + i % 3,
            "registration_no": "" if i % 4 == 0 else f"SYN-DPIIT{i:05d}", "status": "Active" if i % 5 else "Closed",
            "evidence_available": "Yes" if i % 4 else "No"}


def kra15_payload(rows=3, long_text=False):
    return {"activities": [{"records": [kra15_entrepreneur(i + 1, long_text) for i in range(rows)]}]}


def kra22_activity(i=1, long_text=False):
    return {"date": f"2026-09-{1 + i % 28:02d}", "title": f"Synthetic career session {i}" + (" on emerging roles in semiconductor design" if long_text else ""),
            "activity_type": ["Counselling", "Expert Talk", "Workshop (synthetic)"][i % 3],
            "career_domain": ["IT/Software", "Higher Studies", "Core Engineering"][i % 3], "target_programme": "B.Tech ECE",
            "resource_person": f"Test Counsellor {i}", "organization": "Example Careers Pvt Ltd (synthetic)", "duration": "2 hours",
            "students": 60 + i, "faculty": i % 4,
            "outcome": "Synthetic outcome: students mapped career options." + (" Synthetic follow-up actions recorded." * 10 if long_text else "")}


def kra22_payload(rows=3, long_text=False):
    return {"activities": [{"records": [kra22_activity(i + 1, long_text) for i in range(rows)]}]}


def kra31_event(i=1, long_text=False):
    return {"event_id": "" if i % 3 == 0 else f"SYN-EV-{i:02d}", "name": f"Synthetic Hack {i}" + (" for smart mobility and clean energy solutions" if long_text else ""),
            "event_type": "Hackathon" if i % 2 else "Ideathon", "level": "National" if i % 2 else "State",
            "date": f"2026-09-{1 + i % 28:02d}", "duration": "24 hours", "organizer": "ECE Department / Innovation Cell (synthetic)",
            "co_organizer": "" if i % 4 == 0 else "Example Partner Foundation (synthetic)", "teams": 20 + i, "participants": 80 + 4 * i,
            "institutions": 5 + i % 7, "mentors": "6" if i % 2 else "Test Mentor A, Test Mentor B",
            "outcome": "Synthetic outcome: prototypes shortlisted." + (" Synthetic incubation follow-up noted." * 8 if long_text else "")}


def kra31_payload(rows=3, long_text=False):
    return {"activities": [{"records": [kra31_event(i + 1, long_text) for i in range(rows)]}]}


KRA38_TYPES = ["Professional Development Programmes", "Orientation/Induction Programmes", "Refresher Course", "Short Term Course"]


def kra38_programme(i=1, long_text=False):
    return {"faculty_name": f"Test Faculty {i} Łukasz" + (" Venkataraghavan Subramanian" if long_text else ""),
            "programme_type": KRA38_TYPES[i % 4], "duration_days": 5, "start_date": f"2026-08-{1 + i % 20:02d}",
            "end_date": f"2026-08-{5 + i % 20:02d}",
            "institution": "Example Institute of Technology (synthetic)" + (", Centre for Continuing Education and Faculty Development" if long_text else "")}


def kra38_payload(rows=3, long_text=False):
    return {"activities": [{"records": [kra38_programme(i + 1, long_text) for i in range(rows)]}]}


def fp_programme(kra, i=1, students=3, has_component="Yes", long_text=False):
    extra = " with an extended synthetic description for layout testing" if long_text else ""
    return {"programme_name": f"Synthetic B.Tech Programme {i}" + extra, "programme_code": f"SYN{100 + i}", "has_component": has_component,
            "component_name": f"Synthetic KRA {kra} component {i}" if has_component == "Yes" else "",
            "course_code": f"TST{kra}{i:02d}" if has_component == "Yes" else "",
            "students_undertaking": students + 2 if has_component == "Yes" else "",
            "document_link": "Evidence: Student List; Completion Certificates" if has_component == "Yes" else "",
            "completions": [{"student_name": f"Test Student {i}.{s + 1} Zoë", "roll_no": f"SYN{kra}{i:02d}{s:03d}",
                             "title": f"Synthetic KRA {kra} work {s + 1}" + extra, "partner": "Example Organization (synthetic)",
                             "start_date": "2026-07-01", "completion_date": "2026-09-15",
                             "document_ref": "" if s % 3 == 2 else f"CERT-{kra}-{i}-{s + 1}"} for s in range(students)]
            if has_component == "Yes" else []}


def fp_payload(kra, programmes=2, students=3, long_text=False):
    return {"activities": [fp_programme(kra, i + 1, students, "No" if i == 1 else "Yes", long_text) for i in range(programmes)]}


def kra24_student(i=1, long_text=False):
    placed = i % 3 != 0
    return {"student_name": f"Test Graduate {i} Zoë", "contact": f"+91 90000 {i:05d}, graduate{i}@example.invalid",
            "category": "Placement" if placed else "Higher Education", "programme": "B.Tech ECE",
            "employer": (f"Example Employer {i} Pvt Ltd (synthetic)" + (", Embedded Systems Business Unit" if long_text else "")) if placed else "",
            "employer_contact": "hr@example.invalid" if placed and i % 2 else "",
            "package_inr": ("650000" if i % 2 else "725000.50") if placed else "",
            "institution": "" if placed else f"Example University {i} (synthetic)",
            "admitted_programme": "" if placed else "M.Tech VLSI Design" + (" (Research track, two-year programme)" if long_text else "")}


def kra24_payload(rows=6, long_text=False):
    return {"activities": [{"records": [kra24_student(i + 1, long_text) for i in range(rows)]}]}


def kra12_award(i=1, long_text=False):
    team = i % 2 == 0
    extra = " Synthetic extended description for layout testing." * (15 if long_text else 0)
    return {"recipients": "Test Faculty A\nTest Student B Zoë\nTest Student C" if team else f"Test Faculty {i}",
            "recipient_category": ["Faculty", "Student", "Department", "Institute"][i % 4], "award_title": f"Synthetic Innovation Award {i}",
            "awarding_body": "Example Science Council (synthetic)", "award_date": f"2026-09-{1 + i % 28:02d}",
            "level": "" if i % 3 == 0 else "National", "contribution": "Synthetic low-cost sensor design." + extra[:400],
            "description": "Synthetic description of the recognition." + extra}


def kra12_payload(awards=3, long_text=False):
    return {"activities": [{"coordinator": "Test Coordinator", "report_date": "2026-10-05",
                            "awards": [kra12_award(i + 1, long_text) for i in range(awards)]}]}


def award_record(kra, i=1, long_text=False):
    team = i % 2 == 0
    sport = "Synthetic Football" if kra == 25 else "Synthetic Group Dance"
    return {"student_names": "\n".join(f"Test Student {i}.{m + 1}" for m in range(11 if long_text else 4)) if team else f"Test Student {i} Zoë",
            "event": (f"{sport} Championship {i}" if team else f"Synthetic Solo Event {i}") + (" — inter-university zonal finals" if long_text else ""),
            "event_date": f"2026-09-{1 + i % 28:02d}", "participation": "Team" if team else "Individual",
            "level": ["University (inter-university)", "State", "National", "International"][i % 4],
            "position": ["First", "Second", "Gold medal", "Third"][i % 4], "organiser": "Example University (synthetic)"}


def award_payload(kra, rows=4, long_text=False):
    return {"activities": [{"records": [award_record(kra, i + 1, long_text) for i in range(rows)]}]}


EVENT_EXTRA = {27: {"sport": "Synthetic Football", "competition_format": "Knockout", "teams": 12},
               28: {"cultural_activity": "Synthetic music and dance"},
               29: {"theme": "Synthetic embedded systems", "sub_events": "Synthetic hackathon\nSynthetic paper presentation"},
               30: {"club_name": "Synthetic Robotics Club", "semester": "Odd"},
               41: {"inclusion_themes": ["Cultural", "Linguistic"], "theme_details": "Synthetic unity-in-diversity festival"},
               42: {"constitutional_aspects": ["Values", "Duties"], "topics": "Synthetic reading of the Preamble and Fundamental Duties"}}
EVENT_CATEGORIES = {27: "Sports competition", 28: "Cultural event", 29: "Technical fest", 30: "Club activity"}


def event_record(kra, i=1, long_text=False):
    para = " Synthetic narrative sentence for layout testing." * (25 if long_text else 2)
    return {"event_title": f"Synthetic KRA {kra} event {i}", **({"category": EVENT_CATEGORIES[kra]} if kra in EVENT_CATEGORIES else {}), **EVENT_EXTRA[kra],
            "start_date": f"2026-09-{10 + i % 15:02d}", "end_date": f"2026-09-{11 + i % 15:02d}", "venue": "Main Auditorium (synthetic)",
            "mode": "Offline", "organizer": "ECE Department (synthetic)", "coordinators": "Test Faculty A, Test Faculty B",
            "student_coordinators": "" if i % 2 else "Test Student Zoë", "collaborators": "", "resource_persons": "Test Judge 1\nTest Judge 2",
            "target_audience": "B.Tech students", "participants_students": 120 + i, "participants_faculty": 6, "participants_external": i % 3,
            "institutions": "" if i % 2 else 4, "objectives": "Synthetic objective one\nSynthetic objective two",
            "description": "Synthetic description." + para, "outcomes": "Synthetic outcome one\nSynthetic outcome two" + ("\nSynthetic outcome more" * 6 if long_text else ""),
            "feedback": "Not collected" if i % 3 == 0 else "Synthetic consolidated feedback.",
            "doc_checklist": {"Event Approval": "Yes", "Attendance Sheet": "Yes", "Feedback": "No"},
            "reported_by": "", "report_date": ""}


def event_payload(kra, events=2, long_text=False):
    return {"activities": [event_record(kra, i + 1, long_text) for i in range(events)]}


def kra43_conference(i=1, long_text=False):
    para = " Synthetic narrative sentence for layout testing." * (25 if long_text else 2)
    verified = i % 2 == 1
    return {"conference_name": f"Synthetic International Conference on Embedded Systems {i}", "start_date": "2026-09-10", "end_date": "2026-09-11",
            "organizers": "ECE Department (synthetic)", "partners": "" if i % 2 else "Example Society (synthetic)", "venue": "KIET Campus (synthetic)",
            "mode": "Hybrid", "coordinators": "Test Convener, Test Coordinator", "delegates": 180 + i, "institutions": 25, "papers_submitted": 140,
            "papers_accepted": 60, "papers_published": 48 if verified else 0, "kiet_accepted": 12, "kiet_published": 10 if verified else 0,
            "publication_status": "Published" if verified else "Not yet published", "publisher": "Example Publisher (synthetic)",
            "isbn_issn": "978-0-000-00000-0", "indexing_status": "Verified in Scopus" if verified else "Planned / applied for",
            "indexing_reference": "https://www.scopus.com/sourceid/000000 (synthetic)" if verified else "",
            "brief_report": "Synthetic brief report." + para, "outcomes": "Synthetic outcome one\nSynthetic outcome two",
            "doc_checklist": {"Approval letter": "Yes", "List of accepted papers": "Yes", "Scopus indexing evidence": "Yes" if verified else "No"}}


def kra43_payload(conferences=1, long_text=False):
    return {"activities": [kra43_conference(i + 1, long_text) for i in range(conferences)]}


def kra44_activity(i=1, long_text=False):
    para = " Synthetic narrative sentence for layout testing." * (20 if long_text else 1)
    return {"activity_name": f"Synthetic Embedded Boot Camp {i}", "activity_id": "" if i % 2 == 0 else f"SYN-BC-{i:02d}",
            "activity_type": ["BOOT Camp", "Peer Learning", "Combined"][i % 3], "theme": "Synthetic IoT prototyping",
            "start_date": "2026-09-14", "end_date": "2026-09-16", "duration": "3 days", "venue": "Lab 204 (synthetic)", "mode": "Offline",
            "organizer": "ECE Department (synthetic)", "faculty_coordinator": "Test Faculty Coordinator", "student_coordinators": "Test Student Zoë",
            "mentors": "Test Mentor A", "introduction": "Synthetic introduction written by the department." + para,
            "objectives": ["To promote experiential and hands-on learning.", "To encourage peer-to-peer knowledge sharing."],
            "other_objectives": "", "time": "10:00 AM – 4:00 PM", "target_group": "Second-year students", "programme": "B.Tech ECE",
            "semester": "III", "registered": 60, "participated": 54, "student_mentors": 6, "faculty_mentors": 2, "sessions": 6,
            "phase_1": "Synthetic orientation held." + para, "phase_2": "Synthetic teams of five formed.", "phase_3": "Synthetic hands-on work." + para,
            "phase_4": "" if i % 2 == 0 else "Synthetic peer sessions.", "phase_5": "Synthetic demos.", "phase_6": "Synthetic feedback collected.",
            "doc_checklist": {"Activity Approval": "Yes", "Attendance Sheet": "Yes", "Certificates, if issued": "No"},
            "coordinator_designation": "Assistant Professor", "hod_name": ""}


def kra44_payload(activities=1, long_text=False):
    return {"activities": [kra44_activity(i + 1, long_text) for i in range(activities)]}


def kra45_event(i=1, long_text=False, resource_persons=2):
    para = " Synthetic narrative sentence for layout testing." * (30 if long_text else 2)
    return {"role": "Organized", "faculty_name": f"Test Faculty {i} Łukasz", "designation": "Associate Professor", "mode": "Hybrid",
            "event_name": f"Synthetic National Flagship Symposium {i}", "level": "National" if i % 2 else "International",
            "sdgs": ["Quality education (SDG 4)", "Industry, innovation and infrastructure (SDG 9)"], "venue": "KIET Auditorium (synthetic)",
            "days": 2, "start_date": "2026-09-18", "end_date": "2026-09-19", "funded_by": "Management", "collaboration": "",
            "participants": 240 + i, "registration_charges": "" if i % 2 else "INR 500",
            "resource_persons": [{"name": f"Test Speaker {i}.{r + 1}", "designation": "Professor", "department": "ECE",
                                  "institution": "Example Institute (synthetic)", "city": "Example City", "state": "Example State",
                                  "country": "India"} for r in range(resource_persons)],
            "brief_report": "Synthetic brief report." + para, "focus": ["Academic Related", "SDG"], "outcome": "Synthetic outcome." + para[:300],
            "sdg_alignment": "Synthetic SDG alignment statement.", "feedback": "Synthetic feedback summary.",
            "follow_up_plan": "" if i % 2 else "Synthetic follow-up plan.",
            "checklist": {"Approval Letter": "Yes", "Event Brochure & Invitation": "Yes", "Budget & Statement of Expenditure": "No"}}


def kra45_payload(events=1, long_text=False, resource_persons=2):
    return {"activities": [kra45_event(i + 1, long_text, resource_persons) for i in range(events)]}


def kra21_programme(i=1, long_text=False, qualifiers=0):
    lines = lambda prefix, n: "\n".join(f"{prefix} {k + 1}" for k in range(n))
    return {"programme_title": f"Synthetic GATE Preparation Programme {i}", "examination": "GATE" if i % 2 else "NET",
            "start_date": "2026-08-03", "end_date": "2026-09-25", "duration": "40 hours over 8 weeks", "mode": "Hybrid",
            "venue": "Seminar Hall 2 / online (synthetic)", "organizer": "ECE Department (synthetic)", "coordinator": "Test Coordinator",
            "trainers": "Test Trainer A, Example Academy (synthetic)\nTest Trainer B, Professor, ECE", "target_group": "B.Tech ECE, 3rd and 4th year",
            "enrolled": 80, "participated": 72, "sessions": "" if i % 2 == 0 else 20,
            "topics": lines("Synthetic topic", 25 if long_text else 4), "outcomes": lines("Synthetic observed outcome", 12 if long_text else 2),
            "evidence_refs": "Notice, Schedule, Attendance Sheet",
            "qualifiers": [{"student_name": f"Test Qualifier {i}.{q + 1}", "year": "2026", "level": "National", "exam": "GATE",
                            "link": "" if q % 2 else "Evidence: Exam Scorecards"} for q in range(qualifiers)]}


def kra21_payload(programmes=1, long_text=False, qualifiers=0):
    return {"activities": [kra21_programme(i + 1, long_text, qualifiers) for i in range(programmes)]}


def kra39_grant(i=1, long_text=False, receipts=2):
    return {"funding_body": f"Example Infrastructure Trust {i} (synthetic)", "body_type": ["Government", "Non-government", "Philanthropist"][i % 3],
            "grant_reference": f"SYN/INFRA/{i:03d}", "purpose_type": "Development" if i % 2 else "Maintenance",
            "purpose": "Synthetic smart-classroom upgrade" + (" including projectors, acoustic panels and networking" * 8 if long_text else ""),
            "sanction_date": "2026-07-15", "sanctioned_inr": "1500000.00",
            "receipts": [{"receipt_date": f"2026-0{8 + r % 2}-1{r % 9}", "amount_inr": ["500000.50", "250000", "125000.25"][r % 3],
                          "reference": "" if r % 2 else f"UTR-SYN-{i}{r:03d}"} for r in range(receipts)],
            "utilization_status": "In progress", "utilized_inr": "" if i % 2 == 0 else "320000.75",
            "utilization_remarks": "Synthetic: procurement under way.", "evidence_refs": "Sanction Letter; Receipt"}


def kra39_payload(grants=1, long_text=False, receipts=2):
    return {"activities": [kra39_grant(i + 1, long_text, receipts) for i in range(grants)]}


def kra14_registration(i=1, students=3, long_text=False):
    return {"project_title": f"Synthetic smart irrigation idea {i}" + (" with low-cost soil sensors and solar telemetry" if long_text else ""),
            "registration_id": f"SYN-YUKTHI-{i:04d}", "registration_date": "2026-09-05", "faculty_coordinator": "Test Faculty, Assistant Professor",
            "innovation_area": "Agritech (synthetic)", "status": "Registered",
            "students": [{"name": f"Test Student {i}.{s + 1} Zoë", "roll_no": f"SYN22{i:02d}{s:02d}", "programme": "" if s % 3 == 2 else "B.Tech ECE / III"}
                         for s in range(students)],
            "doc_checklist": {"Yukthi registration confirmation": "Yes", "Team details": "Yes"}, "evidence_refs": ""}


def kra14_payload(registrations=1, students=3, long_text=False):
    return {"activities": [kra14_registration(i + 1, students, long_text) for i in range(registrations)]}


def kra16_ambassador(i=1, contributions=2, long_text=False):
    return {"name": f"Test Ambassador {i} Łukasz", "member_id": f"T{2000 + i}", "category": ["Faculty", "Staff", "Student"][i % 3],
            "designation": "Assistant Professor", "appointing_body": "MoE's Innovation Cell (IIC)",
            "training": "Synthetic Innovation Ambassador foundation training", "training_completed": "2026-08-20",
            "certificate_no": "" if i % 2 == 0 else f"SYN-IA-{i:04d}", "certificate_date": "" if i % 2 == 0 else "2026-08-25",
            "contributions": [{"date": f"2026-09-{10 + c % 18:02d}", "activity": f"Synthetic ideation session {c + 1}",
                               "description": "Synthetic mentoring of student teams." + (" Synthetic follow-up detail." * 12 if long_text else "")}
                              for c in range(contributions)],
            "doc_checklist": {"Appointment / nomination letter": "Yes", "Training completion certificate": "Yes"}, "evidence_refs": ""}


def kra16_payload(ambassadors=1, contributions=2, long_text=False):
    return {"activities": [kra16_ambassador(i + 1, contributions, long_text) for i in range(ambassadors)]}


def support_record(kra, i=1, payments=2, long_text=False):
    base = {"faculty_name": f"Test Faculty {i} Zoë", "employee_id": f"T{3000 + i}",
            "payments": [{"payment_date": f"2026-09-{5 + p % 20:02d}", "amount_inr": ["3000.50", "2000", "1499.99"][p % 3],
                          "reference": f"SYN-VCH-{kra}{i:02d}{p:02d}"} for p in range(payments)],
            "doc_checklist": {"Sanction order": "Yes", "Payment / reimbursement proof": "Yes"}}
    if kra == 34:
        base.update(event_type="Conference" if i % 2 else "Workshop",
                    event_title=f"Synthetic International Conference {i}" + (" on Embedded Systems, Signal Processing and Communication" if long_text else ""),
                    organizer="Example Institute (synthetic)", venue_mode="Example City / Offline", start_date="2026-09-02", end_date="2026-09-04",
                    participation="Paper presentation", sanction_ref=f"SYN/FS/{i:03d}", sanction_date="2026-08-20", sanctioned_inr="5000.00")
    else:
        base.update(professional_body=f"Example Engineering Society {i} (synthetic)", membership_type="Annual" if i % 2 else "Life",
                    membership_no=f"SYN-M-{i:05d}", valid_from="2026-04-01", valid_to="2027-03-31" if i % 2 else "", fee_inr="5500.00",
                    sanction_ref="" if i % 2 == 0 else f"SYN/MS/{i:03d}", sanctioned_inr="5000")
    return base


def support_payload(kra, records=1, payments=2, long_text=False):
    return {"activities": [support_record(kra, i + 1, payments, long_text) for i in range(records)]}


def kra40_audit(i=1, findings=2, long_text=False):
    extra = " Synthetic extended text for layout testing." * (10 if long_text else 0)
    statuses = ["Planned", "Ongoing", "Completed"]
    return {"audit_title": f"Synthetic gender audit {i}", "reporting_basis": "Audit conducted in this period" if i == 1 else "Follow-up of an earlier audit",
            "audit_date": "2026-09-08" if i == 1 else "2025-11-20", "audit_scope": "Synthetic scope: facilities, committees, curriculum." + extra,
            "audit_team": "Test Chair\nTest Member A\nTest Member B", "audit_reference": "" if i % 2 == 0 else f"SYN/GA/{i:02d}",
            "findings": [{"ref": f"F{f + 1}", "finding": f"Synthetic finding {i}.{f + 1}." + extra,
                          "recommendation": f"Synthetic recommendation {i}.{f + 1}." + extra} for f in range(findings)],
            "actions": [{"finding_ref": f"F{f + 1}", "action": f"Synthetic action for F{f + 1}." + extra[:200], "responsible": "Test Coordinator",
                         "target_date": "" if f % 2 else "2026-12-31", "status": statuses[f % 3], "progress": "Synthetic progress note."}
                        for f in range(findings)],
            "equity_activities": [{"title": "Synthetic equity workshop", "date": "2026-09-15", "participants": 60, "outcome": "Synthetic outcome observed."}],
            "outcomes": "Synthetic outcome one", "doc_checklist": {"Gender audit report": "Yes", "Action-taken report": "No"}}


def kra40_payload(audits=1, findings=2, long_text=False):
    return {"activities": [kra40_audit(i + 1, findings, long_text) for i in range(audits)]}
