"""KRA 18 Functional MoU activity reports (Phase 4 industry-collaboration batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

MOU_REQUIRED = ("org_name", "org_type", "mou_ref", "signing_date", "validity", "coord_institution", "coord_organization")
ACTIVITY_REQUIRED = ("title", "activity_date", "duration", "activity_type", "venue", "mode", "target_participants", "programme_branch",
                     "participants", "resource_person", "rp_designation", "key_topics", "objective", "description", "outcomes")


class KRA18Tests(WorkflowMixin, PortalTestCase):
    kra = 18
    evidence = ()  # no minimum evidence agreed (D-040)
    payload = staticmethod(lambda: fx.kra18_payload(2, 2))
    expect_text = ("REPORT ON Signed Functional MoU with Industry / Research Organization", "Example Research Organization 2 (synthetic)",
                   "SYN/MOU/002", "Synthetic MoU activity 2.2", "Evidence Maintained", "Outcome/Impact Evidence")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"org_name": "Only a partner", "mou_activities": [{"title": "Only a title"}]}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)
        for k in MOU_REQUIRED[1:]:
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in ACTIVITY_REQUIRED[1:]:
            self.assertIn(f"activities.0.mou_activities.0.{k}", fe, k)
        self.assertFalse(any(".ev_" in k or "activity_type_other" in k for k in fe), fe)  # Yes/No answers optional

    def test_functional_mou_needs_an_activity(self):
        p = fx.kra18_payload(1, 1)
        p["activities"][0]["mou_activities"] = []
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps an MoU without activities
        self.assertEqual(self.errors_for(p)["activities.0.mou_activities"], ["Add at least 1 row(s)."])

    def test_other_activity_type_conditional(self):
        p = copy.deepcopy(fx.kra18_payload(1, 1))
        row = p["activities"][0]["mou_activities"][0]
        row.update(activity_type="Other", activity_type_other="")
        self.assertEqual(self.errors_for(p)["activities.0.mou_activities.0.activity_type_other"], ["Required."])
        row.update(activity_type="Workshop", activity_type_other="Leftover text")
        self.assertIn("activities.0.mou_activities.0.activity_type_other", self.errors_for(p))
        row["activity_type_other"] = ""
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=18)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=18).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra18"})

    def test_activities_stay_with_their_mou(self):
        p = fx.kra18_payload(2, 2)
        p["activities"][1]["mou_activities"][1]["title"] = "Second MoU only activity"
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 2 functional MoUs")
            acts = self.detail(self.a, sid)["payload"]["activities"]
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(acts, p["activities"])  # exact round trip, nested activities kept per MoU
        self.assertEqual(self.asg.submissions.count(), 1)
        section = html.split("MoU 2 of 2 (SYN/MOU/002) — Activity 2 of 2")[1].split("</section>")[0]
        self.assertIn("Second MoU only activity", section)
        self.assertIn("Example Research Organization 2 (synthetic)", section)  # MoU details repeated with its activity
        self.assertNotIn("Example Research Organization 1", section)
        self.assertEqual(html.count("— Activity "), 4)

    def test_source_examples_not_prefilled_and_unanswered_evidence(self):
        sid = self.new_draft()
        p = fx.kra18_payload(1, 1)
        for k in ("objective", "description", "outcomes"):
            p["activities"][0]["mou_activities"][0][k] = ""
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        for example in ("strengthening industry/research collaboration", "Enhanced industry/research exposure", "commenced with an introductory"):
            self.assertNotIn(example, html)
        self.assertIn("<td>Website/News Link</td><td class=\"center\">—</td>", html)  # not inferred from uploads
