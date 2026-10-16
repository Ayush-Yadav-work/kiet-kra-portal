import datetime
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from apps.catalogue.models import AnnualAssignment, ReportingPeriod
from apps.evidence.models import Evidence
from apps.submissions.models import ReopenGrant, ReopenRequest, Submission, SubmissionRevision
from tests.base import PortalTestCase, frozen, ist
from tests.fixtures import kra33_payload

PDF = b"%PDF-1.4\n% synthetic\n" + b"0" * 2000
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 2000


class CalendarTests(PortalTestCase):
    def test_period_boundaries_are_ist_midnight_stored_utc(self):
        self.assertEqual(self.p2.opens_at, ist(2026, 9, 1))
        self.assertEqual(self.p2.closes_at, ist(2026, 11, 1))
        self.assertEqual(self.p2.opens_at.astimezone(datetime.timezone.utc), datetime.datetime(2026, 8, 31, 18, 30, tzinfo=datetime.timezone.utc))
        p3 = ReportingPeriod.objects.get(year__label="2026-27", index=3)
        self.assertEqual((p3.opens_at, p3.closes_at), (ist(2026, 11, 1), ist(2027, 1, 1)))
        p6 = ReportingPeriod.objects.get(year__label="2026-27", index=6)
        self.assertEqual(p6.closes_at, ist(2027, 7, 1))

    def test_open_close_edges(self):
        self.assertFalse(self.p2.is_open(ist(2026, 9, 1) - datetime.timedelta(microseconds=1)))
        self.assertTrue(self.p2.is_open(ist(2026, 9, 1)))  # exact opening is inside
        self.assertTrue(self.p2.is_open(ist(2026, 11, 1) - datetime.timedelta(microseconds=1)))
        self.assertFalse(self.p2.is_open(ist(2026, 11, 1)))  # exact closing is outside

    def test_leap_year_period(self):
        p4 = ReportingPeriod.objects.get(year__label="2027-28", index=4)  # Jan-Feb 2028 (leap)
        self.assertTrue(p4.is_open(ist(2028, 2, 29, 23, 59)))
        self.assertFalse(p4.is_open(ist(2028, 3, 1)))

    def test_cannot_create_draft_before_open_or_after_close(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 8, 31, 23, 59)):
            r = a.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p2.id}/")
            self.assertEqual((r.status_code, r.json()["code"]), (409, "window_closed"))
        with frozen(ist(2026, 11, 1)):
            r = a.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p2.id}/")
            self.assertEqual(r.status_code, 409)
        self.assertFalse(Submission.objects.exists())


class DraftAndSubmitTests(PortalTestCase):
    def test_incomplete_draft_saves_and_untouched_draft_shows_not_submitted(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.assertEqual(self.detail(a, sid)["display_status"], "NOT_SUBMITTED")  # C11
            r = self.save(a, sid, 0, payload={"activities": [{"event_name": "Partial"}]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), {**r.json(), "edit_version": 1, "display_status": "DRAFT"})

    def test_structural_validation_on_save(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            r = self.save(a, sid, 0, payload={"activities": [{"alumni_count": "many", "bogus": 1}]})
            self.assertEqual(r.status_code, 400)
            self.assertIn("activities.0.alumni_count", r.json()["field_errors"])
            self.assertIn("activities.0.bogus", r.json()["field_errors"])
            r = self.save(a, sid, 0, payload={"activities": [{} for _ in range(21)]})
            self.assertEqual(r.status_code, 400)
            r = self.save(a, sid, 0, status="APPROVED", remarks="ok")  # status is never client-writable
            self.assertEqual(r.status_code, 200)
            self.assertEqual(Submission.objects.get(pk=sid).status, "DRAFT")

    def test_version_conflict_between_two_tabs(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.assertEqual(self.save(a, sid, 0, remarks="tab 1").status_code, 200)
            r = self.save(a, sid, 0, remarks="tab 2")
            self.assertEqual((r.status_code, r.json()["code"], r.json()["edit_version"]), (409, "version_conflict", 1))
            self.assertEqual(Submission.objects.get(pk=sid).remarks, "tab 1")

    def test_invalid_submit_fails_with_field_errors(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.save(a, sid, 0, payload={"activities": [{"event_name": "x"}]})
            r = a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 1}, format="json")
            self.assertEqual(r.status_code, 400)
            fe = r.json()["field_errors"]
            self.assertIn("activities.0.chapter_name", fe)
            self.assertIn("achievement_text", fe)
            self.assertIn("evidence", fe)
            self.assertFalse(SubmissionRevision.objects.exists())

    def test_submit_snapshot_and_lock(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            d = self.complete_and_submit(a, sid)
            self.assertEqual(d["status"], "SUBMITTED")
            rev = SubmissionRevision.objects.get(submission_id=sid)
            self.assertEqual(rev.snapshot["target_text"], self.asg_a.target_text)
            self.assertEqual(len(rev.evidence_manifest), 3)
            self.assertEqual(self.save(a, sid, d["edit_version"], remarks="late").status_code, 409)
            r = a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": d["edit_version"]}, format="json")
            self.assertEqual(r.status_code, 409)  # double submit does not duplicate
            self.assertEqual(SubmissionRevision.objects.filter(submission_id=sid).count(), 1)
            r = a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/x",
                                                                 "category": "Photographs", "label": "late"}, format="json")
            self.assertEqual(r.status_code, 409)
            with self.assertRaises(RuntimeError):
                rev.save()  # revisions are immutable

    def test_nil_requires_reason_and_no_evidence(self):
        a, vc = self.client_for(self.dean_a), self.client_for(self.vc)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.save(a, sid, 0, is_nil=True)
            r = a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 1}, format="json")
            self.assertEqual(list(r.json()["field_errors"]), ["nil_reason"])
            self.save(a, sid, 1, nil_reason="No alumni event this period (synthetic).")
            r = a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 2}, format="json")
            self.assertEqual(r.status_code, 200)
            rev = r.json()["current_revision"]["id"]
            self.assertEqual(vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json").status_code, 200)
            self.assertEqual(self.detail(a, sid)["display_status"], "APPROVED")


class ReviewTests(PortalTestCase):
    def submitted(self, at=ist(2026, 10, 1)):
        a = self.client_for(self.dean_a)
        with frozen(at):
            sid = self.open_draft(a, self.asg_a, self.p2)
            d = self.complete_and_submit(a, sid)
        return a, sid, d["current_revision"]["id"]

    def review(self, sid, rev, decision, reason="", grant=False, at=ist(2026, 10, 2)):
        with frozen(at):
            return self.client_for(self.vc).post(f"/api/v1/submissions/{sid}/review/", {
                "revision": rev, "decision": decision, "reason": reason, "grant_reopen": grant}, format="json")

    def test_reject_requires_reason_and_approve_stale_revision_rejected(self):
        a, sid, rev = self.submitted()
        self.assertEqual(self.review(sid, rev, "REJECT").status_code, 400)
        self.assertEqual(self.review(sid, "00000000-0000-0000-0000-000000000000", "APPROVE").json()["code"], "stale_revision")
        self.assertEqual(self.review(sid, rev, "REJECT", "Fix dates").status_code, 200)
        # resubmit within window, VC tab still holding the old revision cannot approve
        with frozen(ist(2026, 10, 3)):
            d = self.detail(a, sid)
            self.save(a, sid, d["edit_version"], remarks="fixed")
            r = a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": d["edit_version"] + 1}, format="json")
            self.assertEqual(r.json()["current_revision"]["sequence"], 2)
        self.assertEqual(self.review(sid, rev, "APPROVE", at=ist(2026, 10, 4)).status_code, 409)
        rev2 = r.json()["current_revision"]["id"]
        self.assertEqual(self.review(sid, rev2, "APPROVE", at=ist(2026, 10, 4)).status_code, 200)
        self.assertEqual(self.review(sid, rev2, "APPROVE", at=ist(2026, 10, 4)).status_code, 409)  # no double approve

    def test_return_approved_keeps_history(self):
        a, sid, rev = self.submitted()
        self.review(sid, rev, "APPROVE")
        r = self.review(sid, rev, "RETURN", "Correct participant counts", at=ist(2026, 10, 5))
        self.assertEqual(r.json()["status"], "REJECTED")
        h = a.get(f"/api/v1/submissions/{sid}/history/").json()
        self.assertEqual([d["decision"] for d in h["revisions"][0]["decisions"]], ["APPROVE", "RETURN"])

    # --- C1 ---
    def test_c1_more_than_72h_left_offers_no_grant(self):
        a, sid, rev = self.submitted()
        with frozen(ist(2026, 10, 2)):
            self.assertFalse(self.detail(self.client_for(self.vc), sid)["grant_option_available"])
        self.review(sid, rev, "REJECT", "x", grant=True)
        self.assertFalse(ReopenGrant.objects.exists())

    def test_c1_closing_within_72h_checked_creates_one_grant(self):
        a, sid, rev = self.submitted()
        at = ist(2026, 10, 30, 12)  # 36h before close
        with frozen(at):
            self.assertTrue(self.detail(self.client_for(self.vc), sid)["grant_option_available"])
        self.review(sid, rev, "REJECT", "x", grant=True, at=at)
        g = ReopenGrant.objects.get()
        self.assertEqual((g.starts_at, g.expires_at, g.source), (at, at + datetime.timedelta(hours=72), "REVIEW"))

    def test_c1_after_close_unchecked_creates_none_then_checked_return_creates_one(self):
        a, sid, rev = self.submitted()
        self.review(sid, rev, "REJECT", "x", grant=False, at=ist(2026, 11, 5))
        self.assertFalse(ReopenGrant.objects.exists())
        with frozen(ist(2026, 11, 5, 1)):
            self.assertEqual(self.save(a, sid, self.detail(a, sid)["edit_version"], remarks="x").json()["code"], "window_closed")

    def test_c1_grant_allows_correction_after_deadline_then_expires(self):
        a, sid, rev = self.submitted()
        at = ist(2026, 11, 10, 9)
        self.review(sid, rev, "REJECT", "Add photographs", grant=True, at=at)
        with frozen(at + datetime.timedelta(hours=71)):
            d = self.detail(a, sid)
            self.assertTrue(d["editable"])
            self.assertEqual(self.save(a, sid, d["edit_version"], remarks="corrected").status_code, 200)
            banner = a.get("/api/v1/reopen-grants/active/").json()["results"]
            self.assertEqual(len(banner), 1)  # C9
        with frozen(at + datetime.timedelta(hours=72)):
            self.assertFalse(self.detail(a, sid)["editable"])
            self.assertEqual(a.get("/api/v1/reopen-grants/active/").json()["results"], [])  # C9 disappears at expiry
        with frozen(at + datetime.timedelta(hours=1)):  # B's banner never shows A's grants
            self.assertEqual(self.client_for(self.dean_b).get("/api/v1/reopen-grants/active/").json()["results"], [])

    def test_c1_grant_db_constraint_requires_exactly_one_source(self):
        a, sid, rev = self.submitted()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReopenGrant.objects.create(submission_id=sid, starts_at=ist(2026, 11, 2), expires_at=ist(2026, 11, 5),
                                       approved_by=self.vc, source="REQUEST")


class ReopenRequestTests(PortalTestCase):
    def test_c2_request_without_row_creates_one_draft_and_one_request(self):
        a, vc = self.client_for(self.dean_a), self.client_for(self.vc)
        url = f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p1.id}/reopen-requests/"
        with frozen(ist(2026, 10, 1)):
            self.assertEqual(a.post(url, {"reason": ""}, format="json").status_code, 400)
            r = a.post(url, {"reason": "Event report was delayed"}, format="json")
            self.assertEqual(r.status_code, 201)
            self.assertEqual(a.post(url, {"reason": "again"}, format="json").json()["code"], "request_pending")
            sub = Submission.objects.get()
            self.assertEqual((sub.status, sub.edit_version), ("DRAFT", 0))
            self.assertEqual(ReopenRequest.objects.count(), 1)
            # C11: shown as Not submitted while pending, in Dean list and VC progress
            rows = a.get(f"/api/v1/assignments/?year=2026-27&period={self.p1.id}").json()["results"]
            self.assertEqual(next(x for x in rows if x["kra"]["number"] == 33)["submission"]["display_status"], "NOT_SUBMITTED")
            prog = vc.get(f"/api/v1/progress/?year=2026-27&period={self.p1.id}&department=CSE&kra=33").json()
            self.assertEqual(prog["results"][0]["display_status"], "NOT_SUBMITTED")
            # denial needs a reason; row still Not submitted afterwards
            req_id = r.json()["id"]
            self.assertEqual(vc.post(f"/api/v1/reopen-requests/{req_id}/decision/", {"approve": False}, format="json").status_code, 400)
            vc.post(f"/api/v1/reopen-requests/{req_id}/decision/", {"approve": False, "reason": "Not justified"}, format="json")
            self.assertEqual(self.detail(a, str(sub.id))["display_status"], "NOT_SUBMITTED")
            # second request after denial is allowed (one pending at a time); approval grants exactly 72h
            r = a.post(f"/api/v1/submissions/{sub.id}/reopen-requests/", {"reason": "More detail"}, format="json")
            d = vc.post(f"/api/v1/reopen-requests/{r.json()['id']}/decision/", {"approve": True}, format="json").json()
            self.assertEqual(datetime.datetime.fromisoformat(d["grant"]["expires_at"]) - datetime.datetime.fromisoformat(d["grant"]["starts_at"]),
                             datetime.timedelta(hours=72))
            self.assertEqual(vc.post(f"/api/v1/reopen-requests/{r.json()['id']}/decision/", {"approve": True}, format="json").status_code, 409)
            # C11: first evidence upload turns it into Draft
            a.post(f"/api/v1/submissions/{sub.id}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/a",
                                                                "category": "Photographs", "label": "p"}, format="json")
            self.assertEqual(self.detail(a, str(sub.id))["display_status"], "DRAFT")
            self.assertEqual(a.post(f"/api/v1/submissions/{sub.id}/reopen-requests/", {"reason": "x"}, format="json").json()["code"], "grant_active")

    def test_request_rejected_while_period_open(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            r = a.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p2.id}/reopen-requests/", {"reason": "x"}, format="json")
            self.assertEqual(r.json()["code"], "period_open")
        self.assertFalse(Submission.objects.exists())


class EvidenceTests(PortalTestCase):
    def setUp(self):
        self.a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            self.sid = self.open_draft(self.a, self.asg_a, self.p2)

    def upload(self, data, name="x.pdf", category="Photographs"):
        with frozen(ist(2026, 10, 1)):
            return self.a.post(f"/api/v1/submissions/{self.sid}/evidence/",
                               {"file": SimpleUploadedFile(name, data), "category": category, "label": name}, format="multipart")

    def test_c3_evidence_does_not_bump_edit_version(self):
        self.assertEqual(self.upload(PDF).status_code, 201)
        self.assertEqual(Submission.objects.get(pk=self.sid).edit_version, 0)
        with frozen(ist(2026, 10, 1)):
            self.assertEqual(self.save(self.a, self.sid, 0, remarks="typed during upload").status_code, 200)

    def test_signature_validation_rejects_html_svg_exe(self):
        for data, name in [(b"<html><script>", "a.pdf"), (b"<svg xmlns=", "a.png"), (b"MZ\x90\x00", "a.exe")]:
            r = self.upload(data, name)
            self.assertEqual(r.json()["code"], "invalid_type", name)
        self.assertEqual(self.upload(PNG, "photo.png").json()["mime"], "image/png")

    def test_c5_drive_link_has_null_file_fields_and_file_needs_checksum(self):
        with frozen(ist(2026, 10, 1)):
            bad = self.a.post(f"/api/v1/submissions/{self.sid}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "http://evil.example/x",
                                                                            "category": "Photographs", "label": "x"}, format="json")
            self.assertEqual(bad.status_code, 400)
            ok = self.a.post(f"/api/v1/submissions/{self.sid}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://docs.google.com/d/1",
                                                                           "category": "Photographs", "label": "x"}, format="json")
            self.assertEqual(ok.status_code, 201)
        ev = Evidence.objects.get(pk=ok.json()["id"])
        self.assertIsNone(ev.storage_key)
        self.assertIsNone(ev.bytes)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Evidence.objects.create(submission_id=self.sid, source_type="FILE", category="Photographs", label="x",
                                    storage_key="evidence/" + "a" * 32 + ".pdf", original_filename="x.pdf", mime="application/pdf",
                                    bytes=10, checksum=None, uploaded_by=self.dean_a)

    @override_settings(EVIDENCE_MAX_ACTIVE_BYTES=5000, EVIDENCE_MAX_HISTORY_BYTES=8000)
    def test_c6_quota_counts_active_only_with_history_cap(self):
        first = self.upload(PDF).json()  # ~2 KB
        self.assertEqual(self.upload(PDF).status_code, 201)
        self.assertEqual(self.upload(PDF).json()["code"], "quota_active")
        with frozen(ist(2026, 10, 1)):
            self.a.delete(f"/api/v1/evidence/{first['id']}/")
        self.assertEqual(self.upload(PDF).status_code, 201)  # removed file no longer counts
        with frozen(ist(2026, 10, 1)):
            for e in Evidence.objects.filter(submission_id=self.sid, removed=False):
                self.a.delete(f"/api/v1/evidence/{e.id}/")
        self.assertEqual(self.upload(PDF).json()["code"], "quota_history")  # 4 x ~2 KB > 8000 bytes history

    def test_protected_download_headers_and_removed_file_retained(self):
        ev = self.upload(PDF, "report.pdf").json()
        r = self.a.get(f"/api/v1/evidence/{ev['id']}/download/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn('attachment; filename="report.pdf"', r["Content-Disposition"])
        self.assertEqual(b"".join(r.streaming_content), PDF)
        with frozen(ist(2026, 10, 1)):
            self.a.delete(f"/api/v1/evidence/{ev['id']}/")
        self.assertEqual(self.a.get(f"/api/v1/evidence/{ev['id']}/download/").status_code, 200)
        self.assertEqual(self.client_for(self.dean_b).get(f"/api/v1/evidence/{ev['id']}/download/").status_code, 404)


class TargetAndSeedTests(PortalTestCase):
    def test_exact_source_targets(self):
        t = {a.department.code: a.target_text for a in AnnualAssignment.objects.filter(kra__number=43, year__label="2026-27")}
        self.assertEqual(t["CSE"], "Min 1 Per Department  per Year ( 20% papers of accepted and published papers should be from KIET University )")
        self.assertEqual(AnnualAssignment.objects.get(department__code="CSE", kra__number=32).target_text, "NA")
        self.assertEqual(AnnualAssignment.objects.get(department__code="CSE", kra__number=2).target_text, "3")
        self.assertEqual(AnnualAssignment.objects.get(department__code="CSE", kra__number=39).target_text, "1050119")
        self.assertEqual(AnnualAssignment.objects.filter(year__label="2026-27").count(), 585)
        self.assertFalse(AnnualAssignment.objects.filter(year__label="2027-28").exists())  # no automatic future targets

    def test_target_is_locked_and_reseed_does_not_overwrite(self):
        a = AnnualAssignment.objects.get(department__code="CSE", kra__number=1)
        a.target_text = "999"
        with self.assertRaises(ValidationError):
            a.save()
        AnnualAssignment.objects.filter(pk=a.pk).update(target_text="5")  # simulate a historic value differing from seed
        err = io.StringIO()
        call_command("seed_catalogue", stdout=io.StringIO(), stderr=err)
        self.assertEqual(AnnualAssignment.objects.get(pk=a.pk).target_text, "5")
        self.assertIn("kept", err.getvalue())
        self.assertEqual(AnnualAssignment.objects.count(), 585)

    def test_old_snapshot_unchanged_after_catalogue_edit(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.complete_and_submit(a, sid)
        self.asg_a.kra.activity_text = "changed later"
        self.asg_a.kra.save()
        rev = SubmissionRevision.objects.get(submission_id=sid)
        self.assertTrue(rev.snapshot["kra"]["activity_text"].startswith("KRA 33:"))
