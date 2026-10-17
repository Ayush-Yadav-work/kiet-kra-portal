"""KRA 39 Infrastructure grants received — adapted format (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA39Tests(WorkflowMixin, PortalTestCase):
    kra = 39
    evidence = ()  # no minimum evidence agreed (D-057)
    payload = staticmethod(lambda: fx.kra39_payload(2))
    expect_text = ("Grants Received for Development and Maintenance of Infrastructure", "Adapted report format", "Grant 2 of 2",
                   "Sanctioned amount (INR)", "500000.50", "Amount utilized so far (INR)", "INR in Lakhs")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"funding_body": "Only a body", "receipts": [{"reference": "x"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("body_type", "grant_reference", "purpose_type", "purpose", "sanction_date", "sanctioned_inr", "utilization_status"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("utilized_inr", "utilization_remarks", "evidence_refs"):
            self.assertNotIn(f"activities.0.{k}", fe, k)
        self.assertIn("activities.0.receipts.0.receipt_date", fe)
        self.assertIn("activities.0.receipts.0.amount_inr", fe)

    def test_amounts_exact_in_inr(self):
        p = fx.kra39_payload(1)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            stored = self.detail(self.a, sid)["payload"]["activities"][0]
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual((stored["sanctioned_inr"], [r["amount_inr"] for r in stored["receipts"]], stored["utilized_inr"]),
                         ("1500000.00", ["500000.50", "250000"], "320000.75"))
        self.assertNotIn("750000", html)  # receipts never totalled
        self.assertNotIn("lakh", html.split("Grant details")[1].lower())  # no conversion to lakhs in the grant sections
        bad = copy.deepcopy(p)
        bad["activities"][0]["sanctioned_inr"] = "1500000.555"
        self.assertEqual(self.errors_for(bad, strict=False), {})  # draft keeps a well-formed number
        self.assertIn("activities.0.sanctioned_inr", self.errors_for(bad))  # >2 decimals rejected at submission, never rounded
        bad["activities"][0]["sanctioned_inr"] = "15 lakh"
        self.assertIn("activities.0.sanctioned_inr", self.errors_for(bad, strict=False))  # units are not typed into amounts

    def test_sanctioned_received_utilized_kept_distinct(self):
        p = copy.deepcopy(fx.kra39_payload(1, receipts=0))
        p["activities"][0].update(utilized_inr="", utilization_status="Not started")
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())  # sanctioned without receipts is allowed
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("No amount received recorded for this grant.", html)
        self.assertIn("1500000.00", html)

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=39)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=39).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)  # e.g. "1050119" kept as text, not rescaled
        self.assertEqual({a.template_version.key for a in after}, {"kra39"})
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra39_payload(1))
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn(self.asg.target_text, html)
