"""KRA 15 Entrepreneurs (Phase 4 table batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

HEADINGS = ("Sl. No.", "Academic Year", "Name of Entrepreneur", "Category", "Student/Alumni ID", "Programme", "Batch/ Passing Year", "Gender",
            "Startup/ Enterprise Name", "Sector/ Domain", "Founder/ Co-Founder", "Year of Establishment", "Registration No. /DPIIT No.",
            "Current Status", "Evidence Available")


class KRA15Tests(WorkflowMixin, PortalTestCase):
    kra = 15
    evidence = ()  # no minimum evidence agreed (D-044)
    payload = staticmethod(lambda: fx.kra15_payload(4))
    expect_text = ("Entrepreneurs (Faculty / Alumni / Student)", "Synthetic Ventures 4", "SYN-DPIIT00003", "Co-Founder", "Faculty")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"records": [{"name": "Only a name", "category": "Student"}]}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("member_id", "programme", "batch", "gender", "enterprise", "sector", "founder_role", "year_established", "status",
                  "evidence_available"):
            self.assertIn(f"activities.0.records.0.{k}", fe, k)
        self.assertNotIn("activities.0.records.0.registration_no", fe)  # registration/DPIIT not mandatory

    def test_faculty_rows_skip_student_only_columns(self):
        p = copy.deepcopy(fx.kra15_payload(3))
        row = p["activities"][0]["records"][1]  # i=2 -> Faculty
        self.assertEqual((row["category"], row["programme"], row["batch"]), ("Faculty", "", ""))
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())
        row["programme"] = "B.Tech ECE"  # leftover student value rejected for faculty at submission
        self.assertIn("activities.0.records.1.programme", self.errors_for(p))
        p["activities"][0]["records"][0]["batch"] = ""  # Alumni row needs its batch
        self.assertEqual(self.errors_for(p)["activities.0.records.0.batch"], ["Required."])

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=15)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=15).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.template_version.key, a.template_version.renderer_template) for a in after},
                         {("kra15", "reports/records_sheet_v1.html")})

    def test_one_table_all_columns_and_round_trip(self):
        p = fx.kra15_payload(5)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 5 entrepreneurs")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(html.count('<table class="records">'), 1)  # source's 3-page split repaired
        head = html.split('<table class="records">')[1].split("</thead>")[0].replace("<wbr>", "")
        for h in HEADINGS:
            self.assertIn(h, head)
        faculty = html.split("Test Entrepreneur 2 Zoë")[1].split("</tr>")[0]
        self.assertEqual(faculty.count('<span class="na">NA</span>'), 2)  # programme and batch NA for faculty
        self.assertNotIn("%", html.split("</thead>")[1].split("</table>")[0])  # no computed percentages/totals
