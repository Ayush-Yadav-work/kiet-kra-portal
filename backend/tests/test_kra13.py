"""KRA 13 Faculty membership in industry advisory boards / committees (Phase 4 industry-collaboration batch). SYNTHETIC data only."""
import copy
import io

from django.core.management import call_command

from apps.catalogue.models import AnnualAssignment
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_phase3 import WorkflowMixin

REQUIRED = ("faculty_name", "designation", "employee_id", "organization", "committee_type", "committee_name", "appointment_date",
            "tenure_from", "membership_nature", "appointing_authority", "chairperson", "purpose", "domain", "contributions",
            "impact_students", "impact_curriculum", "impact_industry", "impact_research", "impact_quality", "total_period",
            "meetings_attended", "major_activities", "recommendations", "major_outcomes", "orgs_involved")
OPTIONAL = ("tenure_to", "committee_org", "website", "objectives", "other_objectives", "meetings", "documents", "other_documents",
            "student_beneficiaries", "hod_name", "hod_designation", "committee_type_other")


class KRA13Tests(WorkflowMixin, PortalTestCase):
    kra = 13
    evidence = ()  # no minimum evidence agreed (D-042)
    payload = staticmethod(lambda: fx.kra13iab_payload(2))
    expect_text = ("Report on Faculty Membership In Industry Advisory Board / Other Committees", "Test Faculty 2", "Synthetic Advisory Board 2",
                   "Nature of Contribution / Responsibilities", "Meetings Attended", "SYN-M2", "Summary of Contribution",
                   "Head of Department / Competent Authority")

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload={"activities": [{"faculty_name": "Only a name"}]})
            self.assertEqual(r.status_code, 200)  # incomplete draft saves
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertNotIn("evidence", fe)
        for k in REQUIRED[1:]:
            self.assertIn(f"activities.0.{k}", fe, k)
        for k in OPTIONAL:
            self.assertNotIn(f"activities.0.{k}", fe, k)

    def test_conditional_type_tenure_and_row_fields(self):
        p = copy.deepcopy(fx.kra13iab_payload(1))
        a = p["activities"][0]
        a.update(committee_type="Other", committee_type_other="", tenure_from="2026-07-01", tenure_to="2026-06-30")
        a["meetings"][0]["agenda"] = ""
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.committee_type_other"], ["Required."])
        self.assertEqual(fe["activities.0.tenure_to"], ["Tenure end cannot be before the tenure start."])
        self.assertEqual(fe["activities.0.meetings.0.agenda"], ["Required."])
        a.update(committee_type_other="Statutory university body (synthetic)", tenure_to="")  # continuing membership
        a["meetings"] = []  # meetings table optional
        self.assertEqual({k for k in self.errors_for(p) if k != "achievement_text"}, set())

    def test_mapping_idempotent_targets_unchanged(self):
        before = {a.pk: a.target_text for a in AnnualAssignment.objects.filter(kra__number=13)}
        call_command("seed_catalogue", stdout=io.StringIO())
        after = AnnualAssignment.objects.filter(kra__number=13).select_related("template_version")
        self.assertEqual({a.pk: a.target_text for a in after}, before)
        self.assertEqual({a.template_version.key for a in after}, {"kra13"})

    def test_memberships_keep_their_own_contributions_and_meetings(self):
        p = fx.kra13iab_payload(2, contributions=2, meetings=3)
        p["activities"][1]["contributions"][0]["contribution"] = "Only in membership two"
        p["activities"][1]["meetings"] = p["activities"][1]["meetings"][:1]
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p, achievement_text="Synthetic: 2 faculty members")
            acts = self.detail(self.a, sid)["payload"]["activities"]
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertEqual(acts, p["activities"])  # exact round trip of nested rows
        one, two = html.split("Membership 2 of 2")
        self.assertNotIn("Only in membership two", one)
        self.assertIn("Only in membership two", two)
        self.assertEqual((one.count("SYN-M"), two.count("SYN-M")), (3, 1))
        self.assertIn("To continuing", two)  # membership 2 has no end date

    def test_source_examples_print_only_when_chosen(self):
        p = copy.deepcopy(fx.kra13iab_payload(1))
        p["activities"][0].update(objectives=[], other_objectives="")
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=p)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("To establish and strengthen interaction", html)
        self.assertNotIn("Guest Lecture / Expert Talk / Workshop", html)  # contribution rows not added are not printed
        self.assertIn("Minutes of Meeting — <b>Yes</b>", html)
        self.assertIn("<li>Attendance Record</li>", html)  # unanswered document not asserted
