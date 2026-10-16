"""KRAs 25–26 sports and cultural awards (Phase 4 awards batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

HEADINGS = ("Sl. No.", "Name of the student", "Name of the event", "Date of the event", "Team / Individual",
            "University / state / National/ International", "Position secured", "Name of the Organising Institution")


class _Awards(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-051)
    expect_text = ("(award for a team event should be counted as one)", "Test Student 2.4", "Gold medal", "Example University (synthetic)")

    def payload(self):
        return fx.award_payload(self.kra, 4)

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"records": [{"event": "Only an event"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("student_names", "event_date", "participation", "level", "position", "organiser"):
            self.assertIn(f"activities.0.records.0.{k}", fe, k)

    def test_team_award_is_one_record(self):
        p = fx.award_payload(self.kra, 2)
        team = p["activities"][0]["records"][1]
        self.assertEqual((team["participation"], team["student_names"].count("\n")), ("Team", 3))
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: as entered")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        body = html.split("</thead>")[1].split("</table>")[0]
        self.assertEqual(body.count("<tr>"), 2)  # one row per award, never one per team member
        self.assertIn("Test Student 2.1<br>Test Student 2.2<br>Test Student 2.3<br>Test Student 2.4", body)
        self.assertEqual(body.count(team["event"]), 1)
        self.assertIn("Synthetic: as entered", html)  # achievement as entered, not computed

    def test_source_headings_and_level_wording(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.award_payload(self.kra, 4))
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        head = html.split('<table class="records">')[1].split("</thead>")[0].replace("<wbr>", "")
        for h in HEADINGS:
            self.assertIn(h, head)
        self.assertIn("University (inter-university)", html)
        p = copy.deepcopy(fx.award_payload(self.kra, 1))
        p["activities"][0]["records"][0]["level"] = "College"  # not in the source/workbook levels
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.records.0.level": ["Choose one of the listed options."]})

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=self.kra)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=self.kra).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.template_version.key, a.template_version.renderer_template) for a in after},
                         {(f"kra{self.kra}", "reports/records_sheet_v1.html")})


class KRA25Tests(_Awards, PortalTestCase):
    kra = 25


class KRA26Tests(_Awards, PortalTestCase):
    kra = 26


class AwardSeparationTests(PortalTestCase):
    def asg(self, n):
        return AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27")

    def test_sports_and_cultural_kept_separate(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sids = {n: self.open_draft(a, self.asg(n), self.p2) for n in (25, 26)}
            self.assertNotEqual(sids[25], sids[26])
            self.save(a, sids[25], 0, payload=fx.award_payload(25, 2), achievement_text="KRA 25: synthetic")
            d25, d26 = self.detail(a, sids[25]), self.detail(a, sids[26])
        self.assertEqual(len(d25["payload"]["activities"][0]["records"]), 2)
        self.assertNotIn("records", str(d26["payload"]))  # nothing copied to KRA 26
        self.assertEqual((d25["achievement_text"], d26["achievement_text"]), ("KRA 25: synthetic", ""))
        self.assertNotEqual(d25["assignment"]["target_text"], d26["assignment"]["target_text"])  # 9 vs 10 in the workbook
