"""KRA 14 Yukthi registrations — project-created format (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA14Tests(WorkflowMixin, PortalTestCase):
    kra = 14
    evidence = ()  # no minimum evidence agreed (D-058)
    payload = staticmethod(lambda: fx.kra14_payload(2))
    expect_text = ("Yukthi Registration", "Project-created report format", "Registration 2 of 2", "SYN-YUKTHI-0002",
                   "Test Student 2.3", "Agritech (synthetic)")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"project_title": "Only a title", "students": [{"programme": "x"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("registration_id", "registration_date", "faculty_coordinator", "innovation_area", "status"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("doc_checklist", "evidence_refs"):
            self.assertNotIn(f"activities.0.{k}", fe, k)
        self.assertIn("activities.0.students.0.name", fe)
        self.assertIn("activities.0.students.0.roll_no", fe)
        self.assertNotIn("activities.0.students.0.programme", fe)

    def test_team_required_with_faculty(self):
        p = copy.deepcopy(fx.kra14_payload(1))
        p["activities"][0]["students"] = []
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps a registration without students
        self.assertEqual(self.errors_for(p)["activities.0.students"], ["Add at least 1 row(s)."])  # "Faculty with Students"

    def test_multiple_registrations_round_trip_and_mapping(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=14)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=14).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra14"})
        p = fx.kra14_payload(3, students=4)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Registration 3 of 3", html)
        self.assertEqual(html.count("Test Student 3."), 4)  # each team stays with its registration
        self.assertIn(self.asg.target_text, html)
