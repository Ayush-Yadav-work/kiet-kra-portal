"""KRA 12 Awards and recognition for research/innovations (Phase 4 awards batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA12Tests(WorkflowMixin, PortalTestCase):
    kra = 12
    evidence = ()  # no minimum evidence agreed (D-050)
    payload = staticmethod(lambda: fx.kra12_payload(3))
    expect_text = ("Awards and Recognition for Research/Innovations by Faculty/Students/Dept./Institute", "School/Department:",
                   "Academic Session:", "Reporting Period:", "Coordinator (if any):", "Complete Detail of Award/ Recognition",
                   "Award 3 of 3", "Example Science Council (synthetic)", "Prepared By:", "Verified By:", "Approved By:")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"awards": [{"award_title": "Only a title"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("recipients", "recipient_category", "awarding_body", "award_date", "contribution", "description"):
            self.assertIn(f"activities.0.awards.0.{k}", fe, k)
        for k in ("activities.0.coordinator", "activities.0.report_date", "activities.0.awards.0.level"):
            self.assertNotIn(k, fe)
        p = {"activities": [{"awards": []}]}
        self.assertEqual(self.errors_for(p)["activities.0.awards"], ["Add at least 1 row(s)."])

    def test_shared_award_is_one_record_with_all_recipients(self):
        p = fx.kra12_payload(2)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 2 awards")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(html.count("Award 2 of 2"), 1)
        self.assertIn("Test Faculty A<br>Test Student B Zoë<br>Test Student C", html)
        self.assertEqual(html.count("Synthetic Innovation Award 2"), 2)  # heading + title row, not one per recipient
        with frozen(ist(2026, 10, 1)):  # unsaved preview of 3 awards: award 3 has no level
            html3 = self.a.post(f"/api/v1/submissions/{sid}/preview/", {"payload": fx.kra12_payload(3)}, format="json").json()["html"]
        self.assertIn("<td>Level</td><td>Not applicable</td>", html3)

    def test_signature_labels_are_not_roles(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra12_payload(1))
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        sign = html.split('class="k11-sign awd-sign"')[1].split("</table>")[0]
        self.assertNotIn("Verified by VC", sign)  # printed labels stay blank lines; verification is the server label
        self.assertIn("Verification: Pending approval", html)

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=12)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=12).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra12"})

    def test_category_limited_to_workbook_recipients(self):
        p = copy.deepcopy(fx.kra12_payload(1))
        p["activities"][0]["awards"][0]["recipient_category"] = "Alumni"
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.awards.0.recipient_category": ["Choose one of the listed options."]})
