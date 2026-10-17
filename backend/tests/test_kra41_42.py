"""KRAs 41–42 inclusive-environment and constitutional-awareness activities (project-created, Phase 4). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

TITLES = {41: "Inclusive Environment Activity Report", 42: "Constitutional Obligations Sensitization Activity Report"}
SPECIFIC = {41: ("inclusion_themes", "theme_details"), 42: ("constitutional_aspects", "topics")}
COMMON = ("start_date", "end_date", "venue", "mode", "organizer", "coordinators", "target_audience", "participants_students",
          "participants_faculty", "participants_external", "objectives", "description", "outcomes", "feedback")


class _Activities(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-063)

    @property
    def expect_text(self):
        return (TITLES[self.kra], "Portal report format", f"Synthetic KRA {self.kra} event 2", "Event 2 of 2", "Documentary evidence")

    def payload(self):
        return fx.event_payload(self.kra, 2)

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"event_title": "Only a title"}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in COMMON + SPECIFIC[self.kra]:
            self.assertIn(f"activities.0.{k}", fe, k)
        self.assertNotIn("activities.0.category", fe)  # no category select for 41/42
        p = copy.deepcopy(fx.event_payload(self.kra, 1))
        p["activities"][0]["category"] = "Sports event"
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.category": ["Unknown field."]})

    def test_workbook_dimensions_only(self):
        p = copy.deepcopy(fx.event_payload(self.kra, 1))
        field = SPECIFIC[self.kra][0]
        p["activities"][0][field] = ["Religious freedom"]  # outside the workbook wording
        self.assertEqual(self.errors_for(p, strict=False), {f"activities.0.{field}": ["Choose from the listed options."]})
        p["activities"][0][field] = []
        self.assertEqual(self.errors_for(p)[f"activities.0.{field}"], ["Select at least one."])

    def test_multiple_activities_and_mapping(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=self.kra)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=self.kra).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)  # "4 Per Year" unchanged
        self.assertEqual({(a.template_version.key, a.template_version.renderer_template) for a in after},
                         {(f"kra{self.kra}", "reports/event_family_v1.html")})
        p = fx.event_payload(self.kra, 4)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: as entered")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Event 4 of 4", html)
        self.assertEqual(self.asg.submissions.count(), 1)


class KRA41Tests(_Activities, PortalTestCase):
    kra = 41


class KRA42Tests(_Activities, PortalTestCase):
    kra = 42
