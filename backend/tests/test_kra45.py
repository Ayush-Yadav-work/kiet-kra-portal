"""KRA 45 National & International flagship events (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin


class KRA45Tests(WorkflowMixin, PortalTestCase):
    kra = 45
    evidence = ()  # no minimum evidence agreed (D-055)
    payload = staticmethod(lambda: fx.kra45_payload(2))
    expect_text = ("KIET / Event Report", "Flagship Event) organized / participated", "UN SDGs Mapped with Event Team",
                   "Quality education (SDG 4)", "Resource Person(s) Details:", "Test Speaker 2.2", "Focusing", "Implementation/follow-up plan",
                   "Submission Check List", "Signature of the Faculty", "Event 2 of 2")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"event_name": "Only a name", "resource_persons": [{"city": "X"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("role", "faculty_name", "designation", "mode", "level", "sdgs", "venue", "days", "start_date", "end_date", "funded_by",
                  "participants", "brief_report", "focus", "outcome", "sdg_alignment", "feedback"):
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ("collaboration", "registration_charges", "follow_up_plan", "checklist"):
            self.assertNotIn(f"activities.0.{k}", fe, k)
        self.assertIn("activities.0.resource_persons.0.name", fe)
        self.assertIn("activities.0.resource_persons.0.institution", fe)

    def test_source_options_and_dates(self):
        p = copy.deepcopy(fx.kra45_payload(1))
        a = p["activities"][0]
        a.update(level="Regional", end_date="2026-09-01")  # source option kept selectable; eligibility not decided by the portal
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.end_date"], ["End date cannot be before the start date."])
        self.assertNotIn("activities.0.level", fe)
        a.update(end_date="2026-09-19", sdgs=["SDG 18"])
        self.assertIn("activities.0.sdgs", self.errors_for(p, strict=False))

    def test_no_mbu_wording_and_no_embedded_files(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra45_payload(1))
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("MBU", html)
        self.assertIn("Implementation/follow-up plan (if any) :", html)
        self.assertNotIn("<img", html.split("</header>")[-1].split('class="summary')[1])  # no photographs/brochures embedded
        self.assertIn("Photographs (Geo Tagged: Inauguration, Event and Valedictory)", html)

    def test_multiple_events_and_mapping(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=45)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=45).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra45"})
        p = fx.kra45_payload(3, resource_persons=3)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Event 3 of 3", html)
        self.assertEqual(html.count("Test Speaker 3."), 3)  # resource persons kept with their own event

    def test_checklist_items_are_safe_form_keys(self):
        """Checklist items become form field paths; ASCII quotes, brackets and dots would be rewritten by the form library."""
        from apps.catalogue.models import TemplateVersion
        bad = {(tv.key, i) for tv in TemplateVersion.objects.all() for s in tv.schema["sections"] for f in s["fields"]
               if f["type"] == "checklist" for i in f["items"] if set(i) & set("'\"[].")}
        self.assertEqual(bad, set())

