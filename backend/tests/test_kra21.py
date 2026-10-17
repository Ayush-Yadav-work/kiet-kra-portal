"""KRA 21 Competitive-examination training conducted — adapted format (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA21Tests(WorkflowMixin, PortalTestCase):
    kra = 21
    evidence = ()  # no minimum evidence agreed (D-056)
    payload = staticmethod(lambda: fx.kra21_payload(2))
    expect_text = ("Competitive Examination Training Conducted", "Adapted report format", "Programme 2 of 2",
                   "Synthetic GATE Preparation Programme 2", "Students who attended", "Synthetic topic 4")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"programme_title": "Only a title"}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("examination", "start_date", "end_date", "duration", "mode", "venue", "organizer", "coordinator", "trainers",
                  "target_group", "enrolled", "participated", "topics", "outcomes"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("sessions", "evidence_refs", "qualifiers"):
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_counts_dates_and_no_minimum_duration(self):
        p = copy.deepcopy(fx.kra21_payload(1))
        a = p["activities"][0]
        a.update(participated=90, end_date="2026-08-01", duration="2 hours")  # short programmes allowed
        self.assertEqual(self.errors_for(p, strict=False), {})
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.participated"], ["Students participated cannot exceed students enrolled."])
        self.assertEqual(fe["activities.0.end_date"], ["End date cannot be before the start date."])
        self.assertNotIn("activities.0.duration", fe)

    def test_qualifiers_optional_and_separate_from_training(self):
        p = fx.kra21_payload(1)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 1 training programme")
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("Students qualifying examinations", html)  # optional table omitted when empty
        p = fx.kra21_payload(1, qualifiers=3)
        p["activities"][0]["qualifiers"][1]["level"] = ""
        self.assertEqual(self.errors_for(p)["activities.0.qualifiers.1.level"], ["Required."])  # rows that exist are complete
        p["activities"][0]["qualifiers"][1]["level"] = "State"
        with frozen(ist(2026, 10, 1)):
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {"payload": p}, format="json").json()["html"]
        self.assertIn("supporting information only", html)
        self.assertIn("not the KRA 21 achievement", html)
        self.assertIn("Synthetic: 1 training programme", html)  # achievement as entered, never derived from qualifiers

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=21)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=21).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra21"})
