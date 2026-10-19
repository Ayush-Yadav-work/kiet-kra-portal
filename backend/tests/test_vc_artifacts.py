"""VC Phase 2 — durable approved-PDF artifacts (plan v2.3 §9.1, D-076). The renderer is either unreachable or mocked:
approval must never need it, and the worker's PDF must come from the frozen approval snapshot."""
import io
from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import override_settings

from apps.audit.errors import ApiError
from apps.reports import artifacts
from apps.reports.models import ApprovalArtifact, GeneratedDocument, WorkerHeartbeat
from apps.submissions.models import ReviewDecision
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1, 10)
FAKE = b"%PDF-1.7 synthetic approved artifact %%EOF"
DOWN = "http://127.0.0.1:9"  # nothing listens here: the renderer is "down"


def fake_renderer(seen):
    def call(parts):
        seen.append(parts["footer"])
        return FAKE + str(len(seen)).encode() + b"\n%%EOF"
    return call


@override_settings(RENDERER_URL=DOWN, ARTIFACT_BACKOFF_SECONDS=10, ARTIFACT_MAX_ATTEMPTS=3, ARTIFACT_LEASE_SECONDS=60)
class ArtifactTests(PortalTestCase):
    def approved(self):
        a, vc = self.client_for(self.dean_a), self.client_for(self.vc)
        sid = self.open_draft(a, self.asg_a, self.p2)
        rev = self.complete_and_submit(a, sid)["current_revision"]["id"]
        r = vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)  # renderer down: the approval still succeeds
        return sid, rev, vc, a

    def test_approval_queues_job_and_download_shows_processing_until_worker_runs(self):
        with frozen(NOW):
            sid, rev, vc, a = self.approved()
            job = ApprovalArtifact.objects.get()
            self.assertEqual((job.state, str(job.revision_id), job.reviewer_name, job.attempts), ("PENDING", rev, "t.vc", 0))
            r = vc.get(f"/api/v1/submissions/{sid}/export/", HTTP_ACCEPT="application/json")
            self.assertEqual((r.status_code, r.json()["code"], r["Retry-After"]), (202, "pdf_processing", "5"))
            r = a.get(f"/api/v1/submissions/{sid}/export/?inline=1")  # browser tab: bounded self-refreshing page
            self.assertEqual(r.status_code, 202)
            self.assertIn(b'http-equiv="refresh"', r.content)
            self.assertIn(b"wait=1", r.content)
            r = a.get(f"/api/v1/submissions/{sid}/export/?inline=1&wait=24")
            self.assertNotIn(b"http-equiv", r.content)  # polling stops; the page offers Try again
            self.assertFalse(GeneratedDocument.objects.exists())  # never a Pending-approval PDF in its place
            seen = []
            with mock.patch("apps.reports.pdf.call_renderer", fake_renderer(seen)):
                done = artifacts.run_one("w1")
            self.assertEqual(done.state, "READY")
            self.assertIn("Verified by VC - t.vc", seen[0])
            r = a.get(f"/api/v1/submissions/{sid}/export/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(b"".join(r.streaming_content), FAKE + b"1\n%%EOF")

    def test_later_return_and_rename_never_rewrite_the_artifact(self):
        with frozen(NOW):
            sid, rev, vc, a = self.approved()
            self.vc.first_name = "Renamed VC"
            self.vc.save()
            vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "RETURN", "reason": "fix"}, format="json")
            seen = []
            with mock.patch("apps.reports.pdf.call_renderer", fake_renderer(seen)):
                artifacts.run_one("w1")  # rendered after the return and the rename
            self.assertIn("Verified by VC - t.vc", seen[0])
            self.assertNotIn("Renamed", seen[0])
            self.assertNotIn("Historical", seen[0])
            r = a.get(f"/api/v1/submissions/{sid}/export/?revision={rev}")  # the approved revision keeps its original PDF
            self.assertEqual(b"".join(r.streaming_content), FAKE + b"1\n%%EOF")
            self.assertEqual(ApprovalArtifact.objects.count(), 1)

    def test_retry_backoff_failure_and_operator_retry(self):
        with frozen(NOW):
            sid, *_ = self.approved()
        down = mock.patch("apps.reports.pdf.call_renderer", side_effect=ApiError(503, "pdf_unavailable", "down"))
        with down:
            with frozen(NOW):
                job = artifacts.run_one("w1")
                self.assertEqual((job.state, job.attempts), ("PENDING", 1))
                self.assertEqual(job.next_attempt_at, NOW + timedelta(seconds=10))
                self.assertIsNone(artifacts.run_one("w1"))  # not due yet
            with frozen(NOW + timedelta(seconds=11)):
                self.assertEqual(artifacts.run_one("w1").next_attempt_at, NOW + timedelta(seconds=31))  # 20 s backoff
            with frozen(NOW + timedelta(seconds=40)):
                job = artifacts.run_one("w1")
        self.assertEqual((job.state, job.attempts), ("FAILED", 3))
        self.assertIn("pdf_unavailable", job.last_error)
        with frozen(NOW + timedelta(minutes=5)):
            self.assertIsNone(artifacts.run_one("w1"))  # bounded: never retried automatically
            r = self.client_for(self.dean_a).get(f"/api/v1/submissions/{sid}/export/", HTTP_ACCEPT="application/json")
            self.assertEqual((r.status_code, r.json()["code"]), (503, "pdf_failed"))
            out = io.StringIO()
            call_command("artifact_jobs", "--retry-failed", stdout=out)
            self.assertIn("requeued 1", out.getvalue())
            with mock.patch("apps.reports.pdf.call_renderer", fake_renderer([])):
                self.assertEqual(artifacts.run_one("w1").state, "READY")

    def test_lease_recovery_duplicate_consumers_and_graceful_release(self):
        with frozen(NOW):
            self.approved()
            job = artifacts.claim("w1")
            self.assertIsNone(artifacts.claim("w2"))  # leased: a second consumer gets nothing
            artifacts.release(job, "w1")  # graceful shutdown gives it back without spending the attempt
            job.refresh_from_db()
            self.assertEqual((job.state, job.attempts), ("PENDING", 0))
            job = artifacts.claim("w1")  # w1 then "crashes" mid-render
        with frozen(NOW + timedelta(seconds=61)):
            stolen = artifacts.claim("w2")  # lease expired: recovered by another worker
            self.assertEqual((stolen.pk, stolen.attempts), (job.pk, 2))
            folder = artifacts.read_path("approved/" + "0" * 32 + ".pdf").parent
            files = lambda: set(folder.glob("*.pdf")) if folder.exists() else set()
            before = files()
            late = artifacts.finish(job, "w1", data=FAKE)  # the crashed worker's late result is discarded
            self.assertEqual((late.state, late.lease_owner), ("RUNNING", "w2"))
            self.assertEqual(files(), before)  # its file was removed, nothing published
            with mock.patch("apps.reports.pdf.call_renderer", fake_renderer([])):
                done = artifacts.process(stolen, "w2")
        self.assertEqual(done.state, "READY")
        self.assertEqual(len(files() - before), 1)

    def test_worker_command_heartbeat_and_health(self):
        vc = self.client_for(self.vc)
        with frozen(NOW):
            self.approved()
            r = vc.get("/health/artifacts/")
            self.assertEqual((r.status_code, r.json()["problems"]), (503, ["no_live_worker"]))
            with mock.patch("apps.reports.pdf.call_renderer", fake_renderer([])):
                call_command("run_artifact_worker", "--once", stdout=io.StringIO())
            self.assertEqual(ApprovalArtifact.objects.get().state, "READY")
            beat = WorkerHeartbeat.objects.get()
            self.assertEqual(beat.processed, 1)
            self.assertIsNotNone(beat.stopped_at)  # a stopped worker is not "live"
            artifacts.beat("live", NOW)
            self.assertEqual(vc.get("/health/artifacts/").json(), {"ok": True, "problems": [], "live_workers": 1, "pending": 0,
                                                                   "failed": 0, "oldest_pending_seconds": 0})

    def test_legacy_approval_without_artifact_gets_job_or_reuses_retained_pdf(self):
        with frozen(NOW):
            sid, rev, vc, a = self.approved()
            ApprovalArtifact.objects.all().delete()  # as if approved before D-076
            d = ReviewDecision.objects.get()
            artifacts.write_bytes("generated/" + "a" * 32 + ".pdf", FAKE)
            GeneratedDocument.objects.create(submission_id=sid, revision_id=rev, content_hash="h" * 64, status_snapshot="APPROVED",
                                             verification_label="Verified by VC - t.vc", renderer_version="old",
                                             storage_key="generated/" + "a" * 32 + ".pdf", bytes=len(FAKE))
            r = a.get(f"/api/v1/submissions/{sid}/export/")
            self.assertEqual(b"".join(r.streaming_content), FAKE)  # retained file served, nothing re-rendered
            art = ApprovalArtifact.objects.get(decision=d)
            self.assertEqual((art.state, art.renderer_version), ("READY", "old"))

    def test_quick_preview_is_html_only_and_works_with_renderer_down(self):
        with frozen(NOW):
            a, vc = self.client_for(self.dean_a), self.client_for(self.vc)
            sid = self.open_draft(a, self.asg_a, self.p2)
            rev = self.complete_and_submit(a, sid)["current_revision"]["id"]
            with mock.patch("apps.reports.pdf.call_renderer") as renderer:
                for _ in range(5):  # rapid switching: every request is plain HTML of the exact revision
                    r = vc.post(f"/api/v1/submissions/{sid}/preview/", {"revision": rev}, format="json")
                    self.assertEqual(r.status_code, 200)
                    self.assertIn("Pending approval", r.json()["html"])
                renderer.assert_not_called()
            self.assertFalse(GeneratedDocument.objects.exists())
            self.assertFalse(ApprovalArtifact.objects.exists())
