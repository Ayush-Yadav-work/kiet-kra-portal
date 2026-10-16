"""KRAs 36-37 FDP/STP family (bounded Phase 4 task). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from apps.reports.families import fdp_stp_schema
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

REQUIRED = ("programme_title", "duration_hours", "organized_by", "mode", "target_group", "participants_count", "coordinator",
            "resource_persons", "introduction", "participants", "modules", "assessment_method", "min_attendance",
            "passing_criteria", "certificate_authority", "certificates_issued", "formats")
OPTIONAL = ("dates", "impact_details", "supporting_documents", "prepared_name", "approved_date")
MIN_HOURS_MSG = ["KRA 37 requires a programme of at least 30 hours (workbook: min 30 hours)."]


class FdpMixin(WorkflowMixin):
    evidence = ()  # no minimum evidence agreed (D-037)
    extra_required = ()

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"programme_title": "Only a title"}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertNotIn("evidence", fe)
        for k in REQUIRED + self.extra_required:
            if k != "programme_title":
                self.assertIn(f"activities.0.{k}", fe, k)
        for k in OPTIONAL:
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_stored_schema_matches_family_definition(self):
        self.assertEqual(self.asg.template_version.schema, fdp_stp_schema(self.kra))
        self.assertEqual(self.asg.template_version.renderer_template, "reports/fdp_stp_v1.html")

    def hours_errors(self, hours, strict=True):
        p = copy.deepcopy(fx.kra3637_payload(self.kra, hours=hours))
        return self.errors_for(p, strict=strict).get("activities.0.duration_hours")


class KRA36Tests(FdpMixin, PortalTestCase):
    kra = 36
    payload = staticmethod(lambda: fx.kra3637_payload(36, programmes=2))
    expect_text = ("REPORT ON FACULTY DEVELOPMENT PROGRAMME (FDP)/", "Title of the STP", "Staff Participation",
                   "Name of Staff Member", "STP Content/Syllabus", "The STP was organized with the following objectives:",
                   "After completion of the STP, participants were able to:", "Synthetic Office Procedures Training 2")
    extra_required = ("other_objectives", "other_outcomes")  # no faculty source lists for staff training

    def test_no_30_hour_threshold(self):
        for h in ("2", "29.5"):
            self.assertIsNone(self.hours_errors(h), h)
        self.assertNotIn("focus_areas", {f["id"] for s in fdp_stp_schema(36)["sections"] for f in s["fields"]})
        self.assertNotIn("teaching", " ".join(f.get("label", "") for s in fdp_stp_schema(36)["sections"] for f in s["fields"]))


class KRA37Tests(FdpMixin, PortalTestCase):
    kra = 37
    payload = staticmethod(lambda: fx.kra3637_payload(37, programmes=2))
    expect_text = ("Title of the FDP", "Focus Area", "Intellectual Property Rights (IPR)", "Faculty Participation",
                   "FDP Content/Syllabus", "32 hours", "To strengthen research, innovation and consultancy capabilities.",
                   "Develop research and innovation capabilities.")
    extra_required = ("focus_areas", "objectives", "outcomes")

    def test_30_hour_minimum_below_at_above(self):
        self.assertEqual(self.hours_errors("29.9"), MIN_HOURS_MSG)
        self.assertIsNone(self.hours_errors("30"))
        self.assertIsNone(self.hours_errors("30.0"))
        self.assertIsNone(self.hours_errors("45.5"))

    def test_short_programme_draft_saves_but_cannot_submit(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload=fx.kra3637_payload(37, hours="12"), achievement_text="1")
            self.assertEqual(r.status_code, 200)  # draft keeps 12 exactly
            self.assertEqual(self.detail(self.a, sid)["payload"]["activities"][0]["duration_hours"], "12")
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 1}, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json()["field_errors"]["activities.0.duration_hours"], MIN_HOURS_MSG)

    def test_nil_ignores_threshold(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=fx.kra3637_payload(37, hours="5"))
            self.save(self.a, sid, 1, is_nil=True, nil_reason="Synthetic: no FDP this period")
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 2}, format="json")
            self.assertEqual(r.status_code, 200, r.content)

    def test_claims_only_when_ticked(self):
        p = copy.deepcopy(fx.kra3637_payload(37))
        p["activities"][0].update(objectives=[], outcomes=[], other_objectives="", other_outcomes="", formats=[])
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        for claim in ("To enhance teaching, learning and assessment competencies.", "Apply innovative and effective",
                      "Expert lectures", "students will be able to"):
            self.assertNotIn(claim, html)
        for k in ("objectives", "outcomes", "formats"):
            self.assertEqual(fe[f"activities.0.{k}"], ["Select at least one."])


class FdpSeparationTests(PortalTestCase):
    def asg(self, n):
        return AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27")

    def test_mappings_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number__in=(36, 37))}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number__in=(36, 37)).select_related("template_version", "kra")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({(a.kra.number, a.template_version.key) for a in after}, {(36, "kra36"), (37, "kra37")})
        self.assertEqual(after.count(), 26)

    def test_independent_storage(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            s36, s37 = self.open_draft(a, self.asg(36), self.p2), self.open_draft(a, self.asg(37), self.p2)
            self.assertNotEqual(s36, s37)
            self.save(a, s36, 0, payload=fx.kra3637_payload(36), achievement_text="KRA 36 synthetic")
            self.save(a, s37, 0, payload=fx.kra3637_payload(37), achievement_text="KRA 37 synthetic")
            a.post(f"/api/v1/submissions/{s37}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/x",
                   "category": "Attendance sheet", "label": "KRA37 only"}, format="json")
            d36, d37 = self.detail(a, s36), self.detail(a, s37)
            self.assertEqual((d36["achievement_text"], d37["achievement_text"]), ("KRA 36 synthetic", "KRA 37 synthetic"))
            self.assertNotIn("focus_areas", d36["payload"]["activities"][0])
            self.assertEqual(len(a.get(f"/api/v1/submissions/{s36}/evidence/").json()["results"]), 0)
            self.assertEqual(len(a.get(f"/api/v1/submissions/{s37}/evidence/").json()["results"]), 1)
            # A KRA 37-only field is rejected on KRA 36.
            p = copy.deepcopy(fx.kra3637_payload(36))
            p["activities"][0]["focus_areas"] = ["Intellectual Property Rights (IPR)"]
            self.assertEqual(self.save(a, s36, 1, payload=p).status_code, 400)
