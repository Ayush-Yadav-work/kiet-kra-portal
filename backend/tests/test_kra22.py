"""KRA 22 Career counselling activities (Phase 4 table batch). SYNTHETIC data only."""
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

COLUMNS = ("date", "title", "activity_type", "career_domain", "target_programme", "resource_person", "organization", "duration",
           "students", "faculty", "outcome")
HEADINGS = ("Sl. No.", "Academic Year", "Date", "Title of Activity", "Type of Activity", "Career Domain", "Target Programme/Branch",
            "Resource Person/Counsellor", "Organization", "Duration", "No. of Students", "No. of Faculty", "Outcome")


class KRA22Tests(WorkflowMixin, PortalTestCase):
    kra = 22
    evidence = ()  # no minimum evidence agreed (D-045)
    payload = staticmethod(lambda: fx.kra22_payload(3))
    expect_text = ("Career Counselling Activities Conducted", "Synthetic career session 3", "Test Counsellor 2", "Higher Studies", "Expert Talk")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"records": [{"title": "Only a title"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in COLUMNS:
            if k != "title":
                self.assertIn(f"activities.0.records.0.{k}", fe, k)

    def test_counts_and_free_text_types(self):
        p = fx.kra22_payload(2)
        row = p["activities"][0]["records"][0]
        row.update(students=-1, faculty="3", activity_type="Panel discussion (synthetic)")  # type not limited to the source samples
        fe = self.errors_for(p, strict=False)
        self.assertEqual(fe, {"activities.0.records.0.faculty": ["Must be a whole number."]})  # malformed blocks the draft
        row["faculty"] = 0
        self.assertEqual(self.errors_for(p)["activities.0.records.0.students"], ["Must be between 0 and 100000."])

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=22)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=22).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra22"})

    def test_one_table_all_columns_and_round_trip(self):
        p = fx.kra22_payload(4)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(html.count('<table class="records">'), 1)  # source's 2-page split repaired
        head = html.split('<table class="records">')[1].split("</thead>")[0].replace("<wbr>", "")
        for h in HEADINGS:
            self.assertIn(h, head)
        body = html.split("</thead>")[1].split("</table>")[0]
        self.assertEqual(body.count("<tr>"), 4)
        self.assertIn("02 Sep 2026", body)
        self.assertNotIn("Total", body)  # no automatic totals
