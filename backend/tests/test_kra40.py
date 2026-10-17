"""KRA 40 Gender audit and equity measures — project-created format (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA40Tests(WorkflowMixin, PortalTestCase):
    kra = 40
    evidence = ()  # no minimum evidence agreed (D-062)
    payload = staticmethod(lambda: fx.kra40_payload(2))
    expect_text = ("Gender Audit and Measures for the Promotion of Gender Equity", "Project-created report format", "Audit 2 of 2",
                   "Follow-up of an earlier audit", "Finding F2", "Synthetic recommendation 2.2", "Ongoing", "Synthetic equity workshop")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"audit_title": "Only a title", "actions": [{"finding_ref": "F1"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("reporting_basis", "audit_date", "audit_scope", "audit_team", "outcomes"):
            self.assertIn(f"activities.0.{k}", fe, k)
        self.assertEqual(fe["activities.0.findings"], ["Add at least 1 row(s)."])
        for k in ("action", "responsible", "status", "progress"):
            self.assertIn(f"activities.0.actions.0.{k}", fe, k)
        self.assertEqual(fe["activities.0.actions.0.finding_ref"], ["Use the Ref of a finding listed for this audit."])
        for k in ("audit_reference", "equity_activities", "doc_checklist"):
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_actions_linked_to_findings_of_the_same_audit(self):
        p = copy.deepcopy(fx.kra40_payload(2))
        p["activities"][1]["actions"][0]["finding_ref"] = "F9"
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps an unmatched reference
        self.assertEqual(self.errors_for(p)["activities.1.actions.0.finding_ref"], ["Use the Ref of a finding listed for this audit."])
        sid = self.new_draft()
        good = fx.kra40_payload(1, findings=2)
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=good)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        f2 = html.split("Finding F2")[1].split("</table>")[0]
        self.assertIn("Synthetic action for F2", f2)  # printed under its own finding
        self.assertNotIn("Synthetic action for F1", f2)

    def test_follow_up_without_new_audit_and_statuses(self):
        p = copy.deepcopy(fx.kra40_payload(1))
        a = p["activities"][0]
        a.update(reporting_basis="Follow-up of an earlier audit", audit_date="2025-11-20", equity_activities=[])
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())  # earlier audit date allowed
        a["actions"][0]["status"] = "Compliant"
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.actions.0.status": ["Choose one of the listed options."]})

    def test_no_prefilled_claims_and_mapping(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=40)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=40).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra40"})
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {"payload": {"activities": [{}]}}, format="json").json()["html"]
        body = html.split("1. Gender audit")[1].lower()
        for claim in ("compliant", "successfully", "achieved"):
            self.assertNotIn(claim, body)
