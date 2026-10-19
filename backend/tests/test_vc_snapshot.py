"""VC Phase 1 — analytics snapshot boundary with REAL transactions (plan v2.3 §8.1): TransactionTestCase, committed
fixtures, ATOMIC_REQUESTS, nested-caller refusal, concurrent writer between reads, connection state afterwards, API and
export consistency. SYNTHETIC data only."""
import csv
import io
import threading
from unittest import mock

from django.core.management import call_command
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from apps.catalogue.models import AcademicYear, AnnualAssignment, Department, ReportingPeriod
from apps.submissions import analytics
from apps.submissions.models import Submission
from tests.base import TEST_STORAGE, PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1)


@override_settings(SESSION_COOKIE_AGE=10**8, PRIVATE_STORAGE_ROOT=TEST_STORAGE)
class SnapshotTests(TransactionTestCase):
    client_for = PortalTestCase.client_for

    def setUp(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        cse = Department.objects.get(code="CSE")
        self.vc = PortalTestCase.make_user("t.vc", "VC")
        self.dean = PortalTestCase.make_user("t.dean.cse", "DEAN", cse)
        self.p1 = ReportingPeriod.objects.get(year__label="2026-27", index=1)
        self.asg = AnnualAssignment.objects.get(department=cse, kra__number=33, year__label="2026-27")
        self.sub = Submission.objects.create(assignment=self.asg, period=self.p1, status="SUBMITTED", edit_version=2, created_by=self.dean)
        self.f = {"year": AcademicYear.objects.get(label="2026-27"), "scope": "ytd", "period": None, "departments": ["CSE", "ECE"],
                  "kras": [], "status": "", "page": 1, "page_size": 50}

    def test_api_exports_and_request_transaction_settings(self):
        v = self.client_for(self.vc)
        q = "/api/v1/analytics/?year=2026-27&scope=ytd&department=CSE&department=ECE"
        with frozen(NOW):
            r = v.get(q)
            self.assertEqual(r.status_code, 200, r.content)
            body = r.json()
            self.assertEqual((body["summary"]["expected"], body["summary"]["approved"], body["breakdown"]["AWAITING_REVIEW"]), (180, 0, 1))
            self.assertEqual((body["details"]["total"], len(body["details"]["results"]), r["Cache-Control"]), (180, 50, "private, no-store"))
            with mock.patch.dict(connection.settings_dict, {"ATOMIC_REQUESTS": True}):  # request-wide transactions enabled
                self.assertEqual(v.get(q).json()["summary"], body["summary"])  # the view still owns its snapshot
            c = v.get(q.replace("/analytics/", "/analytics/export/") + "&kind=csv")
            rows = list(csv.reader(io.StringIO(c.content.decode("utf-8-sig"))))
            self.assertEqual((len(rows) - 1, c["Cache-Control"]), (180, "private, no-store"))
            captured = {}
            with mock.patch("apps.submissions.analytics_views.call_renderer", side_effect=lambda parts: captured.update(parts) or b"%PDF-1.4 x\n%%EOF"):
                p = v.get(q.replace("/analytics/", "/analytics/export/") + "&kind=pdf")
            self.assertEqual((p.status_code, p["Content-Type"]), (200, "application/pdf"))
            html = captured["html"]
            self.assertIn("0 of 180 reports approved", html)
            self.assertNotIn("<script", html.lower())  # static, script-free charts
            self.assertNotIn("http://", html)
            self.assertEqual(html.count("<tr><td>CSE</td><td class=\"num\">"), 90)  # every filtered detail row, not one page
            with mock.patch("apps.submissions.analytics.MAX_EXPORT_ROWS", 10):
                big = v.get(q.replace("/analytics/", "/analytics/export/") + "&kind=csv")
            self.assertEqual((big.status_code, big.json()["code"]), (400, "too_many_rows"))  # refused, never truncated
            dean = self.client_for(self.dean)
            for path in ("/api/v1/analytics/?year=2026-27", "/api/v1/analytics/export/?year=2026-27&kind=csv"):
                self.assertEqual(dean.get(path).status_code, 403)
                self.assertIn(self.client_class().get(path).status_code, (401, 403))

    def test_reader_owns_transaction_and_leaves_connection_clean(self):
        with self.assertRaises(analytics.SnapshotError), transaction.atomic():
            analytics.read_snapshot(lambda: 1)  # never silently downgraded inside a caller's transaction
        self.assertEqual(analytics.read_snapshot(lambda: Submission.objects.count()), 1)
        with self.assertRaises(ValueError):
            analytics.read_snapshot(lambda: (_ for _ in ()).throw(ValueError("boom")))
        with connection.cursor() as c:  # isolation/read-only were transaction-scoped
            c.execute("SHOW transaction_isolation")
            self.assertEqual(c.fetchone()[0], "read committed")
            c.execute("SHOW transaction_read_only")
            self.assertEqual(c.fetchone()[0], "off")
        Submission.objects.filter(pk=self.sub.pk).update(remarks="writes still work")
        self.assertEqual(Submission.objects.get(pk=self.sub.pk).remarks, "writes still work")

    def test_concurrent_approval_between_reads_is_not_seen(self):
        def approve_elsewhere():  # a separate connection commits an approval after the first dataset read
            def run():
                try:
                    Submission.objects.filter(pk=self.sub.pk).update(status="APPROVED")
                finally:
                    connections.close_all()
            t = threading.Thread(target=run)
            t.start(); t.join()
        with frozen(NOW):
            first = analytics.dataset(self.f, NOW, between=approve_elsewhere)
            after = analytics.dataset(self.f, NOW)
        self.assertEqual((first["summary"]["approved"], first["breakdown"]["AWAITING_REVIEW"]), (0, 1))  # one consistent snapshot
        self.assertEqual((after["summary"]["approved"], after["breakdown"]["AWAITING_REVIEW"]), (1, 0))  # committed change visible next time
        self.assertEqual(Submission.objects.get(pk=self.sub.pk).status, "APPROVED")
