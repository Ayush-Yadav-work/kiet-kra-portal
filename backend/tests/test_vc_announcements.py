"""VC Phase 2 — announcements (plan v2.3 §10, D-077): audience isolation, unread semantics, pinning, expiry, withdrawal,
stale reads and the pending-departments shortcut."""
from datetime import timedelta

from django.test import TransactionTestCase, override_settings

from apps.catalogue.models import AnnualAssignment, ReportingPeriod
from apps.submissions.models import ReopenGrant, Submission

from tests.base import TEST_STORAGE, PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1, 10)
API = "/api/v1/announcements/"


class Helpers:
    def setUp(self):
        self.v, self.a, self.b = (PortalTestCase.client_for(self, u) for u in (self.vc, self.dean_a, self.dean_b))

    def create(self, audience=None, **kw):
        body = {"title": "Synthetic notice", "body": "Line one\nhttps://example.org/info", "audience": audience or {"all": True}, **kw}
        r = self.v.post(API, body, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def publish(self, n, **kw):
        r = self.v.post(f"{API}{n['id']}/publish/", {"edit_version": n["edit_version"], **kw}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def patch(self, n, **changes):
        r = self.v.patch(f"{API}{n['id']}/", {"edit_version": n["edit_version"], **changes}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def inbox(self, client):
        return client.get(API).json()

    def read(self, client, n, version=None):
        return client.post(f"{API}{n['id']}/read/", {"content_version": version or n["content_version"]}, format="json")


class AnnouncementTests(Helpers, PortalTestCase):
    def test_audience_isolation_and_draft_invisibility(self):
        with frozen(NOW):
            draft = self.create({"departments": ["CSE"]})
            self.assertEqual(self.inbox(self.a)["total"], 0)  # drafts are invisible
            self.assertEqual(self.a.get(f"{API}{draft['id']}/").status_code, 404)
            cse = self.publish(draft)
            every = self.publish(self.create())
            self.assertEqual(cse["recipients"], ["CSE"])
            self.assertEqual(len(every["recipients"]), 13)  # all departments resolved to a snapshot at publication
            self.assertEqual({x["id"] for x in self.inbox(self.a)["results"]}, {cse["id"], every["id"]})
            self.assertEqual([x["id"] for x in self.inbox(self.b)["results"]], [every["id"]])
            for path in ("", "revisions/"):  # ECE cannot reach the CSE-only notice by URL, nor its history
                self.assertEqual(self.b.get(f"{API}{cse['id']}/{path}").status_code, 404)
            self.assertEqual(self.read(self.b, cse).status_code, 404)
            self.assertEqual(self.a.post(API, {"title": "x", "body": "y", "audience": {"all": True}}, format="json").status_code, 403)
            self.assertEqual(self.a.post(f"{API}{cse['id']}/publish/", {}, format="json").status_code, 403)
            self.assertNotIn("recipients", self.a.get(f"{API}{cse['id']}/").json())  # Deans never see the audience

    def test_unread_semantics_content_vs_metadata_and_readd(self):
        with frozen(NOW):
            n = self.publish(self.create({"departments": ["CSE"]}))
            self.assertEqual(self.inbox(self.a)["unread_count"], 1)
            self.a.get(f"{API}{n['id']}/")
            self.assertEqual(self.inbox(self.a)["unread_count"], 1)  # loading the list/detail never marks it read
            self.assertEqual(self.read(self.a, n).json()["unread_count"], 0)
        with frozen(NOW + timedelta(minutes=1)):
            n = self.patch(n, pinned=True)
            n = self.patch(n, expires_at="2026-12-31")
            n = self.patch(n, audience={"departments": ["CSE", "ECE"]})
            self.assertEqual(self.inbox(self.a)["unread_count"], 0)  # pin/expiry/audience edits keep CSE's read state
            self.assertEqual(self.inbox(self.b)["unread_count"], 1)  # newly added ECE starts unread
        with frozen(NOW + timedelta(minutes=2)):
            n = self.patch(n, body="Changed text")
            n = self.patch(n, title="Changed title")
            self.assertEqual(n["content_version"], 3)
            self.assertEqual(self.inbox(self.a)["unread_count"], 1)  # content changes: unread again, counted once
            stale = self.read(self.a, n, version=2)
            self.assertEqual((stale.status_code, stale.json()["code"]), (409, "stale_read"))
            self.assertEqual(self.inbox(self.a)["unread_count"], 1)  # the unseen version was not marked read
            self.read(self.a, n)
            self.assertTrue(self.inbox(self.a)["results"][0]["updated"])
        with frozen(NOW + timedelta(minutes=3)):
            n = self.patch(n, audience={"departments": ["ECE"]})
            self.assertEqual(self.a.get(f"{API}{n['id']}/").status_code, 404)  # removed: no access, even by URL
            self.assertEqual(self.a.get(f"{API}{n['id']}/revisions/").status_code, 404)
        with frozen(NOW + timedelta(minutes=4)):
            n = self.patch(n, audience={"departments": ["CSE", "ECE"]})
            self.assertEqual(self.inbox(self.a)["unread_count"], 1)  # re-added: a new membership starts unread
            history = self.v.get(f"{API}{n['id']}/revisions/").json()["results"]
            self.assertEqual([h["audience"] for h in history][-3:], [["CSE", "ECE"], ["ECE"], ["CSE", "ECE"]])

    def test_pinned_order_expiry_withdrawal_and_conflicts(self):
        with frozen(NOW):
            old = self.publish(self.create(title="Older pinned", pinned=True, expires_at="2026-10-02T09:00"))
        with frozen(NOW + timedelta(minutes=5)):
            new = self.publish(self.create(title="Newer"))
            self.assertEqual([x["title"] for x in self.inbox(self.a)["results"]], ["Older pinned", "Newer"])
            r = self.v.patch(f"{API}{new['id']}/", {"edit_version": 0, "pinned": True}, format="json")
            self.assertEqual(r.json()["code"], "version_conflict")  # a stale tab cannot overwrite
        with frozen(ist(2026, 10, 2, 9, 1)):
            self.assertEqual([x["title"] for x in self.inbox(self.a)["results"]], ["Newer"])  # pinning never bypasses expiry
            self.assertEqual(self.a.get(f"{API}{old['id']}/").status_code, 404)
            self.assertEqual(self.v.get(f"{API}?state=EXPIRED").json()["total"], 1)  # VC keeps history
            w = self.v.post(f"{API}{new['id']}/withdraw/", {"edit_version": new["edit_version"]}, format="json").json()
            self.assertEqual(w["state"], "WITHDRAWN")
            self.assertEqual(self.inbox(self.a)["unread_count"], 0)
            self.assertEqual(self.read(self.a, new).status_code, 404)
            self.assertEqual(self.v.patch(f"{API}{new['id']}/", {"edit_version": w["edit_version"], "title": "x"}, format="json").status_code, 409)
            self.assertEqual(self.v.delete(f"{API}{new['id']}/", {"edit_version": w["edit_version"]}, format="json").json()["code"], "not_draft")
            d = self.create()
            self.assertEqual(self.v.delete(f"{API}{d['id']}/", {"edit_version": 0}, format="json").status_code, 204)

    def test_plain_text_only_and_validation(self):
        with frozen(NOW):
            for field, value in (("body", "<script>alert(1)</script>"), ("title", "<b>x</b>"), ("body", "see javascript:alert(1)"),
                                 ("body", "ftp://files.example.org/x")):
                r = self.v.post(API, {"title": "t", "body": "b", "audience": {"all": True}, field: value}, format="json")
                self.assertEqual(r.status_code, 400, value)
            r = self.v.post(API, {"title": "t", "body": "b", "audience": {"departments": ["NOPE"]}}, format="json")
            self.assertEqual(r.status_code, 400)
            r = self.v.post(API, {"title": "t", "body": "b", "audience": {"all": True}, "expires_at": "2026-09-01"}, format="json")
            self.assertEqual(r.json()["field_errors"], {"expires_at": ["The expiry must be in the future."]})
            n = self.publish(self.create(body="Use 5 < 6 & quotes \"ok\""))  # stored exactly; escaped by the UI
            self.assertEqual(self.a.get(f"{API}{n['id']}/").json()["body"], 'Use 5 < 6 & quotes "ok"')



@override_settings(PRIVATE_STORAGE_ROOT=TEST_STORAGE)
class PendingShortcutTests(Helpers, TransactionTestCase):
    """The shortcut reads the analytics snapshot, which must own its transaction (so not inside TestCase)."""

    make_user = staticmethod(PortalTestCase.make_user)

    def setUp(self):
        PortalTestCase.setUpTestData.__func__(type(self))
        super().setUp()

    def test_pending_departments_shortcut_requires_review(self):
        with frozen(NOW):
            # KRA 33 in P1 (closed): CSE has an approved report, ECE nothing -> ECE pending; ME rejected -> pending
            Submission.objects.create(assignment=self.asg_a, period=self.p1, status="APPROVED", created_by=self.dean_a)
            me = AnnualAssignment.objects.get(year=self.p2.year, kra__number=33, department__code="ME")
            Submission.objects.create(assignment=me, period=self.p1, status="REJECTED", created_by=self.dean_a)
            grants = ReopenGrant.objects.count()
            body = {"year": "2026-27", "period_ids": [self.p1.id], "kras": [33], "departments": ["CSE", "ECE", "ME"]}
            pv = self.v.post(f"{API}pending-draft/", {**body, "preview": True}, format="json").json()
            self.assertEqual(pv["eligible"], ["ECE", "ME"])
            r = self.v.post(f"{API}pending-draft/", body, format="json")
            self.assertEqual(r.status_code, 201, r.content)
            d = r.json()
            self.assertEqual((d["state"], d["audience"]["departments"]), ("DRAFT", ["ECE", "ME"]))  # a draft, not a publication
            self.assertIn("does not reopen", d["body"])
            self.assertEqual(self.inbox(self.b)["total"], 0)
            future = self.v.post(f"{API}pending-draft/", {**body, "period_ids": [ReportingPeriod.objects.get(year=self.p1.year, index=3).id]}, format="json")
            self.assertEqual(future.status_code, 400)  # only opened periods
            Submission.objects.filter(assignment=me).update(status="APPROVED")  # ME no longer pending
            r = self.v.post(f"{API}{d['id']}/publish/", {"edit_version": d["edit_version"]}, format="json")
            self.assertEqual((r.status_code, r.json()["code"], r.json()["no_longer_pending"]), (409, "eligibility_changed", ["ME"]))
            d = self.patch(d, audience={"departments": ["ECE"]})  # the VC reviews the recipients
            n = self.publish(d)
            self.assertEqual(n["recipients"], ["ECE"])
            self.assertEqual(ReopenGrant.objects.count(), grants)  # no reopening, no deadline change
            self.assertEqual(self.inbox(self.b)["unread_count"], 1)
            self.assertEqual(self.inbox(self.a)["total"], 0)
