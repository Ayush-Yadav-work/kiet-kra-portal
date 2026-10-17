"""KRAs 34–35 faculty financial support — project-created formats (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

TITLE = {34: "Financial Support to Attend Conferences", 35: "Financial Support for Membership of Professional Bodies"}
REQUIRED = {34: ("event_type", "event_title", "organizer", "venue_mode", "start_date", "end_date", "participation", "sanction_ref",
                 "sanction_date", "sanctioned_inr"),
            35: ("professional_body", "membership_type", "membership_no", "valid_from", "fee_inr", "sanctioned_inr")}


class _Support(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-060)

    @property
    def expect_text(self):
        return (TITLE[self.kra], "Project-created report format", "Test Faculty 2", "Sanctioned amount" if self.kra == 34 else "Support sanctioned",
                "3000.50", "SYN-VCH-", "Minimum of Rs. 5000/- per year per faculty")

    def payload(self):
        return fx.support_payload(self.kra, 2)

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"faculty_name": "Only a name", "payments": [{"reference": "x"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("employee_id",) + REQUIRED[self.kra]:
            self.assertIn(f"activities.0.{k}", fe, k)
        self.assertNotIn("activities.0.payments", fe)  # a sanction may not be paid yet
        self.assertIn("activities.0.payments.0.payment_date", fe)
        self.assertIn("activities.0.payments.0.amount_inr", fe)

    def test_amounts_exact_small_payments_allowed_nothing_totalled(self):
        p = fx.support_payload(self.kra, 1, payments=3)  # 3000.50 + 2000 + 1499.99, each below Rs. 5,000
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            stored = self.detail(self.a, sid)["payload"]["activities"][0]
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual([x["amount_inr"] for x in stored["payments"]], ["3000.50", "2000", "1499.99"])
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())  # smaller payments not rejected
        self.assertNotIn("6500.49", html)  # never totalled
        self.assertIn(stored["sanctioned_inr"], html)
        bad = copy.deepcopy(p)
        bad["activities"][0]["payments"][0]["amount_inr"] = "100.005"
        self.assertEqual(self.errors_for(bad, strict=False), {})  # draft keeps it
        self.assertIn("activities.0.payments.0.amount_inr", self.errors_for(bad))  # >2 decimals rejected at submission, not rounded
        bad["activities"][0]["payments"][0]["amount_inr"] = "Rs 500"
        self.assertIn("activities.0.payments.0.amount_inr", self.errors_for(bad, strict=False))

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=self.kra)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=self.kra).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.template_version.key, a.template_version.renderer_template) for a in after},
                         {(f"kra{self.kra}", "reports/faculty_support_v1.html")})


class KRA34Tests(_Support, PortalTestCase):
    kra = 34

    def test_event_dates_order(self):
        p = copy.deepcopy(fx.support_payload(34, 1))
        p["activities"][0]["end_date"] = "2026-09-01"
        self.assertEqual(self.errors_for(p)["activities.0.end_date"], ["End date cannot be before the start date."])


class KRA35Tests(_Support, PortalTestCase):
    kra = 35

    def test_validity_and_life_membership(self):
        p = copy.deepcopy(fx.support_payload(35, 2))
        self.assertEqual(p["activities"][1]["valid_to"], "")  # life membership: no end date
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())
        p["activities"][0]["valid_to"] = "2026-01-01"
        self.assertEqual(self.errors_for(p)["activities.0.valid_to"], ["Valid-to date cannot be before the valid-from date."])
