"""KRA 11 Bridge Courses (bounded Phase 4 task). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA11Tests(WorkflowMixin, PortalTestCase):
    kra = 11
    evidence = ()  # no minimum evidence agreed (D-034)
    payload = staticmethod(lambda: fx.kra11_payload(courses=2, modules=4))
    expect_text = ("Report on Bridge Courses Conducted", "Synthetic Bridge Course 2: Mathematics Foundations",
                   "2026-27 / 1st Year / Odd Semester", "Test Coordinator 1, Zoë Ñúñez", "Synthetic topic 4",
                   "Overall Feedback Score:", "4.35", "maintained for each Bridge Course")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload={"activities": [{}]})
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)  # no invented evidence minimum
        for k in ("year_semester", "faculty_coordinators", "hod", "course_name", "duration_hours", "mode", "resource_person",
                  "students_enrolled", "students_completed", "modules", "learning_outcomes", "assessment_method",
                  "min_attendance", "passing_criteria", "certificate_authority", "certificates_issued"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("feedback_score", "suggestions", "impact_indicators", "supporting_documents", "prepared_name",
                  "approved_date", "additional_objectives"):
            self.assertNotIn(f"activities.0.{k}", fe, k)  # optional per D-034

    def test_mapping_is_idempotent_and_keeps_targets(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=11)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=11)
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra11"})
        self.assertEqual(after.count(), 13)

    def test_course_rules(self):
        p = copy.deepcopy(fx.kra11_payload(courses=1))
        c = p["activities"][0]
        c["students_completed"], c["students_enrolled"] = 130, 120
        c["duration_hours"] = "30.25"
        c["modules"][0]["hours"] = "abc"
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.modules.0.hours": ["Must be a number."]})
        c["modules"][0]["hours"] = "7.5"
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.students_completed"], ["Students completed cannot exceed students enrolled."])
        self.assertEqual(fe["activities.0.duration_hours"], ["Use at most 1 decimal places (values are not rounded)."])
        c["modules"] = []
        self.assertEqual(self.errors_for(p)["activities.0.modules"], ["Add at least 1 row(s)."])

    def test_multiple_courses_and_cap(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload=fx.kra11_payload(courses=20, modules=2))
            self.assertEqual(r.status_code, 200)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
            self.assertIn("Course 20 of 20", html)
            self.assertIn("Courses in this report", html)
            r = self.save(self.a, sid, 1, payload=fx.kra11_payload(courses=21, modules=1))
            self.assertEqual(r.status_code, 400)

    def test_source_wording_and_approved_correction(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra11_payload(courses=1))
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        for t in ("Objectives of Bridge Courses - The major objectives of the Bridge Courses are:",
                  "To bridge the gap in students’ prerequisite knowledge and skills.", "Suggested Impact Indicators",
                  "Participation in competitions/hackathons", "Prepared By:", "Approved By:", "Signature:"):
            self.assertIn(t, html)
        self.assertNotIn("VAC/Add-on", html)  # copied wording corrected (D-034)
        self.assertIn("Synthetic extra objective", html)
