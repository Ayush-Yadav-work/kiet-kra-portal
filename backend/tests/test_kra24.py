"""KRA 24 Placement / higher education (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA24Tests(WorkflowMixin, PortalTestCase):
    kra = 24
    evidence = ()  # no minimum evidence agreed (D-049)
    payload = staticmethod(lambda: fx.kra24_payload(6))
    expect_text = ("Percentage of placement of outgoing students and students progressing to higher education", "Test Graduate 6",
                   "Example Employer 2 Pvt Ltd (synthetic)", "INR 725000.50", "M.Tech VLSI Design", "not counted as placements")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        rows = [{"student_name": "Placed", "category": "Placement"}, {"student_name": "Higher", "category": "Higher Education"}]
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"records": rows}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        row0 = {k.split(".")[-1] for k in fe if k.startswith("activities.0.records.0.")}
        row1 = {k.split(".")[-1] for k in fe if k.startswith("activities.0.records.1.")}
        self.assertEqual(row0, {"contact", "programme", "employer", "package_inr"})  # employer contact optional
        self.assertEqual(row1, {"contact", "programme", "institution", "admitted_programme"})

    def test_category_switch_keeps_values_but_excludes_them(self):
        p = copy.deepcopy(fx.kra24_payload(1))
        row = p["activities"][0]["records"][0]
        self.assertEqual(row["category"], "Placement")
        row.update(category="Higher Education", institution="Example University X (synthetic)", admitted_programme="M.Tech X")
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())  # kept placement values not validated
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            stored = self.detail(self.a, sid)["payload"]["activities"][0]["records"][0]
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual((stored["employer"], stored["package_inr"]), (row["employer"], row["package_inr"]))  # never erased
        self.assertNotIn(row["employer"], html)
        self.assertNotIn("INR 650000", html)
        self.assertIn("Example University X (synthetic)", html)
        row["package_inr"] = "12.345"  # invalid but inactive: still ignored
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())
        row["category"] = "Placement"  # active again: validated
        self.assertIn("activities.0.records.0.package_inr", self.errors_for(p))

    def test_package_kept_exactly(self):
        p = fx.kra24_payload(2)
        p["activities"][0]["records"][0]["package_inr"] = "600000.00"
        p["activities"][0]["records"][1]["package_inr"] = "725000.50"
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            got = self.detail(self.a, sid)["payload"]["activities"][0]["records"]
        self.assertEqual([r["package_inr"] for r in got], ["600000.00", "725000.50"])  # decimals as entered, never rounded
        bad = copy.deepcopy(p)
        bad["activities"][0]["records"][0]["package_inr"] = "-1"
        self.assertIn("activities.0.records.0.package_inr", self.errors_for(bad))

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=24)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=24).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra24"})

    def test_no_counts_or_percentages(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra24_payload(6), achievement_text="Synthetic: as entered")
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        body = html.split("</thead>")[1].split("</table>")[0]
        self.assertNotIn("%", body)
        self.assertEqual(body.count("<tr>"), 6)
        self.assertIn("Synthetic: as entered", html)
