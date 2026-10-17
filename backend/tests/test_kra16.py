"""KRA 16 Innovation ambassadors — project-created format (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA16Tests(WorkflowMixin, PortalTestCase):
    kra = 16
    evidence = ()  # no minimum evidence agreed (D-059)
    payload = staticmethod(lambda: fx.kra16_payload(2))
    expect_text = ("Innovation Ambassador", "Project-created report format", "Ambassador 2 of 2", "Test Ambassador 2",
                   "Innovation Cell (IIC)", "Synthetic ideation session 2")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"name": "Only a name", "contributions": [{"activity": "x"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("member_id", "category", "designation", "appointing_body", "training"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("training_completed", "certificate_no", "certificate_date", "doc_checklist", "evidence_refs"):
            self.assertNotIn(f"activities.0.{k}", fe, k)
        self.assertIn("activities.0.contributions.0.date", fe)
        self.assertIn("activities.0.contributions.0.description", fe)

    def test_optional_certificate_and_contributions(self):
        p = copy.deepcopy(fx.kra16_payload(1))
        p["activities"][0].update(certificate_no="", certificate_date="", training_completed="", contributions=[])
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())  # newly appointed, nothing yet
        p["activities"][0]["category"] = "Alumni"
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.category": ["Choose one of the listed options."]})

    def test_multiple_ambassadors_round_trip_and_mapping(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=16)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=16).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra16"})
        p = fx.kra16_payload(3, contributions=3)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Ambassador 3 of 3", html)
        self.assertEqual(html.count("Synthetic ideation session 3"), 3)  # each ambassador's own contributions
