"""Shared test setup. Uses the real PostgreSQL test database and the real seed command. SYNTHETIC users only."""
import atexit
import datetime
import io
import shutil
import tempfile
from contextlib import contextmanager
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.catalogue.models import AnnualAssignment, Department, ReportingPeriod

IST = ZoneInfo("Asia/Kolkata")
PASSWORD = "Synthetic-Test-Pass-91"
# Uploaded evidence and generated PDFs from tests go to a throwaway folder, never the working .work/private (Phase 6A).
TEST_STORAGE = tempfile.mkdtemp(prefix="kra_test_private_")
atexit.register(shutil.rmtree, TEST_STORAGE, ignore_errors=True)


def ist(*args):
    return datetime.datetime(*args, tzinfo=IST)


@contextmanager
def frozen(at):
    with mock.patch("django.utils.timezone.now", return_value=at):
        yield


@override_settings(SESSION_COOKIE_AGE=10**8, PRIVATE_STORAGE_ROOT=TEST_STORAGE)  # sessions must survive frozen far-future clocks
class PortalTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalogue", stdout=io.StringIO())
        cls.cse, cls.ece = Department.objects.get(code="CSE"), Department.objects.get(code="ECE")
        cls.vc = cls.make_user("t.vc", "VC")
        cls.dean_a = cls.make_user("t.dean.cse", "DEAN", cls.cse)
        cls.dean_b = cls.make_user("t.dean.ece", "DEAN", cls.ece)
        cls.asg_a = AnnualAssignment.objects.get(department=cls.cse, kra__number=33, year__label="2026-27")
        cls.asg_b = AnnualAssignment.objects.get(department=cls.ece, kra__number=33, year__label="2026-27")
        cls.p1 = ReportingPeriod.objects.get(year__label="2026-27", index=1)  # Jul 1 - Sep 1 2026
        cls.p2 = ReportingPeriod.objects.get(year__label="2026-27", index=2)  # Sep 1 - Nov 1 2026

    @staticmethod
    def make_user(username, role, dept=None):
        u = User(username=username, role=role, department=dept, first_name=username, must_change_password=False)
        u.set_password(PASSWORD)
        u.save()
        return u

    def client_for(self, user):
        c = APIClient()
        c.force_login(user)  # real Django session, same as the portal login
        return c

    # --- workflow helpers (all via the HTTP API) ---
    def open_draft(self, client, asg, period):
        r = client.post(f"/api/v1/assignments/{asg.id}/periods/{period.id}/")
        assert r.status_code in (200, 201), r.content
        return r.json()["submission_id"]

    def finalise(self, client, year, drafts, start=None):
        """VC selective finalisation (VC Phase 1): preview, then confirm with the returned token. Drafts must be fresh."""
        items = [{"id": str(d.id), "edit_version": d.edit_version} for d in drafts]
        pv = client.post(f"/api/v1/admin/years/{year}/finalise/preview/", {"items": items, "start": start}, format="json")
        if pv.status_code != 200:
            return pv
        return client.post(f"/api/v1/admin/years/{year}/finalise/", {"token": pv.json()["token"]}, format="json")

    def detail(self, client, sid):
        return client.get(f"/api/v1/submissions/{sid}/").json()

    def save(self, client, sid, version, **changes):
        return client.patch(f"/api/v1/submissions/{sid}/draft/", {"edit_version": version, **changes}, format="json")

    def add_required_evidence(self, client, sid):
        for cat in ("Event Notice/Invitation", "Attendance Sheet", "Photographs"):
            r = client.post(f"/api/v1/submissions/{sid}/evidence/", {
                "source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/file/d/synthetic", "category": cat,
                "label": f"Synthetic {cat}"}, format="json")
            assert r.status_code == 201, r.content

    def complete_and_submit(self, client, sid):
        from tests.fixtures import kra33_payload

        v = self.detail(client, sid)["edit_version"]
        r = self.save(client, sid, v, payload=kra33_payload(), achievement_text="1 event (synthetic)")
        assert r.status_code == 200, r.content
        self.add_required_evidence(client, sid)
        r = client.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": r.json()["edit_version"]}, format="json")
        assert r.status_code == 200, r.content
        return r.json()
