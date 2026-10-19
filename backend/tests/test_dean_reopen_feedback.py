"""Dean feedback on reopening decisions: a denial (with its reason) is returned to the Dean on the dashboard rows and the
workspace detail, a later request supersedes it without losing history, other departments cannot see it, and a denial
changes nothing else (no grant, status, target or C11 classification)."""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.catalogue.models import AnnualAssignment
from apps.submissions.models import ReopenGrant, Submission
from tests.base import PortalTestCase, frozen, ist

OCT1 = ist(2026, 10, 1)  # P1 closed, P2 open
REASON = 'Window closed on time <b>"no"</b> & no exception'


class DenialFeedbackTests(PortalTestCase):
    def setUp(self):
        self.a, self.b, self.v = self.client_for(self.dean_a), self.client_for(self.dean_b), self.client_for(self.vc)

    def request(self, reason="Missed the deadline (synthetic)"):
        r = self.a.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p1.id}/reopen-requests/", {"reason": reason}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()["id"]

    def decide(self, rid, approve, reason=""):
        return self.v.post(f"/api/v1/reopen-requests/{rid}/decision/", {"approve": approve, "reason": reason}, format="json")

    def row(self, client=None, asg=None):
        rows = (client or self.a).get(f"/api/v1/assignments/?year=2026-27&period={self.p1.id}").json()["results"]
        return next(r for r in rows if r["id"] == str((asg or self.asg_a).id))

    def test_denial_reason_visible_on_dashboard_and_workspace_and_nothing_else_changes(self):
        with frozen(OCT1):
            rid = self.request()
            self.assertEqual(self.decide(rid, False, "   ").json()["field_errors"], {"reason": ["Required."]})  # blank refused
            sub = Submission.objects.get(assignment=self.asg_a, period=self.p1)
            before = (sub.status, sub.edit_version, self.row()["submission"]["display_status"], self.asg_a.target_text)
            self.assertEqual(self.decide(rid, False, REASON).status_code, 200)
            q = self.row()["latest_reopen_request"]
            self.assertEqual((q["id"], q["state"], q["decision_reason"], q["kra_number"], q["period"]),
                             (rid, "DENIED", REASON, 33, self.p1.label))  # exact text; the UI escapes it
            self.assertIsNotNone(q["decided_at"])
            detail = self.a.get(f"/api/v1/submissions/{sub.id}/").json()
            self.assertEqual([(r["state"], r["decision_reason"]) for r in detail["reopen_requests"]], [("DENIED", REASON)])
            self.assertTrue(detail["can_request_reopen"])  # asking again is still allowed (rules unchanged)
            sub.refresh_from_db()
            self.asg_a.refresh_from_db()
            self.assertEqual((sub.status, sub.edit_version, self.row()["submission"]["display_status"], self.asg_a.target_text), before)
            self.assertFalse(ReopenGrant.objects.exists())  # a denial grants nothing
            self.assertIsNone(detail["active_grant"])

    def test_later_request_supersedes_denial_but_history_keeps_it(self):
        with frozen(OCT1):
            first = self.request("first")
            self.decide(first, False, "Denied once")
        with frozen(OCT1.replace(hour=12)):
            second = self.request("second")
            self.assertEqual(self.row()["latest_reopen_request"]["state"], "PENDING")  # the old denial is not the current state
            self.assertEqual(self.decide(second, True).status_code, 200)
            self.assertEqual(self.row()["latest_reopen_request"]["state"], "APPROVED")
            sub = Submission.objects.get(assignment=self.asg_a, period=self.p1)
            history = self.a.get(f"/api/v1/submissions/{sub.id}/").json()["reopen_requests"]
            self.assertEqual([(r["id"], r["state"]) for r in history], [(second, "APPROVED"), (first, "DENIED")])  # newest first
            self.assertEqual(history[1]["decision_reason"], "Denied once")

    def test_other_department_cannot_see_request_or_reason(self):
        with frozen(OCT1):
            rid = self.request()
            self.decide(rid, False, REASON)
            sub = Submission.objects.get(assignment=self.asg_a, period=self.p1)
            self.assertEqual(self.b.get(f"/api/v1/submissions/{sub.id}/").status_code, 404)
            self.assertNotIn(rid, [r["id"] for r in self.b.get("/api/v1/reopen-requests/").json()])
            ece_rows = self.b.get(f"/api/v1/assignments/?year=2026-27&period={self.p1.id}").json()["results"]
            self.assertNotIn(str(self.asg_a.id), [r["id"] for r in ece_rows])
            self.assertTrue(all(r["latest_reopen_request"] is None for r in ece_rows))

    def test_dashboard_query_count_does_not_grow_with_requests(self):
        with frozen(OCT1):
            self.request()
            with CaptureQueriesContext(connection) as one:
                self.row()
            for kra in (1, 2, 3):
                asg = AnnualAssignment.objects.get(year__label="2026-27", department=self.cse, kra__number=kra)
                self.a.post(f"/api/v1/assignments/{asg.id}/periods/{self.p1.id}/reopen-requests/", {"reason": "x"}, format="json")
            with CaptureQueriesContext(connection) as four:
                self.row()
        self.assertEqual(len(four), len(one))  # no per-row request queries
