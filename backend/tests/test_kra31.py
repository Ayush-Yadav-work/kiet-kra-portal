"""KRA 31 Hackathons/ideathons organized (Phase 4 table batch). SYNTHETIC data only."""
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

REQUIRED = ("name", "event_type", "level", "date", "duration", "organizer", "teams", "participants", "institutions", "outcome")
HEADINGS = ("Sl. No.", "Academic Year", "Event ID", "Name of Hackathon/Ideathon", "Type", "Level", "Date", "Duration",
            "Organizing Department/Cell", "Co-Organizer/Partner", "No. of Teams", "No. of Participants", "No. of Institutions",
            "Industry /Expert Mentors", "Outcome")


class KRA31Tests(WorkflowMixin, PortalTestCase):
    kra = 31
    evidence = ()  # no minimum evidence agreed (D-046)
    payload = staticmethod(lambda: fx.kra31_payload(3))
    expect_text = ("Hackathons / Ideathons Organized (State Level / National Level)", "Synthetic Hack 3", "SYN-EV-02", "Ideathon", "National")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"records": [{"name": "Only a name"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in REQUIRED[1:]:
            self.assertIn(f"activities.0.records.0.{k}", fe, k)
        for k in ("event_id", "co_organizer", "mentors"):
            self.assertNotIn(f"activities.0.records.0.{k}", fe, k)

    def test_counts_level_and_type(self):
        p = fx.kra31_payload(2)
        row = p["activities"][0]["records"][0]
        row.update(teams=50, participants=40)
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps inconsistent counts
        self.assertEqual(self.errors_for(p)["activities.0.records.0.teams"], ["No. of Teams cannot exceed No. of Participants."])
        row.update(teams=10, level="International", event_type="Workshop")  # KRA counts state/national hackathons/ideathons only
        fe = self.errors_for(p, strict=False)
        self.assertEqual(set(fe), {"activities.0.records.0.level", "activities.0.records.0.event_type"})

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=31)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=31).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra31"})

    def test_one_table_all_columns_and_round_trip(self):
        p = fx.kra31_payload(4)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(html.count('<table class="records">'), 1)  # source's 2-page split repaired
        head = html.split('<table class="records">')[1].split("</thead>")[0].replace("<wbr>", "")
        for h in HEADINGS:
            self.assertIn(h, head)
        self.assertNotIn("HCK-25-01", html)  # source example IDs never seeded
