"""Audit Batch A (2026-10-24): shared atomic login throttling (H1), Drive-link ports (L1), CSV formula cells (L2).
SYNTHETIC users and data only; Django's isolated test database."""
import csv
import io
import os
import subprocess
import sys
import threading
from datetime import timedelta
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import Client, TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts import throttle
from apps.accounts.models import LoginThrottle
from apps.catalogue.models import AnnualAssignment, Department, ReportingPeriod
from apps.evidence.services import is_drive_url
from apps.submissions.analytics_views import cell
from tests.base import PASSWORD, PortalTestCase, frozen, ist

BAD = "Synthetic-Wrong-Pass-0"


def login(client, username, password, portal="dean"):
    return client.post(f"/api/v1/auth/{portal}/login/", {"username": username, "password": password}, content_type="application/json")


class ThrottleTests(PortalTestCase):
    def test_limits_reset_and_release(self):
        c = Client()
        with frozen(ist(2026, 10, 1, 10)):
            for _ in range(5):
                self.assertEqual(login(c, "t.dean.cse", BAD).status_code, 400)
            self.assertEqual(login(c, "t.dean.cse", PASSWORD).status_code, 429)  # the correct password is not even checked
            self.assertEqual(login(Client(), "t.dean.ece", PASSWORD).status_code, 200)  # other accounts unaffected
        with frozen(ist(2026, 10, 1, 10, 16)):  # 15-minute fixed window has ended
            self.assertEqual(login(Client(), "t.dean.cse", PASSWORD).status_code, 200)
            self.assertFalse(LoginThrottle.objects.filter(key="loginfail:DEAN:t.dean.cse").exists())  # success clears the account
            ip = LoginThrottle.objects.get(key="loginfail-ip:127.0.0.1")
            self.assertEqual(ip.count, 0)  # a success gives its IP slot back: only failures accumulate

    def test_ip_limit_spans_usernames_and_roles(self):
        with frozen(ist(2026, 10, 1, 10)):
            for i in range(20):
                self.assertEqual(login(Client(), f"nobody{i}", BAD, "dean" if i % 2 else "vc").status_code, 400)
            self.assertEqual(login(Client(), "t.dean.cse", PASSWORD).status_code, 429)
            other_ip = Client(REMOTE_ADDR="10.0.0.9")
            self.assertEqual(login(other_ip, "t.dean.cse", PASSWORD).status_code, 200)

    def test_store_unavailable_fails_closed(self):
        with mock.patch("apps.accounts.throttle.reserve", side_effect=DatabaseError("synthetic outage")), \
                mock.patch("apps.accounts.views.authenticate") as auth:
            r = login(Client(), "t.dean.cse", PASSWORD)
        self.assertEqual((r.status_code, r.json()["code"]), (503, "login_unavailable"))
        auth.assert_not_called()  # no password is checked without the shared counter

    def test_no_process_local_state(self):
        from apps.accounts import views
        self.assertFalse(hasattr(views, "cache"))  # the old LocMemCache path is gone, not merely unused


class SharedThrottleTests(TransactionTestCase):
    """Committed rows, separate connections and separate OS processes: what multiple web workers would see."""

    def setUp(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        self.dean = PortalTestCase.make_user("t.dean.cse", "DEAN", Department.objects.get(code="CSE"))

    def test_concurrent_reservations_are_atomic(self):
        results, barrier = [], threading.Barrier(12)

        def worker():
            try:
                barrier.wait()
                results.append(throttle.reserve("synthetic:concurrent", 900))
            finally:
                connection.close()
        threads = [threading.Thread(target=worker) for _ in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), list(range(1, 13)))  # no lost update: every attempt got its own slot

    def test_concurrent_wrong_passwords_never_exceed_the_limit(self):
        statuses, barrier = [], threading.Barrier(12)
        real = __import__("django.contrib.auth", fromlist=["authenticate"]).authenticate
        checked = []

        def counting(*a, **k):
            checked.append(1)
            return real(*a, **k)

        def worker():
            try:
                barrier.wait()
                statuses.append(login(Client(), "t.dean.cse", BAD).status_code)
            finally:
                connection.close()
        with mock.patch("apps.accounts.views.authenticate", side_effect=counting):
            threads = [threading.Thread(target=worker) for _ in range(12)]
            [t.start() for t in threads]
            [t.join() for t in threads]
        self.assertEqual(sorted(statuses), [400] * 5 + [429] * 7)
        self.assertEqual(len(checked), 5)  # at most MAX_USER_FAILS password checks, however concurrent

    def test_separate_processes_share_the_counter_and_it_survives_restart(self):
        """Each subprocess is a fresh Python/Django process (a separate web worker, or the same worker after a
        restart) pointed at this test database."""
        db = connection.settings_dict
        url = f"postgresql://{quote(db['USER'])}:{quote(db['PASSWORD'] or '')}@{db['HOST']}:{db['PORT']}/{db['NAME']}"
        env = {**os.environ, "DATABASE_URL": url, "DJANGO_ALLOWED_HOSTS": "testserver", "DJANGO_DEBUG": "1"}
        script = ("import sys,json;from django.test import Client;c=Client();"
                  "print(','.join(str(c.post('/api/v1/auth/dean/login/',{'username':'t.dean.cse','password':p},"
                  "content_type='application/json').status_code) for p in sys.argv[1:]))")

        def worker(*passwords):
            r = subprocess.run([sys.executable, str(Path(settings.BASE_DIR) / "manage.py"), "shell", "-c",
                                f"import sys; sys.argv=['x', *{list(passwords)!r}]; exec({script!r})"],
                               env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            return r.stdout.strip().splitlines()[-1]
        self.assertEqual(worker(BAD, BAD, BAD), "400,400,400")  # worker 1
        self.assertEqual(worker(BAD, BAD), "400,400")  # worker 2 (or worker 1 restarted): continues the same count
        self.assertEqual(worker(PASSWORD), "429")  # worker 3: blocked although its own process never saw a failure
        self.assertEqual(LoginThrottle.objects.get(key="loginfail:DEAN:t.dean.cse").count, 6)


class DriveLinkTests(PortalTestCase):
    def test_url_rules(self):
        ok = ("https://drive.google.com/file/d/abc/view", "https://docs.google.com/document/d/abc/edit",
              "https://drive.google.com:443/file/d/abc", "HTTPS://DRIVE.GOOGLE.COM/file/d/abc")
        bad = ("https://drive.google.com:8443/file/d/abc", "https://drive.google.com:0/x", "https://drive.google.com:99999/x",
               "https://drive.google.com:abc/x", "https://drive.google.com:-1/x", "http://drive.google.com/file/d/abc",
               "https://user@drive.google.com/x", "https://user:pw@drive.google.com/x", "https://:pw@drive.google.com/x",
               "https://drive.google.com.evil.example/x", "https://evil.example/drive.google.com", "javascript:alert(1)",
               "data:text/html,x", "https://drive.google.com/" + "a" * 1000, "")
        for u in ok:
            self.assertTrue(is_drive_url(u), u)
        for u in bad:
            self.assertFalse(is_drive_url(u), u)

    def test_api_create_path(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1, 10)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            post = lambda u: a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": u,
                                                                               "category": "Photographs", "label": "x"}, format="json")
            self.assertEqual(post("https://drive.google.com:443/file/d/abc").status_code, 201)
            self.assertEqual(post("https://drive.google.com/file/d/abc").status_code, 201)
            for u in ("https://drive.google.com:8443/file/d/abc", "https://drive.google.com:99999/x", "https://u:p@drive.google.com/x"):
                r = post(u)
                self.assertEqual((r.status_code, r.json()["field_errors"]), (400, {"drive_url": ["Not a Google Drive link."]}), u)


class CsvCellTests(PortalTestCase):
    def test_cell_neutralises_hidden_triggers(self):
        for v in ("=1+1", "+1", "-1", "@SUM(A1)", "\t=1", "\r=1", " =1+1", "  @x", "\n=1", "\x00=1", "\x0b+1",
                  " =1", "　-1", "﻿=1", "​@x", " \t\r\n=HYPERLINK(\"http://x\",\"y\")"):
            self.assertEqual(cell(v), "'" + v, repr(v))
        for v in ("Plain text", "a=b", "3 events, 2 workshops", 'He said "yes"', "line1\nline2", "", None, 33, "1-2 days", "e-mail"):
            self.assertEqual(cell(v), "" if v is None else str(v), repr(v))

    def test_csv_quoting_still_applies_after_neutralising(self):
        buf = io.StringIO()
        row = [cell(v) for v in (' =1,2', '"=x"', "a,b", "x\n=y", 'say "hi"')]
        csv.writer(buf).writerow(row)
        back = next(csv.reader(io.StringIO(buf.getvalue())))
        self.assertEqual(back, ["' =1,2", '"=x"', "a,b", "x\n=y", 'say "hi"'])  # round-trips; only the formula cell is prefixed


class CsvExportTests(TransactionTestCase):
    """The real analytics CSV (its reader owns a transaction, so this runs outside TestCase)."""

    def setUp(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        ece = Department.objects.get(code="ECE")
        self.vc = PortalTestCase.make_user("t.vc", "VC")
        self.dean = PortalTestCase.make_user("t.dean.ece", "DEAN", ece)
        self.p2 = ReportingPeriod.objects.get(year__label="2026-27", index=2)
        self.ece = ece

    def test_export_neutralises_and_keeps_stored_values(self):
        d, v = APIClient(), APIClient()
        d.force_login(self.dean)
        v.force_login(self.vc)
        values = {34: " =HYPERLINK(\"http://x\",\"y\")", 35: "\t@SUM(1,2)", 36: "Plain, with \"quotes\"\nand a newline"}
        with frozen(ist(2026, 10, 1, 10)):
            for n, text in values.items():
                asg = AnnualAssignment.objects.get(department=self.ece, kra__number=n, year__label="2026-27")
                sid = d.post(f"/api/v1/assignments/{asg.id}/periods/{self.p2.id}/").json()["submission_id"]
                d.patch(f"/api/v1/submissions/{sid}/draft/", {"edit_version": 0, "is_nil": True, "nil_reason": "x",
                                                               "achievement_text": text}, format="json")
                self.assertEqual(d.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 1}, format="json").status_code, 200)
                rev = v.get(f"/api/v1/submissions/{sid}/").json()["current_revision"]["id"]
                self.assertEqual(v.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json").status_code, 200)
            r = v.get("/api/v1/analytics/export/", {"year": "2026-27", "scope": "ytd", "kind": "csv", "department": "ECE"})
        self.assertEqual(r.status_code, 200)
        rows = {row[1]: row for row in csv.reader(io.StringIO(r.content.decode("utf-8-sig"))) if row[1] in ("34", "35", "36")}
        self.assertEqual(rows["34"][6], "'" + values[34])
        self.assertEqual(rows["35"][6], "'" + values[35])
        self.assertEqual(rows["36"][6], values[36])  # ordinary text untouched (commas/quotes/newlines via CSV quoting)
        from apps.submissions.models import Submission
        self.assertEqual(Submission.objects.get(assignment__kra__number=34, assignment__department=self.ece).achievement_text, values[34])
