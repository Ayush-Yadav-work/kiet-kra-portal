"""KRA 23 Skill Development & Employability Training (bounded Phase 4 task). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA23Tests(WorkflowMixin, PortalTestCase):
    kra = 23
    evidence = ()  # no minimum evidence agreed (D-035)
    payload = staticmethod(lambda: fx.kra23_payload(programmes=2, programs=2))
    expect_text = ("Report on Skill Development &amp; Employability Training", "Synthetic Entrepreneurship Bootcamp 2",
                   "2026-27 / 3rd Year / Odd Semester", "Test Coordinator 1, Śarmā Łukasz", "Synthetic Module Batch 2",
                   "Example Incubation Agency", "The programme was organized with the following objectives:",
                   "maintained for each Skill Development Programme")

    def test_pdf_export(self):
        self.expect_text = tuple(t.replace("&amp;", "&") for t in self.expect_text)
        super().test_pdf_export()

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"programme_title": "Only a title"}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)
        for k in ("year_semester", "faculty_coordinators", "hod", "programs", "modules", "learning_outcomes",
                  "assessment_method", "min_attendance", "passing_criteria", "certificate_authority", "certificates_issued"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("programme_title", "objectives", "other_objectives", "feedback_score", "suggestions", "impact_indicators",
                  "supporting_documents", "approved_name"):
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_program_rows_rules(self):
        p = copy.deepcopy(fx.kra23_payload(programs=2))
        rows = p["activities"][0]["programs"]
        rows[0]["students_completed"] = 70  # > enrolled 60
        rows[1]["resource_agency"] = ""
        rows[1]["duration_hours"] = "2.25"
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps it as typed
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.programs.0.students_completed"], ["Students completed cannot exceed students enrolled."])
        self.assertEqual(fe["activities.0.programs.1.resource_agency"], ["Required."])
        self.assertEqual(fe["activities.0.programs.1.duration_hours"], ["Use at most 1 decimal places (values are not rounded)."])
        rows[0]["mode"] = "Blended"
        self.assertIn("activities.0.programs.0.mode", self.errors_for(p, strict=False))

    def test_multiple_records_one_submission(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload=fx.kra23_payload(programmes=3, programs=50, modules=2))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(self.save(self.a, sid, 1, payload=fx.kra23_payload(programs=51)).status_code, 400)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Programme 3 of 3", html)
        self.assertIn("Programmes in this report", html)
        self.assertEqual(self.asg.submissions.count(), 1)

    def test_objectives_and_impact_not_asserted_automatically(self):
        p = copy.deepcopy(fx.kra23_payload())
        p["activities"][0].update(objectives=[], other_objectives="", impact_indicators=[])
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("To develop an entrepreneurial mind-set among students.", html)  # only ticked objectives print
        self.assertNotIn("— observed", html)
        self.assertIn("Improvement in employability skills", html)  # source indicator list still printed
        self.assertNotIn("VAC/Add-on", html)

    def test_mapping_is_idempotent_and_keeps_targets(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=23)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=23)
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra23"})
