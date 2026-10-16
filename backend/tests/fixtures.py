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
