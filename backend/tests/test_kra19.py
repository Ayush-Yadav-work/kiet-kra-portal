"""KRA 19 Industrial Visits (bounded Phase 4 task). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

REQUIRED = ("visit_date", "year_semester", "faculty_coordinators", "hod", "industry_name", "students_participated",
            "industry_profile", "objectives", "technical_overview", "departments_visited", "equipment", "quality_safety",
            "environmental", "learning_outcomes", "courses", "gaps", "conclusion", "feedback_summary")
OPTIONAL = ("students_eligible", "experts", "lo_matrix", "suggestions", "coordinator_remarks", "coordinator_name",
            "feedback_responses", "feedback_ratings", "annexures")


class KRA19Tests(WorkflowMixin, PortalTestCase):
    kra = 19
    evidence = ()  # no minimum evidence agreed (D-039)
    payload = staticmethod(lambda: fx.kra19_payload(2))
    expect_text = ("Industrial Visit Report", "Example Manufacturing Plant 2 (synthetic)", "Test Expert 2", "Synthetic Assembly Shop 2",
                   "Program Outcomes (POs)", "PSO1", "Theory-Practice Gap (synthetic)", "Industrial Visit Feedback Form (KRA 19b)",
                   "58 (of 64 in the class/batch)", "Synthetic Manufacturing Processes")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"industry_name": "Only a name"}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)  # 19b forms are evidence but not mandatory (D-039)
        for k in REQUIRED:
            if k != "industry_name":
                self.assertIn(f"activities.0.{k}", fe, k)
        for k in OPTIONAL:
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=19)}
        self.assertIn("NIL", before.values())  # target strings kept as the workbook has them
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=19).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra19"})

    def test_po_pso_matrix_persistence_and_rendering(self):
        p = fx.kra19_payload(1, matrix_rows=3, sparse_matrix=True)
        rows = p["activities"][0]["lo_matrix"]
        rows[0].update(pso1_a="A1", pso1_b="B1")
        rows[1].update(pso1_a="", pso1_b="")  # empty optional cells
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.assertEqual(self.save(self.a, sid, 0, payload=p).status_code, 200)
            stored = self.detail(self.a, sid)["payload"]["activities"][0]["lo_matrix"]
            self.assertEqual(stored, rows)  # exact round trip, distinct ids for the two "PSO1" columns
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        matrix = html.split('class="k11-grid iv-matrix"')[1].split("</table>")[0]
        self.assertEqual(matrix.count("<th>PSO1</th>"), 2)  # source labels kept, not renamed (D-012)
        self.assertNotIn("PSO2", matrix)
        first = matrix.split("1. Synthetic learning outcome 1")[1].split("</tr>")[0]
        cells = [c.split("</td>")[0] for c in first.split('<td class="center">')[1:]]
        self.assertEqual(len(cells), 14)
        self.assertEqual(cells[-2:], ["A1", "B1"])
        self.assertIn("", cells[:12])  # empty optional cells render blank
        fe = self.errors_for(p, strict=True)
        self.assertFalse(any(".lo_matrix." in k for k in fe), fe)

    def test_matrix_cells_bounded_and_outcome_required(self):
        p = copy.deepcopy(fx.kra19_payload(1, matrix_rows=1))
        row = p["activities"][0]["lo_matrix"][0]
        row["po3"] = "Strongly mapped"  # textual but bounded
        row["outcome"] = ""
        fe = self.errors_for(p, strict=False)
        self.assertEqual(fe, {"activities.0.lo_matrix.0.po3": ["Maximum 6 characters (currently 15)."]})
        row["po3"] = "3"
        self.assertEqual(self.errors_for(p)["activities.0.lo_matrix.0.outcome"], ["Required."])

    def test_long_outcome_text_and_counts_rules(self):
        p = copy.deepcopy(fx.kra19_payload(1, matrix_rows=20, long_text=True))
        a = p["activities"][0]
        a["students_participated"], a["students_eligible"], a["feedback_responses"] = 70, 64, 80
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.students_participated"], ["Students who participated cannot exceed the students eligible."])
        a["students_eligible"] = 75  # first rule satisfied; a rule is skipped while its field already has an error
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.feedback_responses"], ["Feedback responses cannot exceed the students who participated."])
        a["students_eligible"] = ""  # optional: rule skipped when blank
        a["students_participated"] = 60
        a["feedback_responses"] = 40
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())

    def test_multiple_visits_one_submission_kept_separate(self):
        sid = self.new_draft()
        p = fx.kra19_payload(3)
        p["activities"][1]["lo_matrix"][0]["po1"] = "X2"
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 3 visits, 174 student participations")
            d = self.detail(self.a, sid)
            acts = d["payload"]["activities"]
            self.assertEqual([x["industry_name"] for x in acts],
                             [f"Example Manufacturing Plant {i} (synthetic)" for i in (1, 2, 3)])
            self.assertEqual([x["lo_matrix"][0]["po1"] for x in acts], [acts[0]["lo_matrix"][0]["po1"], "X2", acts[2]["lo_matrix"][0]["po1"]])
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Visit 3 of 3", html)
        self.assertIn("Visits in this report", html)
        self.assertEqual(self.asg.submissions.count(), 1)  # one consolidated submission per period
        self.assertEqual(d["achievement_text"], "Synthetic: 3 visits, 174 student participations")  # as entered, not computed

    def test_19b_is_summary_only(self):
        p = copy.deepcopy(fx.kra19_payload(1))
        p["activities"][0]["feedback_ratings"] = []
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("Consolidated feedback summary", html)
        self.assertNotIn("Organization &amp; Planning of Visit", html)  # no empty 19b grid when no averages entered
        for personal in ("Name of Student", "Roll Number"):
            self.assertNotIn(personal, html)
