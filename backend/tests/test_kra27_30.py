"""KRAs 27–30 event-organizing reports (Phase 4 events batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

TITLES = {27: "Sports Competition / Event Report", 28: "Cultural Competition / Event Report",
          29: "Technical / Academic Fest Report", 30: "Club / Forum Activity Report"}
SPECIFIC = {27: ("sport",), 28: ("cultural_activity",), 29: ("theme",), 30: ("club_name", "semester")}
COMMON = ("event_title", "category", "start_date", "end_date", "venue", "mode", "organizer", "coordinators", "target_audience",
          "participants_students", "participants_faculty", "participants_external", "objectives", "description", "outcomes", "feedback")
OPTIONAL = ("student_coordinators", "collaborators", "resource_persons", "institutions", "doc_checklist", "reported_by", "report_date")


class _Events(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-052)

    @property
    def expect_text(self):
        return (TITLES[self.kra], "Portal report format", f"Synthetic KRA {self.kra} event 2", "Event 2 of 2", "Documentary evidence",
                "Test Judge 2")

    def payload(self):
        return fx.event_payload(self.kra, 2)

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"event_title": "Only a title"}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in COMMON[1:] + SPECIFIC[self.kra]:
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in OPTIONAL:
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_dates_counts_and_category(self):
        p = copy.deepcopy(fx.event_payload(self.kra, 1, long_text=True))
        a = p["activities"][0]
        a.update(start_date="2026-09-20", end_date="2026-09-10", participants_students=-1)
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps them
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.end_date"], ["End date cannot be before the start date."])
        self.assertIn("activities.0.participants_students", fe)
        a.update(end_date="2026-09-21", participants_students=0, category="Award won")  # categories stay within the workbook activity
        self.assertEqual(set(self.errors_for(p, strict=False)), {"activities.0.category"})

    def test_kra_specific_fields_only(self):
        other = {27: "theme", 28: "sport", 29: "club_name", 30: "cultural_activity"}[self.kra]
        p = copy.deepcopy(fx.event_payload(self.kra, 1))
        p["activities"][0][other] = "Borrowed field"
        self.assertEqual(self.errors_for(p, strict=False), {f"activities.0.{other}": ["Unknown field."]})

    def test_multiple_events_one_submission_no_prefilled_claims(self):
        p = fx.event_payload(self.kra, 3)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: as entered")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
            empty = self.a.post(f"/api/v1/submissions/{sid}/preview/", {"payload": {"activities": [{}]}}, format="json").json()["html"]
        self.assertIn("Event 3 of 3", html)
        self.assertEqual(self.asg.submissions.count(), 1)
        self.assertNotIn("successfully", empty.lower())  # no prefilled claims of success
        self.assertEqual(empty.count("Not entered"), 4)

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=self.kra)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=self.kra).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.template_version.key, a.template_version.renderer_template) for a in after},
                         {(f"kra{self.kra}", "reports/event_family_v1.html")})


class KRA27Tests(_Events, PortalTestCase):
    kra = 27


class KRA28Tests(_Events, PortalTestCase):
    kra = 28


class KRA29Tests(_Events, PortalTestCase):
    kra = 29


class KRA30Tests(_Events, PortalTestCase):
    kra = 30

    def test_per_club_per_semester_target_shown_as_assigned(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.event_payload(30, 1))
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn(self.asg.target_text, html)  # e.g. "01 activity per club per sem", not converted
        self.assertIn("Synthetic Robotics Club", html)


class EventSeparationTests(PortalTestCase):
    def asg(self, n):
        return AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27")

    def test_four_kras_keep_separate_records(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sids = {n: self.open_draft(a, self.asg(n), self.p2) for n in (27, 28, 29, 30)}
            self.assertEqual(len(set(sids.values())), 4)
            self.save(a, sids[29], 0, payload=fx.event_payload(29, 2), achievement_text="KRA 29: synthetic")
            docs = {n: self.detail(a, sids[n]) for n in sids}
        self.assertEqual(len(docs[29]["payload"]["activities"]), 2)
        for n in (27, 28, 30):
            self.assertNotIn("event_title", str(docs[n]["payload"]))
            self.assertEqual(docs[n]["achievement_text"], "")
            self.assertEqual(docs[n]["assignment"]["target_text"], self.asg(n).target_text)
