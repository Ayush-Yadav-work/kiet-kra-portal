"""KRA 44 BOOT camps and peer learning (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA44Tests(WorkflowMixin, PortalTestCase):
    kra = 44
    evidence = ()  # no minimum evidence agreed (D-054)
    payload = staticmethod(lambda: fx.kra44_payload(2))
    expect_text = ("KIET Deemed to be University, Ghaziabad", "EVENT REPORT- BOOT Camp", "Peer Learning Activity", "1. General Information",
                   "2. Introduction", "3. Objectives", "4. Activity Details", "5. BOOT Camp / Peer Learning Structure", "Phase VI",
                   "6. Documentary Evidence", "Activity 2 of 2", "Head of Department/Dean")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"activity_name": "Only a name"}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("activity_type", "theme", "start_date", "end_date", "duration", "venue", "mode", "organizer", "faculty_coordinator",
                  "introduction", "target_group", "programme", "semester", "registered", "participated", "student_mentors",
                  "faculty_mentors", "sessions"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("activity_id", "student_coordinators", "mentors", "objectives", "time", "phase_1", "doc_checklist", "hod_name"):
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_counts_and_dates(self):
        p = copy.deepcopy(fx.kra44_payload(1))
        a = p["activities"][0]
        a.update(participated=70, registered=60, sessions=0, end_date="2026-09-01")
        self.assertEqual(self.errors_for(p, strict=False), {})
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.participated"], ["Students participated cannot exceed students registered."])
        self.assertIn("activities.0.sessions", fe)
        self.assertEqual(fe["activities.0.end_date"], ["End date cannot be before the start date."])

    def test_source_text_is_guidance_not_prefill(self):
        sid = self.new_draft()
        p = copy.deepcopy(fx.kra44_payload(1))
        p["activities"][0].update(introduction="", objectives=[], phase_1="", phase_4="")
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("experiential, collaborative and skill-oriented", html)  # source introduction not asserted
        self.assertNotIn("Students were introduced to the objectives", html)  # source phase text not asserted
        self.assertEqual(html.count("Not described"), 2)
        self.assertNotIn("To promote experiential and hands-on learning.", html)

    def test_multiple_activities_and_mapping(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=44)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=44).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra44"})
        p = fx.kra44_payload(3)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Activity 3 of 3", html)
        self.assertEqual(self.asg.submissions.count(), 1)
