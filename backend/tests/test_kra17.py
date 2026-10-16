"""KRA 17 Training centres / labs with industry (Phase 4 industry-collaboration batch). SYNTHETIC data only."""
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

REQUIRED = ("centre_name", "industry_partner", "nature", "date_established", "location", "facilities", "purpose",
            "faculty_coordinator", "industry_coordinator", "status")


class KRA17Tests(WorkflowMixin, PortalTestCase):
    kra = 17
    evidence = ()  # no minimum evidence agreed (D-041)
    payload = staticmethod(lambda: fx.kra17_payload(3))
    expect_text = ("Training centres / labs established in collaboration with Industries", "Synthetic IoT Training Centre 3",
                   "Example Industry Partner 2 (synthetic)", "Centre of Excellence (CoE)", "Facilities/", "Industry Coordinator")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"centres": [{"centre_name": "Only a name"}]}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in REQUIRED[1:]:
            self.assertIn(f"activities.0.centres.0.{k}", fe, k)
        for k in ("mou_date", "mou_validity"):  # MoU optional pending college review (D-041)
            self.assertNotIn(f"activities.0.centres.0.{k}", fe, k)

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=17)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=17).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra17"})

    def test_all_source_columns_on_one_table(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra17_payload(4))
            self.assertEqual(self.detail(self.a, sid)["payload"], fx.kra17_payload(4))  # exact round trip
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(html.count('<table class="records">'), 1)  # source's 2-page column split repaired
        head = html.split('<table class="records">')[1].split("</thead>")[0].replace("<wbr>", "")
        for label in ("Sl. No.", "Academic Year", "Name of Training Centre/Lab", "Department", "Industry Partner", "Nature of Collaboration",
                      "Date Established", "MoU Date", "MoU Validity", "Location", "Facilities/Equipment", "Purpose/Training Area",
                      "Faculty Coordinator", "Industry Coordinator", "Current Status"):
            self.assertIn(label, head)
        self.assertEqual(html.count("Synthetic IoT Training Centre"), 4)
        self.assertIn("2026-27", html.split("Synthetic IoT Training Centre 4")[0].rsplit("<tr>", 1)[1])  # auto academic year

    def test_unknown_collaboration_type_rejected(self):
        p = fx.kra17_payload(1)
        p["activities"][0]["centres"][0]["nature"] = "Joint Lab/Training Centre/CoE"  # source sample text, not an option
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.centres.0.nature": ["Choose one of the listed options."]})
