"""KRA 38 FDPs/MDPs attended by faculty (Phase 4 table batch). SYNTHETIC data only."""
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA38Tests(WorkflowMixin, PortalTestCase):
    kra = 38
    evidence = ()  # no minimum evidence agreed (D-047)
    payload = staticmethod(lambda: fx.kra38_payload(3))
    expect_text = ("Percentage of teachers undergoing online/ face-to-face Faculty Development Programmes (FDPs)/",
                   "Test Faculty 3", "Short Term Course", "Name of the Organising Institution")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"records": [{"faculty_name": "Only a name"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("programme_type", "duration_days", "start_date", "end_date", "institution"):
            self.assertIn(f"activities.0.records.0.{k}", fe, k)

    def test_dates_and_duration(self):
        p = fx.kra38_payload(1)
        row = p["activities"][0]["records"][0]
        row.update(start_date="2026-08-10", end_date="2026-08-01", duration_days=0)
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps them
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.records.0.end_date"], ["End date cannot be before the start date."])
        self.assertEqual(fe["activities.0.records.0.duration_days"], ["Must be between 1 and 365."])
        row.update(end_date="2026-08-12", duration_days=30)  # duration is as entered, not computed from the dates
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())

    def test_mapping_idempotent_targets_unchanged_and_separate_from_36_37(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=38)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=38).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra38"})
        self.assertEqual({a.template_version.key for a in AnnualAssignment.objects.filter(kra__number=37)}, {"kra37"})

    def test_one_portrait_table_round_trip(self):
        p = fx.kra38_payload(5)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 5 faculty attended")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(html.count('<table class="records">'), 1)
        head = html.split('<table class="records">')[1].split("</thead>")[0].replace("<wbr>", "")
        for h in ("Name of the Faculty", "Type of Program (Professional Development Programmes", "Duration (in No. of days)",
                  "Start Date", "End Date", "Name of the Organising Institution"):
            self.assertIn(h, head)
        self.assertNotIn("Academic Year</th>", head)  # source has no year/department columns
