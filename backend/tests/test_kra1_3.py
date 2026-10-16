"""KRAs 1-3 course-report family (bounded Phase 4 task). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from apps.reports.families import course_family_schema
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

REQUIRED_COMMON = ("year_semester", "faculty_coordinators", "hod", "course_name", "duration_hours", "mode", "resource_agency",
                   "modules", "learning_outcomes", "assessment_method", "min_attendance", "passing_criteria",
                   "certificate_authority", "certificates_issued")
OPTIONAL_COMMON = ("objectives", "other_objectives", "feedback_score", "suggestions", "impact_indicators",
                   "supporting_documents", "prepared_name", "approved_date")


class FamilyMixin(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-036)
    required_extra = ()
    optional_extra = ()

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"course_name": "Only a name"}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)
        for k in REQUIRED_COMMON + self.required_extra:
            if k != "course_name":
                self.assertIn(f"activities.0.{k}", fe, k)
        for k in OPTIONAL_COMMON + self.optional_extra:
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_stored_schema_matches_family_definition(self):
        tv = self.asg.template_version
        self.assertEqual(tv.schema, course_family_schema(self.kra))
        self.assertEqual(tv.renderer_template, "reports/course_family_v1.html")


class KRA1Tests(FamilyMixin, PortalTestCase):
    kra = 1
    payload = staticmethod(lambda: fx.kra13_payload(1, courses=2))
    expect_text = ("REPORT ON VALUE ADDED COURSES, ADD-ON COURSES AND MOOCs", "Detail of New Courses", "Course Code", "TST101",
                   "Approval reference: Synthetic BoS item 4.2", "Objectives of New Courses", "maintained for each New Course")
    required_extra = ("course_code",)
    optional_extra = ("approval_ref", "students_enrolled", "students_completed")


class KRA2Tests(FamilyMixin, PortalTestCase):
    kra = 2
    payload = staticmethod(lambda: fx.kra13_payload(2, courses=2))
    expect_text = ("Detail of Value Added Courses", "Objectives of Value Added Courses - The major objectives of the Value Added Courses are:",
                   "Synthetic KRA2 Course 2", "maintained for each VAC/Add-on Course")
    required_extra = ("students_enrolled", "students_completed")


class KRA3Tests(FamilyMixin, PortalTestCase):
    kra = 3
    payload = staticmethod(lambda: fx.kra13_payload(3, courses=2))
    expect_text = ("Detail of Online Courses (MOOCs)", "Platform / Certifying Body", "SWAYAM", "maintained for each Online Course (MOOC)")
    required_extra = ("platform", "students_enrolled", "students_completed")


class FamilySeparationTests(PortalTestCase):
    def asg(self, n):
        return AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27")

    def test_mappings_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number__in=(1, 2, 3))}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number__in=(1, 2, 3)).select_related("template_version", "kra")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.kra.number, a.template_version.key) for a in after}, {(1, "kra1"), (2, "kra2"), (3, "kra3")})
        self.assertEqual(after.count(), 39)

    def test_drafts_achievements_and_evidence_stay_separate(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sids = {n: self.open_draft(a, self.asg(n), self.p2) for n in (1, 2, 3)}
            self.assertEqual(len(set(sids.values())), 3)  # three separate submissions, never combined
            for n in (1, 2, 3):
                r = self.save(a, sids[n], 0, payload=fx.kra13_payload(n), achievement_text=f"KRA {n}: synthetic")
                self.assertEqual(r.status_code, 200, r.content)
            a.post(f"/api/v1/submissions/{sids[2]}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/x",
                   "category": "Attendance records", "label": "KRA2 only"}, format="json")
            for n in (1, 2, 3):
                d = self.detail(a, sids[n])
                self.assertEqual(d["achievement_text"], f"KRA {n}: synthetic")
                self.assertEqual(d["payload"]["activities"][0]["course_name"], f"Synthetic KRA{n} Course 1")
                self.assertEqual(d["assignment"]["target_text"], self.asg(n).target_text)
                ev = a.get(f"/api/v1/submissions/{sids[n]}/evidence/").json()["results"]
                self.assertEqual(len(ev), 1 if n == 2 else 0)
                self.assertEqual([e["display_status"] for e in d["period_entries"] if e["period"]["index"] == 2], ["DRAFT"])
            # Submitting KRA 2 leaves KRA 1 and 3 as drafts.
            v = self.detail(a, sids[2])["edit_version"]
            self.assertEqual(a.post(f"/api/v1/submissions/{sids[2]}/submit/", {"edit_version": v}, format="json").status_code, 200)
            self.assertEqual([self.detail(a, sids[n])["status"] for n in (1, 2, 3)], ["DRAFT", "SUBMITTED", "DRAFT"])

    def test_fields_are_kra_specific(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid2 = self.open_draft(a, self.asg(2), self.p2)
            p = copy.deepcopy(fx.kra13_payload(2))
            p["activities"][0]["platform"] = "SWAYAM"  # KRA 3 field on KRA 2
            r = self.save(a, sid2, 0, payload=p)
            self.assertEqual(r.status_code, 400)
            self.assertIn("activities.0.platform", r.json()["field_errors"])
            sid1 = self.open_draft(a, self.asg(1), self.p2)
            p = copy.deepcopy(fx.kra13_payload(1))
            p["activities"][0].update(students_enrolled="", students_completed="")
            self.save(a, sid1, 0, payload=p)
            fe = a.post(f"/api/v1/submissions/{sid1}/validate/").json()["field_errors"]
            self.assertNotIn("activities.0.students_enrolled", fe)  # optional for new courses
            p["activities"][0].update(students_enrolled=10, students_completed=12)
            self.save(a, sid1, 1, payload=p)
            fe = a.post(f"/api/v1/submissions/{sid1}/validate/").json()["field_errors"]
            self.assertEqual(fe["activities.0.students_completed"], ["Students completed cannot exceed students enrolled."])

    def test_objectives_only_when_ticked(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg(2), self.p2)
            p = copy.deepcopy(fx.kra13_payload(2))
            p["activities"][0].update(objectives=[], other_objectives="", impact_indicators=[])
            self.save(a, sid, 0, payload=p)
            html = a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("To supplement the knowledge acquired through the regular curriculum.", html)
        self.assertNotIn("— observed", html)
        self.assertIn("Value Added Courses (VACs), Add-on Courses and Massive Open Online Courses (MOOCs)", html)  # fixed intro
