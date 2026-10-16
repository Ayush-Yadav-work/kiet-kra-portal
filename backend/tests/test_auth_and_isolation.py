from django.core.cache import cache
from rest_framework.test import APIClient

from tests.base import PASSWORD, PortalTestCase, frozen, ist


class LoginPortalTests(PortalTestCase):
    def setUp(self):
        cache.clear()

    def login(self, client, portal, username, password=PASSWORD):
        return client.post(f"/api/v1/auth/{portal}/login/", {"username": username, "password": password}, format="json")

    def test_correct_role_login_succeeds_and_me_matches(self):
        c = APIClient()
        r = self.login(c, "dean", "t.dean.cse")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "DEAN")
        self.assertEqual(r.json()["department"]["code"], "CSE")
        self.assertEqual(c.get("/api/v1/auth/me/").json()["username"], "t.dean.cse")

    def test_opposite_role_rejected_without_session(self):
        c = APIClient()
        r = self.login(c, "vc", "t.dean.cse")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "invalid_credentials")
        self.assertEqual(c.get("/api/v1/auth/me/").status_code, 401)
        r = self.login(c, "dean", "t.vc")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("sessionid", c.cookies)

    def test_generic_error_for_wrong_password_and_unknown_user(self):
        a = self.login(APIClient(), "dean", "t.dean.cse", "wrong-pass").json()["message"]
        b = self.login(APIClient(), "dean", "nobody").json()["message"]
        self.assertEqual(a, b)

    def test_existing_session_for_other_portal_is_not_switched(self):
        c = APIClient()
        self.login(c, "dean", "t.dean.cse")
        r = self.login(c, "vc", "t.vc")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(c.get("/api/v1/auth/me/").json()["role"], "DEAN")

    def test_cross_role_api_denied(self):
        dean, vc = self.client_for(self.dean_a), self.client_for(self.vc)
        self.assertEqual(dean.get("/api/v1/progress/?year=2026-27&period=%d" % self.p2.id).status_code, 403)
        self.assertEqual(dean.get("/api/v1/reopen-requests/").status_code, 200)  # own scope only
        self.assertEqual(vc.get("/api/v1/reopen-grants/active/").status_code, 403)
        self.assertEqual(APIClient().get("/api/v1/assignments/").status_code, 401)

    def test_inactive_user_denied(self):
        self.dean_b.is_active = False
        self.dean_b.save()
        self.assertEqual(self.login(APIClient(), "dean", "t.dean.ece").status_code, 400)

    def test_rate_limit_after_failures(self):
        c = APIClient()
        for _ in range(5):
            self.login(c, "dean", "t.dean.cse", "bad")
        self.assertEqual(self.login(c, "dean", "t.dean.cse").status_code, 429)

    def test_must_change_password_blocks_api_until_changed(self):
        self.dean_a.must_change_password = True
        self.dean_a.save()
        c = APIClient()
        self.login(c, "dean", "t.dean.cse")
        r = c.get("/api/v1/assignments/")
        self.assertEqual((r.status_code, r.json()["code"]), (403, "password_change_required"))
        r = c.post("/api/v1/auth/change-password/", {"current_password": PASSWORD, "new_password": "short"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = c.post("/api/v1/auth/change-password/", {"current_password": PASSWORD, "new_password": "A-much-better-pass-2026"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/v1/assignments/").status_code, 200)

    def test_logout_ends_session(self):
        c = APIClient()
        self.login(c, "vc", "t.vc")
        c.post("/api/v1/auth/logout/")
        self.assertEqual(c.get("/api/v1/auth/me/").status_code, 401)

    def test_csrf_enforced_on_unsafe_requests(self):
        c = APIClient(enforce_csrf_checks=True)
        c.get("/api/v1/auth/csrf/")
        r = c.post("/api/v1/auth/dean/login/", {"username": "t.dean.cse", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 403)
        token = c.cookies["csrftoken"].value
        r = c.post("/api/v1/auth/dean/login/", {"username": "t.dean.cse", "password": PASSWORD}, format="json",
                   HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)


class DepartmentIsolationTests(PortalTestCase):
    def test_dean_cannot_read_write_export_or_download_other_department(self):
        a, b, vc = self.client_for(self.dean_a), self.client_for(self.dean_b), self.client_for(self.vc)
        with frozen(ist(2026, 10, 1)):
            sid_b = self.open_draft(b, self.asg_b, self.p2)
            self.add_required_evidence(b, sid_b)
            ev_id = b.get(f"/api/v1/submissions/{sid_b}/evidence/").json()["results"][0]["id"]
            for method, url, body in [
                ("get", f"/api/v1/submissions/{sid_b}/", None),
                ("patch", f"/api/v1/submissions/{sid_b}/draft/", {"edit_version": 0, "remarks": "x"}),
                ("post", f"/api/v1/submissions/{sid_b}/preview/", {}),
                ("get", f"/api/v1/submissions/{sid_b}/export/", None),
                ("post", f"/api/v1/submissions/{sid_b}/submit/", {"edit_version": 0}),
                ("get", f"/api/v1/submissions/{sid_b}/evidence/", None),
                ("post", f"/api/v1/submissions/{sid_b}/evidence/", {"source_type": "DRIVE_LINK"}),
                ("get", f"/api/v1/submissions/{sid_b}/history/", None),
                ("post", f"/api/v1/submissions/{sid_b}/reopen-requests/", {"reason": "x"}),
                ("delete", f"/api/v1/evidence/{ev_id}/", None),
                ("get", f"/api/v1/evidence/{ev_id}/download/", None),
                ("get", f"/api/v1/assignments/{self.asg_b.id}/periods/{self.p2.id}/", None),
                ("post", f"/api/v1/assignments/{self.asg_b.id}/periods/{self.p2.id}/", None),
            ]:
                r = getattr(a, method)(url, body, format="json") if body is not None else getattr(a, method)(url)
                self.assertEqual(r.status_code, 404, f"{method} {url} -> {r.status_code}")
            # Lists are scoped: Dean A never sees ECE rows.
            rows = a.get("/api/v1/assignments/?year=2026-27").json()["results"]
            self.assertEqual({r["department"]["code"] for r in rows}, {"CSE"})
            self.assertEqual(len(rows), 45)
            self.assertEqual(a.get("/api/v1/departments/").json(), [{"code": "CSE", "name": self.cse.name}])
            # The VC sees both departments' records.
            self.assertEqual(vc.get(f"/api/v1/submissions/{sid_b}/").status_code, 200)
            self.assertEqual(len(vc.get("/api/v1/assignments/?year=2026-27").json()["results"]), 585)

    def test_malformed_ids_are_404(self):
        a = self.client_for(self.dean_a)
        self.assertEqual(a.get("/api/v1/submissions/not-a-uuid/").status_code, 404)
        self.assertEqual(a.get("/api/v1/submissions/00000000-0000-0000-0000-000000000000/").status_code, 404)

    def test_vc_cannot_edit_or_submit(self):
        vc, a = self.client_for(self.vc), self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.assertEqual(self.save(vc, sid, 0, remarks="vc").status_code, 403)
            self.assertEqual(vc.post(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p2.id}/").status_code, 403)
