"""Phase 6A — permission sweep, nested scope, workflow transitions/deadlines and real concurrent requests. SYNTHETIC data only."""
import datetime
import io
import re
import threading
import time
import uuid
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from rest_framework.permissions import AllowAny
from rest_framework.test import APIClient

from apps.accounts.auth import IsVC
from apps.audit.models import AuditEvent
from apps.catalogue.models import AnnualAssignment, Department, ReportingPeriod
from apps.evidence.models import Evidence
from apps.submissions.models import ReopenGrant, ReopenRequest, ReviewDecision, Submission, SubmissionRevision
from config.urls import api
from tests.base import TEST_STORAGE, PortalTestCase, frozen, ist
from tests.fixtures import kra33_payload

PDF = b"%PDF-1.4\n% synthetic\n" + b"0" * 2000
OCT1 = ist(2026, 10, 1)
VC_ONLY = {"submissions/<uuid:pk>/review/", "reopen-requests/<uuid:pk>/decision/", "progress/", "progress/export/",
           "admin/templates/", "admin/kras/", "admin/years/", "admin/years/<str:label>/copy/",
           "admin/years/<str:label>/finalize/", "admin/drafts/", "admin/drafts/<uuid:pk>/"}


def routes():
    """(route pattern, view class, HTTP methods it implements) for every API endpoint."""
    for p in api:
        view = p.callback.view_class
        yield str(p.pattern), view, [m for m in ("get", "post", "patch", "delete") if hasattr(view, m)]


def fill(pattern, **ids):
    return "/api/v1/" + re.sub(r"<(\w+):(\w+)>", lambda m: str(ids.get(m.group(2), {"uuid": uuid.uuid4(), "int": 1,
                                                                                      "str": "2026-27"}[m.group(1)])), pattern)


def call(client, method, url, body=None):
    return getattr(client, method)(url, body or {}, format="json") if method != "get" else client.get(url)


class PermissionSweepTests(PortalTestCase):
    def test_anonymous_is_refused_on_every_protected_route(self):
        anon = APIClient()
        checked = 0
        for pattern, view, methods in routes():
            if view.permission_classes == [AllowAny]:
                continue  # csrf, login, logout
            for m in methods:
                r = call(anon, m, fill(pattern))
                self.assertIn(r.status_code, (401, 403), f"{m} {pattern} -> {r.status_code}")
                checked += 1
        self.assertGreater(checked, 35)

    def test_dean_refused_on_every_vc_only_route(self):
        found = {p for p, view, _ in routes() if view.permission_classes == [IsVC]}
        self.assertEqual(found, VC_ONLY)  # a new VC route must be added here deliberately
        d = self.client_for(self.dean_a)
        with frozen(OCT1):
            sid = self.open_draft(d, self.asg_a, self.p2)
            for pattern, _, methods in routes():
                if pattern in VC_ONLY:
                    for m in methods:
                        r = call(d, m, fill(pattern, pk=sid))
                        self.assertEqual(r.status_code, 403, f"{m} {pattern}")
        self.assertFalse(AuditEvent.objects.filter(actor=self.dean_a, action__startswith="review").exists())

    def test_vc_refused_on_dean_only_actions(self):
        a, vc = self.client_for(self.dean_a), self.client_for(self.vc)
        with frozen(OCT1):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.add_required_evidence(a, sid)
            ev = a.get(f"/api/v1/submissions/{sid}/evidence/").json()["results"][0]["id"]
            for m, url in (("patch", f"submissions/{sid}/draft/"), ("post", f"submissions/{sid}/validate/"),
                           ("post", f"submissions/{sid}/submit/"), ("post", f"submissions/{sid}/reopen-requests/"),
                           ("post", f"submissions/{sid}/evidence/"), ("delete", f"evidence/{ev}/"),
                           ("get", "reopen-grants/active/"),
                           ("post", f"assignments/{self.asg_a.id}/periods/{self.p2.id}/"),
                           ("post", f"assignments/{self.asg_a.id}/periods/{self.p2.id}/reopen-requests/")):
                self.assertEqual(call(vc, m, "/api/v1/" + url, {"edit_version": 1}).status_code, 403, f"{m} {url}")
        self.assertEqual(Evidence.objects.filter(removed=True).count(), 0)


class NestedScopeTests(PortalTestCase):
    def test_foreign_revision_period_and_requests_hidden(self):
        a, b = self.client_for(self.dean_a), self.client_for(self.dean_b)
        with frozen(OCT1):
            sid_a = self.open_draft(a, self.asg_a, self.p2)
            sid_b = self.open_draft(b, self.asg_b, self.p2)
            rev_b = self.complete_and_submit(b, sid_b)["current_revision"]["id"]
            # own submission + another department's revision id
            self.assertEqual(a.post(f"/api/v1/submissions/{sid_a}/preview/", {"revision": rev_b}, format="json").status_code, 404)
            self.assertEqual(a.get(f"/api/v1/submissions/{sid_a}/export/?revision={rev_b}").status_code, 404)
            # own assignment + a period of another year
            other = ReportingPeriod.objects.filter(year__label="2027-28").first()
            for m in ("get", "post"):
                self.assertEqual(call(a, m, f"/api/v1/assignments/{self.asg_a.id}/periods/{other.id}/").status_code, 404)
        with frozen(ist(2026, 11, 5)):
            self.assertEqual(a.post(f"/api/v1/assignments/{self.asg_b.id}/periods/{self.p2.id}/reopen-requests/",
                                    {"reason": "x"}, format="json").status_code, 404)
            self.assertEqual(self.client_for(self.vc).post(f"/api/v1/submissions/{sid_b}/review/", {
                "revision": rev_b, "decision": "REJECT", "reason": "Synthetic"}, format="json").status_code, 200)
            self.assertEqual(b.post(f"/api/v1/submissions/{sid_b}/reopen-requests/", {"reason": "Synthetic"},
                                    format="json").status_code, 201)
            self.assertEqual(a.get("/api/v1/reopen-requests/").json(), [])
            self.assertEqual(len(b.get("/api/v1/reopen-requests/").json()), 1)

    def test_private_storage_is_not_served_by_url(self):
        a = self.client_for(self.dean_a)
        with frozen(OCT1):
            sid = self.open_draft(a, self.asg_a, self.p2)
            r = a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs",
                       "label": "Synthetic", "file": SimpleUploadedFile("p.pdf", PDF, "application/pdf")}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("storage_key", r.json())  # the server path is never sent to clients
        key = Evidence.objects.get(pk=r.json()["id"]).storage_key
        for prefix in ("/", "/media/", "/static/", "/private/", "/.work/private/", "/api/v1/"):
            for c in (APIClient(), a):
                self.assertEqual(c.get(prefix + key).status_code, 404, prefix)
        self.assertEqual(a.get(f"/api/v1/evidence/{r.json()['id']}/download/").status_code, 200)  # only the guarded route

    def test_report_export_is_not_cacheable(self):
        a = self.client_for(self.dean_a)
        with frozen(OCT1), mock.patch("apps.reports.pdf.call_renderer", return_value=b"%PDF-1.4 synthetic"):
            sid = self.open_draft(a, self.asg_a, self.p2)
            r = a.get(f"/api/v1/submissions/{sid}/export/")
        self.assertEqual((r.status_code, r["Cache-Control"]), (200, "private, no-store"))


class TransitionAndDeadlineTests(PortalTestCase):
    def review(self, sid, rev, decision, reason="", at=ist(2026, 10, 2), grant=False):
        with frozen(at):
            return self.client_for(self.vc).post(f"/api/v1/submissions/{sid}/review/", {
                "revision": rev, "decision": decision, "reason": reason, "grant_reopen": grant}, format="json")

    def prepared(self):
        """Complete CSE KRA 33 P2 draft (not submitted) -> (client, sid, edit_version)."""
        a = self.client_for(self.dean_a)
        with frozen(OCT1):
            sid = self.open_draft(a, self.asg_a, self.p2)
            v = self.save(a, sid, 0, payload=kra33_payload(), achievement_text="1 event (synthetic)").json()["edit_version"]
            self.add_required_evidence(a, sid)
        return a, sid, v

    def submit(self, a, sid, v, at):
        with frozen(at):
            return a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json")

    def test_submit_at_exact_close_refused_one_microsecond_before_accepted(self):
        a, sid, v = self.prepared()
        close = self.p2.closes_at
        self.assertEqual(self.submit(a, sid, v, close).json()["code"], "window_closed")
        self.assertEqual(self.submit(a, sid, v, close + datetime.timedelta(hours=5, minutes=30)).json()["code"], "window_closed")
        self.assertEqual(self.submit(a, sid, v, close - datetime.timedelta(microseconds=1)).status_code, 200)
        # IST rule: 1 Nov 2026 00:00 IST is 31 Oct 18:30 UTC, so a UTC "still 31 October" moment is already closed.
        self.assertEqual(close, datetime.datetime(2026, 10, 31, 18, 30, tzinfo=datetime.timezone.utc))

    def test_status_transition_matrix(self):
        a, sid, v = self.prepared()
        rev = self.submit(a, sid, v, OCT1).json()["current_revision"]["id"]
        self.assertEqual(self.review(sid, rev, "RETURN", "x").json()["code"], "invalid_state")    # Submitted -> Return
        self.assertEqual(self.review(sid, rev, "LOST", "x").status_code, 400)
        self.assertEqual(self.review(sid, rev, "REJECT", "   ").status_code, 400)                 # blank reason
        self.assertEqual(self.review(sid, rev, "APPROVE").status_code, 200)
        self.assertEqual(self.review(sid, rev, "APPROVE").json()["code"], "invalid_state")        # double approve
        self.assertEqual(self.review(sid, rev, "REJECT", "x").json()["code"], "invalid_state")    # Approved -> Reject
        self.assertEqual(self.review(sid, rev, "RETURN").status_code, 400)                        # reason required
        self.assertEqual(self.review(sid, rev, "RETURN", "Correct dates").status_code, 200)
        self.assertEqual(self.review(sid, rev, "APPROVE").json()["code"], "invalid_state")        # Rejected -> Approve
        self.assertEqual(sorted(ReviewDecision.objects.values_list("decision", flat=True)), ["APPROVE", "RETURN"])

    def test_locked_after_submission_and_approval_stale_tabs_refused(self):
        a, sid, v = self.prepared()
        ev = a.get(f"/api/v1/submissions/{sid}/evidence/").json()["results"][0]["id"]
        rev = self.submit(a, sid, v, OCT1).json()["current_revision"]["id"]
        for at, step in ((ist(2026, 10, 2), None), (ist(2026, 10, 3), "APPROVE")):
            if step:
                self.assertEqual(self.review(sid, rev, step).status_code, 200)
            with frozen(at):
                self.assertEqual(self.save(a, sid, v, remarks="stale tab").json()["code"], "not_editable")
                self.assertEqual(a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json").status_code, 409)
                self.assertEqual(a.delete(f"/api/v1/evidence/{ev}/").json()["code"], "not_editable")
                self.assertEqual(a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "category": "Photographs",
                                 "label": "late", "drive_url": "https://drive.google.com/x"}, format="json").status_code, 409)
        r = SubmissionRevision.objects.get(pk=rev)
        self.assertEqual((r.remarks, len(r.evidence_manifest)), ("", 3))
        self.assertEqual(Evidence.objects.filter(submission_id=sid).count(), 3)

    def test_historical_revision_labels_after_reject_resubmit_approve(self):
        a, sid, v = self.prepared()
        rev1 = self.submit(a, sid, v, OCT1).json()["current_revision"]["id"]
        self.review(sid, rev1, "REJECT", "Synthetic: fix")
        with frozen(ist(2026, 10, 3)):
            v = self.save(a, sid, self.detail(a, sid)["edit_version"], achievement_text="2 events (synthetic)").json()["edit_version"]
        rev2 = self.submit(a, sid, v, ist(2026, 10, 3)).json()["current_revision"]["id"]
        self.assertEqual(self.review(sid, rev1, "APPROVE", at=ist(2026, 10, 4)).json()["code"], "stale_revision")  # old VC tab
        self.review(sid, rev2, "APPROVE", at=ist(2026, 10, 4))
        seen = []
        vc = self.client_for(self.vc)
        with mock.patch("apps.reports.pdf.call_renderer", side_effect=lambda p: seen.append(p["html"]) or b"%PDF-1.4 s"):
            for q in (f"?revision={rev1}", f"?revision={rev2}", ""):
                self.assertEqual(vc.get(f"/api/v1/submissions/{sid}/export/{q}").status_code, 200)
        self.assertIn("Historical revision 1: not approved", seen[0])
        self.assertIn("1 event (synthetic)", seen[0])
        self.assertIn("Verified by VC", seen[1])
        self.assertIn("2 events (synthetic)", seen[1])
        self.assertEqual(len(seen), 2)  # current export is the identical approved document, reused from cache
        self.assertEqual(SubmissionRevision.objects.get(pk=rev1).achievement_text, "1 event (synthetic)")

    def test_request_grant_exactly_72h_and_scoped_to_one_report(self):
        a = self.client_for(self.dean_a)
        other = AnnualAssignment.objects.get(department=self.cse, kra__number=20, year__label="2026-27")
        with frozen(ist(2026, 8, 1)):
            sid_p1 = self.open_draft(a, self.asg_a, self.p1)
        with frozen(OCT1):
            sid_other = self.open_draft(a, other, self.p2)
        with frozen(ist(2026, 11, 5)):
            r = a.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p2.id}/reopen-requests/", {"reason": "Synthetic"}, format="json")
            self.assertEqual(r.status_code, 201)
        t = ist(2026, 11, 6, 15, 17, 3)
        with frozen(t):
            g = self.client_for(self.vc).post(f"/api/v1/reopen-requests/{r.json()['id']}/decision/", {"approve": True},
                                              format="json").json()["grant"]
        sid = r.json()["submission_id"]
        grant = ReopenGrant.objects.get(pk=g["id"])
        self.assertEqual(grant.expires_at - grant.starts_at, datetime.timedelta(hours=72))
        self.assertEqual(grant.starts_at, t)
        with frozen(t + datetime.timedelta(hours=72) - datetime.timedelta(microseconds=1)):
            self.assertEqual(self.save(a, sid, 0, remarks="in grant").status_code, 200)
            for other_sid in (sid_p1, sid_other):  # same department, other period / other KRA: still closed
                self.assertEqual(self.save(a, other_sid, 0, remarks="x").json()["code"], "window_closed")
            self.assertEqual(self.save(self.client_for(self.dean_b), sid, 1, remarks="x").status_code, 404)
        with frozen(t + datetime.timedelta(hours=72)):
            self.assertEqual(self.save(a, sid, 1, remarks="after").json()["code"], "window_closed")
            self.assertEqual(a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "category": "Photographs",
                             "label": "late", "drive_url": "https://drive.google.com/x"}, format="json").status_code, 409)


    def test_reopen_request_refused_for_a_period_that_has_not_started(self):
        """Defect found in Phase 6A: only `is_open` was checked, so a future period accepted a request (and a grant)."""
        p5 = ReportingPeriod.objects.get(year__label="2026-27", index=5)
        a = self.client_for(self.dean_a)
        with frozen(OCT1):
            r = a.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{p5.id}/reopen-requests/", {"reason": "x"}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "period_open"))
        self.assertFalse(Submission.objects.filter(period=p5).exists())  # the row creation is rolled back
        self.assertFalse(ReopenRequest.objects.exists())

# ---------------------------------------------------------------- real concurrent requests (PostgreSQL row locks)

@override_settings(SESSION_COOKIE_AGE=10**8, PRIVATE_STORAGE_ROOT=TEST_STORAGE)
class ConcurrencyTests(TransactionTestCase):
    """Each request runs in its own thread and database connection. Where possible the test holds the contended row lock
    until every request is provably waiting on it (pg_stat_activity), then releases it, so the requests truly collide."""

    open_draft, detail, save, add_required_evidence, complete_and_submit, client_for = (
        PortalTestCase.open_draft, PortalTestCase.detail, PortalTestCase.save, PortalTestCase.add_required_evidence,
        PortalTestCase.complete_and_submit, PortalTestCase.client_for)

    def setUp(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        cse = Department.objects.get(code="CSE")
        self.vc = PortalTestCase.make_user("t.vc", "VC")
        self.dean = PortalTestCase.make_user("t.dean.cse", "DEAN", cse)
        self.asg = AnnualAssignment.objects.get(department=cse, kra__number=33, year__label="2026-27")
        self.p2 = ReportingPeriod.objects.get(year__label="2026-27", index=2)
        self.a = self.client_for(self.dean)
        patcher = mock.patch("django.utils.timezone.now", return_value=OCT1)  # process-wide: threads share the clock
        self.clock = patcher.start()
        self.addCleanup(patcher.stop)

    def race(self, calls, lock=None):
        """Run calls concurrently; with lock=(model, pk) hold that row until all calls wait on it. Returns responses."""
        out, errors = [None] * len(calls), []
        go = threading.Barrier(len(calls) + 1)

        def run(i, fn):
            try:
                go.wait()
                out[i] = fn()
            except Exception as e:  # surfaced below
                errors.append(e)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(calls)]
        if lock:
            with transaction.atomic():
                lock[0].objects.select_for_update().get(pk=lock[1])
                [t.start() for t in threads]
                go.wait()
                self.wait_for_lock_waiters(len(calls))
        else:
            [t.start() for t in threads]
            go.wait()
        [t.join(30) for t in threads]
        self.assertEqual(errors, [])
        return out

    def wait_for_lock_waiters(self, n):
        with connection.cursor() as c:
            for _ in range(200):
                c.execute("SELECT pg_stat_clear_snapshot()")
                c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND wait_event_type = 'Lock'")
                if c.fetchone()[0] >= n:
                    return
                time.sleep(0.05)
        self.fail(f"requests did not reach the row lock ({n} expected)")

    def submit_call(self, sid, v):
        return lambda: self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json")

    def prepared(self):
        sid = self.open_draft(self.a, self.asg, self.p2)
        v = self.save(self.a, sid, 0, payload=kra33_payload(), achievement_text="1 event (synthetic)").json()["edit_version"]
        self.add_required_evidence(self.a, sid)
        return sid, v

    def codes(self, responses):
        return sorted(r.status_code for r in responses)

    def test_duplicate_submit_creates_one_revision(self):
        sid, v = self.prepared()
        rs = self.race([self.submit_call(sid, v)] * 3, lock=(Submission, sid))
        self.assertEqual(self.codes(rs), [200, 409, 409])
        self.assertEqual(SubmissionRevision.objects.filter(submission_id=sid).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(action="submitted").count(), 1)

    def test_autosave_versus_submit(self):
        sid, v = self.prepared()
        save = lambda: self.save(self.a, sid, v, achievement_text="autosave text")
        r_save, r_sub = self.race([save, self.submit_call(sid, v)], lock=(Submission, sid))
        self.assertEqual(self.codes([r_save, r_sub]), [200, 409])
        sub = Submission.objects.get(pk=sid)
        if r_sub.status_code == 200:  # submit first: the late autosave must not alter the submitted report
            self.assertEqual(r_save.json()["code"], "not_editable")
            self.assertEqual((sub.status, sub.achievement_text, sub.current_revision.achievement_text),
                             ("SUBMITTED", "1 event (synthetic)", "1 event (synthetic)"))
        else:  # autosave first: the submit carried a stale version and must not submit unseen text
            self.assertEqual(r_sub.json()["code"], "version_conflict")
            self.assertEqual((sub.status, sub.achievement_text, sub.current_revision_id), ("DRAFT", "autosave text", None))

    def test_evidence_upload_and_removal_versus_submit(self):
        sid, v = self.prepared()
        keep = Evidence.objects.filter(submission_id=sid).order_by("uploaded_at").first()
        extra = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "category": "Photographs",
                            "label": "extra", "drive_url": "https://drive.google.com/extra"}, format="json")
        self.assertEqual(extra.status_code, 201, extra.content)
        upload = lambda: self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs",
                                     "label": "racing upload", "file": SimpleUploadedFile("r.pdf", PDF, "application/pdf")},
                                     format="multipart")
        remove = lambda: self.a.delete(f"/api/v1/evidence/{extra.json()['id']}/")
        r_up, r_rm, r_sub = self.race([upload, remove, self.submit_call(sid, v)], lock=(Submission, sid))
        self.assertEqual(r_sub.status_code, 200, r_sub.content)
        manifest = {e["id"] for e in SubmissionRevision.objects.get(submission_id=sid).evidence_manifest}
        active = set(Evidence.objects.filter(submission_id=sid, removed=False).values_list("id", flat=True))
        self.assertEqual(manifest, {str(i) for i in active})  # the submitted manifest is exactly the active evidence
        self.assertIn(str(keep.id), manifest)
        self.assertIn(r_up.status_code, (201, 409))
        self.assertIn(r_rm.status_code, (200, 409))
        self.assertEqual(r_up.status_code == 201, Evidence.objects.filter(label="racing upload").exists())
        self.assertEqual(r_rm.status_code == 200, extra.json()["id"] not in manifest)

    def test_competing_vc_decisions(self):
        sid, v = self.prepared()
        rev = self.submit_call(sid, v)().json()["current_revision"]["id"]
        vc1, vc2 = self.client_for(self.vc), self.client_for(self.vc)
        approve = lambda: vc1.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json")
        reject = lambda: vc2.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "REJECT",
                                                                          "reason": "Synthetic"}, format="json")
        r_ap, r_rj = self.race([approve, reject], lock=(Submission, sid))
        self.assertEqual(self.codes([r_ap, r_rj]), [200, 409])
        decisions = list(ReviewDecision.objects.values_list("decision", flat=True))
        self.assertEqual(len(decisions), 1)
        self.assertEqual(Submission.objects.get(pk=sid).status, "APPROVED" if decisions == ["APPROVE"] else "REJECTED")
        self.assertEqual(AuditEvent.objects.filter(action__startswith="review_").count(), 1)

    def test_double_reopen_decision_and_double_request(self):
        self.clock.return_value = ist(2026, 11, 5)
        url = f"/api/v1/assignments/{self.asg.id}/periods/{self.p2.id}/reopen-requests/"
        ask = lambda: self.a.post(url, {"reason": "Synthetic"}, format="json")
        rs = self.race([ask, ask])  # no row exists yet (C2): both race to create it
        self.assertEqual(self.codes(rs), [201, 409])
        self.assertEqual((Submission.objects.count(), ReopenRequest.objects.count()), (1, 1))
        req = ReopenRequest.objects.get()
        vc1, vc2 = self.client_for(self.vc), self.client_for(self.vc)
        decide = lambda c: lambda: c.post(f"/api/v1/reopen-requests/{req.id}/decision/", {"approve": True}, format="json")
        rs = self.race([decide(vc1), decide(vc2)], lock=(ReopenRequest, req.id))
        self.assertEqual(self.codes(rs), [200, 409])
        self.assertEqual(ReopenGrant.objects.count(), 1)
