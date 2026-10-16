"""KRAs 8, 9 (9a/9b) and 10 consolidated surveys (bounded Phase 4 task). SYNTHETIC data only."""
import copy
import io
from pathlib import Path

import pymupdf
from django.conf import settings
from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from apps.reports.families import (ALUMNI_9A_QUESTIONS, ALUMNI_9B_QUESTIONS, CURRICULUM_QUESTIONS, VARIANT_9A, VARIANT_9B,
                                   survey_schema)
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin
from tests.test_reports import RENDERER, pdf_text

TEMPLATES = Path(settings.PROJECT_ROOT) / "reference" / "templates"
SOURCES = {8: "KRA 8 Curriculum Feedback (Employer and Industry).docx.pdf",
           "9a": "KRA 9a - Alumni Feedback Survey Form (more than 4 Years).docx.pdf",
           "9b": "KRA 9b - Alumni Feedback Survey Form(Less than 4 Years).docx.pdf",
           10: "KRA 10 Curriculum Feedback (Academic Expert).docx.pdf"}
SCALE = ["Poor (1)", "Satisfactory (2)", "Good (3)", "Very Good (4)", "Excellent (5)"]


def norm(s):
    return " ".join(s.replace("​", "").split())


def field(kra, fid):
    return next(f for s in survey_schema(kra)["sections"] for f in s["fields"] if f["id"] == fid)


class SourceFidelityTests(PortalTestCase):
    def test_question_text_count_order_and_scale_match_sources(self):
        for key, items, count in ((8, field(8, "ratings")["items"], 12), (10, field(10, "ratings")["items"], 12),
                                  ("9a", field(9, "v9a_ratings")["items"], 10), ("9b", field(9, "v9b_ratings")["items"], 10)):
            src = norm(pdf_text((TEMPLATES / SOURCES[key]).read_bytes()))
            self.assertEqual(len(items), count, key)
            positions = [src.find(norm(q)) for q in items]
            self.assertTrue(all(p >= 0 for p in positions), (key, [q for q, p in zip(items, positions) if p < 0]))
            self.assertEqual(positions, sorted(positions), f"{key}: questions out of source order")
            squashed = src.replace(" ", "")  # alumni PDFs split words across lines ("Poo r (1)")
            for label in ("Poor(1)", "Satisfactory(2)", "Good(3)", "VeryGood(4)", "Excellent(5)"):
                self.assertIn(label, squashed, (key, label))
        for f in (field(8, "ratings"), field(10, "ratings"), field(9, "v9a_ratings"), field(9, "v9b_ratings")):
            self.assertEqual((f["scale"], f["scale_labels"], f["decimal_places"]), ([1, 2, 3, 4, 5], SCALE, 2))
        self.assertEqual(field(8, "ratings")["items"], field(10, "ratings")["items"])  # sources share the 12 questions
        self.assertNotEqual(ALUMNI_9A_QUESTIONS, ALUMNI_9B_QUESTIONS)
        rel10 = field(10, "relationships")["options"]
        self.assertEqual(rel10[0], "Academic Expert")
        self.assertEqual(rel10[1:], field(8, "relationships")["options"])
        src10 = norm(pdf_text((TEMPLATES / SOURCES[10]).read_bytes()))
        self.assertTrue(all(o in src10 for o in rel10))


class SurveyMixin(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-038)
    required = ()

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"collection_period": "only this"}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)
        for k in self.required + ("consolidated_by", "action_taken", "impact_analysis", "bos_discussion"):
            self.assertIn(f"activities.0.{k}", fe, k)

    def test_stored_schema_matches_family_definition(self):
        tv = self.asg.template_version
        self.assertEqual((tv.schema, tv.renderer_template), (survey_schema(self.kra), "reports/survey_family_v1.html"))


class KRA8Tests(SurveyMixin, PortalTestCase):
    kra = 8
    payload = staticmethod(lambda: fx.kra8_10_payload(8))
    expect_text = ("Curriculum Feedback Survey Form", "Consolidated response of 14 of 20 respondents surveyed",
                   "Not applicable (consolidated report)", "Employer of Graduates", "— represented", "3.80", "4.10", "4.00",
                   CURRICULUM_QUESTIONS[11], "Discussion in BoS")
    required = ("surveyed", "respondents", "organizations", "relationships", "ratings.0", "ratings.11")

    def test_decimal_boundaries_and_invalid_values(self):
        def errs(values, strict=True):
            p = copy.deepcopy(fx.kra8_10_payload(8))
            p["activities"][0]["ratings"] = values + ["4"] * (12 - len(values))
            return {k: v for k, v in self.errors_for(p, strict=strict).items() if k.startswith("activities.0.ratings")}
        self.assertEqual(errs(["1", "5", "1.00", "5.00", "3.5"]), {})  # bounds inclusive, 2 places allowed
        fe = errs(["0.99", "5.01", "4.255"])
        self.assertEqual(fe["activities.0.ratings.0"], ["Must be between 1 and 5."])
        self.assertEqual(fe["activities.0.ratings.1"], ["Must be between 1 and 5."])
        self.assertEqual(fe["activities.0.ratings.2"], ["Use at most 2 decimal places (values are not rounded)."])
        self.assertEqual(errs(["0.99", "5.01", "4.255"], strict=False), {})  # draft keeps them as typed
        self.assertEqual(errs(["abc"], strict=False), {"activities.0.ratings.0": ["Must be a number."]})
        sid = self.new_draft()
        p = copy.deepcopy(fx.kra8_10_payload(8))
        p["activities"][0]["ratings"][0] = "4.255"
        self.errors_for(p, strict=False, sid=sid)
        self.assertEqual(self.detail(self.a, sid)["payload"]["activities"][0]["ratings"][0], "4.255")  # not rounded

    def test_respondents_cannot_exceed_surveyed(self):
        p = copy.deepcopy(fx.kra8_10_payload(8))
        p["activities"][0]["respondents"] = 25
        self.assertEqual(self.errors_for(p)["activities.0.respondents"], ["Respondents cannot exceed the number surveyed."])


class KRA10Tests(SurveyMixin, PortalTestCase):
    kra = 10
    payload = staticmethod(lambda: fx.kra8_10_payload(10))
    expect_text = ("Curriculum Feedback Survey Form", "Academic Expert", "— represented", "Consolidated response of 14 of 20",
                   CURRICULUM_QUESTIONS[0])
    required = ("surveyed", "respondents", "organizations", "relationships", "ratings.0")


class KRA9Tests(SurveyMixin, PortalTestCase):
    kra = 9
    payload = staticmethod(lambda: fx.kra9_payload(("9a", "9b")))
    expect_text = ("Alumni Survey Form", "(For Alumni having more than 4 Years Professional Experience after Passing Degree Course)",
                   "(For Alumni having less than 4 Years Professional Experience after Passing Degree Course)",
                   "ALUMNI FEEDBACK FORM (9a)", "ALUMNI FEEDBACK FORM (9b)", "Consolidated response of 22 of 30 alumni surveyed",
                   ALUMNI_9A_QUESTIONS[2], ALUMNI_9B_QUESTIONS[0], "4.05", "3.95")
    required = ("variants",)

    def preview(self, sid):
        return self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]

    def test_9a_only_9b_only_and_both(self):
        for chosen, present, absent in ((("9a",), ALUMNI_9A_QUESTIONS, ALUMNI_9B_QUESTIONS),
                                        (("9b",), ALUMNI_9B_QUESTIONS, ALUMNI_9A_QUESTIONS)):
            p = fx.kra9_payload(("9a", "9b"))
            p["activities"][0]["variants"] = [{"9a": VARIANT_9A, "9b": VARIANT_9B}[c] for c in chosen]
            other = "9b" if chosen == ("9a",) else "9a"
            p["activities"][0][f"v{other}_ratings"] = []  # unselected variant incomplete: must not block submission
            p["activities"][0][f"v{other}_respondents"] = 99  # and its rule must not fire
            self.assertEqual(self.errors_for(p), {"achievement_text": ["Enter the achievement for this period."]})
            sid = self.new_draft()
            with frozen(ist(2026, 10, 1)):
                html = self.preview(sid)
            self.assertIn(present[0], html)
            self.assertNotIn(absent[0], html)
        p = fx.kra9_payload(("9a", "9b"))
        p["activities"][0]["v9b_ratings"] = ["4"] * 9
        p["activities"][0]["v9a_respondents"] = 31
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.v9b_ratings.9"], ["Enter the consolidated average."])
        self.assertEqual(fe["activities.0.v9a_respondents"], ["Respondents cannot exceed the number surveyed."])
        p["activities"][0]["variants"] = []
        self.assertEqual(self.errors_for(p)["activities.0.variants"], ["Select at least one."])

    def test_switching_selection_keeps_data_and_excludes_deselected_from_pdf(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload=fx.kra9_payload(("9a", "9b")), achievement_text="22 (9a) synthetic")
            p = fx.kra9_payload(("9a",))  # deselect 9b; its entered data is still sent and kept
            r = self.save(self.a, sid, r.json()["edit_version"], payload=p)
            kept = self.detail(self.a, sid)["payload"]["activities"][0]
            self.assertEqual(kept["v9b_ratings"][0], "3.05")
            self.assertEqual(kept["v9b_suggestions"], "Synthetic 9b suggestion")
            html = self.preview(sid)
            self.assertNotIn("ALUMNI FEEDBACK FORM (9b)", html)
            self.assertNotIn("3.05", html)
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": r.json()["edit_version"]}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            if RENDERER:
                data = b"".join(self.a.get(f"/api/v1/submissions/{sid}/export/").streaming_content)
                text = " ".join(pdf_text(data).split())
                self.assertIn("ALUMNI FEEDBACK FORM (9a)", text)
                self.assertNotIn("ALUMNI FEEDBACK FORM (9b)", text)
                self.assertNotIn(" ".join(ALUMNI_9B_QUESTIONS[4].split()), text)

    def test_scores_never_merged(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra9_payload(("9a", "9b")))
            html = self.preview(sid)
        for v in ("4.05", "4.95", "3.05", "3.95"):  # each variant's own averages, no combined figure
            self.assertIn(f"<b>{v}</b>", html)
        self.assertNotIn("3.55", html.split("ALUMNI FEEDBACK FORM (9a)")[1].split("ALUMNI FEEDBACK FORM (9b)")[0])


class SurveySeparationTests(PortalTestCase):
    def asg(self, n):
        return AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27")

    def test_mappings_idempotent_and_kra7_untouched(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number__in=(7, 8, 9, 10))}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number__in=(7, 8, 9, 10)).select_related("template_version", "kra")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.kra.number, a.template_version.key) for a in after},
                         {(7, "kra7"), (8, "kra8"), (9, "kra9"), (10, "kra10")})
        self.assertEqual(self.asg(7).template_version.renderer_template, "reports/kra7_v1.html")

    def test_independent_storage(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sids = {n: self.open_draft(a, self.asg(n), self.p2) for n in (8, 9, 10)}
            self.assertEqual(len(set(sids.values())), 3)
            self.save(a, sids[8], 0, payload=fx.kra8_10_payload(8), achievement_text="KRA 8 synthetic")
            self.save(a, sids[9], 0, payload=fx.kra9_payload(), achievement_text="KRA 9 synthetic")
            self.save(a, sids[10], 0, payload=fx.kra8_10_payload(10), achievement_text="KRA 10 synthetic")
            a.post(f"/api/v1/submissions/{sids[9]}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/x",
                   "category": "BoS Minutes", "label": "KRA9 only"}, format="json")
            for n in (8, 9, 10):
                self.assertEqual(self.detail(a, sids[n])["achievement_text"], f"KRA {n} synthetic")
                self.assertEqual(len(a.get(f"/api/v1/submissions/{sids[n]}/evidence/").json()["results"]), 1 if n == 9 else 0)
            p = fx.kra8_10_payload(8)
            p["activities"][0]["variants"] = [VARIANT_9A]  # KRA 9 field on KRA 8
            self.assertEqual(self.save(a, sids[8], 1, payload=p).status_code, 400)
