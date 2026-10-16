"""KRAs 4–6 field projects / research projects / internships (Phase 4 batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

COMPONENT = {4: "Field project", 5: "Research project", 6: "Internship"}


class _FieldProjects(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-048)

    @property
    def expect_text(self):
        return ("Percentage of Programs that have components of field projects / research projects / internships",
                f"KRA {self.kra}: {COMPONENT[self.kra]} component", "Synthetic B.Tech Programme 2", f"Test Student 1.3",
                f"Students who completed the {COMPONENT[self.kra].lower()}")

    def payload(self):
        return fx.fp_payload(self.kra, 2, 3)

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"programme_name": "Only a name", "has_component": "Yes",
                                                                   "completions": [{"student_name": "Only a student"}]}]})
            self.assertEqual(r.status_code, 200)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in ("programme_code", "component_name", "course_code", "students_undertaking"):
            self.assertIn(f"activities.0.{k}", fe, k)
        self.assertNotIn("activities.0.document_link", fe)
        for k in ("roll_no", "title", "partner", "start_date", "completion_date"):
            self.assertIn(f"activities.0.completions.0.{k}", fe, k)

    def test_not_applicable_component_kept_but_ignored(self):
        p = copy.deepcopy(fx.fp_payload(self.kra, 1, 2))
        a = p["activities"][0]
        a.update(has_component="No", course_code="", students_undertaking=-5)  # stale/invalid component values left behind
        a["completions"][0]["completion_date"] = "2026-01-01"  # before start date
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())  # ignored at submission
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            stored = self.detail(self.a, sid)["payload"]["activities"][0]
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(stored["component_name"], a["component_name"])  # never silently erased
        self.assertEqual(len(stored["completions"]), 2)
        self.assertNotIn(a["component_name"], html)
        self.assertNotIn("Test Student 1.1", html)
        a["has_component"] = "Yes"  # switching back re-validates the kept values
        fe = self.errors_for(p)
        self.assertIn("activities.0.course_code", fe)
        self.assertEqual(fe["activities.0.completions.0.completion_date"], ["Completion date cannot be before the start date."])

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=self.kra)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=self.kra).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.template_version.key, a.template_version.renderer_template) for a in after},
                         {(f"kra{self.kra}", "reports/field_projects_v1.html")})

    def test_source_columns_and_completion_records(self):
        p = fx.fp_payload(self.kra, 3, 4)
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: as entered by the Dean")
            self.assertEqual(self.detail(self.a, sid)["payload"], p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        source = html.split('<table class="records">')[1].split("</table>")[0]
        for h in ("Name of the Programmes offered by the HEI", "Programme Code", f"Whether the program has components of {COMPONENT[self.kra]}",
                  "If yes, name of the component", "Course code of the component", "Number of students undertaking the", "Link to the relevant document"):
            self.assertIn(h, source)
        self.assertEqual(source.count('<span class="na">NA</span>'), 4)  # programme 2 answered No
        self.assertEqual(html.count('<table class="records">'), 3)  # source table + 2 programmes with completions
        self.assertEqual(html.count("Test Student 3."), 4)
        self.assertNotIn("%", source.split("</thead>")[1])  # no percentages computed


class KRA4Tests(_FieldProjects, PortalTestCase):
    kra = 4


class KRA5Tests(_FieldProjects, PortalTestCase):
    kra = 5


class KRA6Tests(_FieldProjects, PortalTestCase):
    kra = 6


class FieldProjectSeparationTests(PortalTestCase):
    def asg(self, n):
        return AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27")

    def test_three_kras_keep_separate_records_targets_and_achievements(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sids = {n: self.open_draft(a, self.asg(n), self.p2) for n in (4, 5, 6)}
            self.assertEqual(len(set(sids.values())), 3)
            self.save(a, sids[5], 0, payload=fx.fp_payload(5, 1, 2), achievement_text="KRA 5: synthetic")
            for n in (4, 5, 6):
                d = self.detail(a, sids[n])
                self.assertEqual(d["assignment"]["target_text"], self.asg(n).target_text)
                if n == 5:
                    self.assertEqual(len(d["payload"]["activities"][0]["completions"]), 2)
                    self.assertEqual(d["achievement_text"], "KRA 5: synthetic")
                else:  # nothing copied from KRA 5
                    self.assertNotIn("completions", str(d["payload"]))
                    self.assertEqual(d["achievement_text"], "")
        self.assertEqual({a.template_version.key for a in AnnualAssignment.objects.filter(kra__number__in=(4, 5, 6), department=self.cse)},
                         {"kra4", "kra5", "kra6"})
