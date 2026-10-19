"""VC Phase 2 — the real worker process (D-076): consumes a committed job automatically, survives being killed mid-render
(the lease expires and a restarted worker finishes it), and writes to the shared private storage. A tiny local HTTP
server stands in for the renderer so the test does not depend on Chromium."""
import io
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase

from apps.catalogue.models import AnnualAssignment, Department, ReportingPeriod
from apps.reports.models import ApprovalArtifact, WorkerHeartbeat
from apps.submissions import services as svc
from apps.submissions.models import Submission, SubmissionRevision
from tests.base import PortalTestCase, ist

FAKE = b"%PDF-1.7\nsynthetic worker output\n%%EOF"


class FakeRenderer(BaseHTTPRequestHandler):
    delay = 0.0
    calls = 0

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).calls += 1
        time.sleep(type(self).delay)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.end_headers()
        self.wfile.write(FAKE)

    def log_message(self, *a):
        pass


class WorkerProcessTests(TransactionTestCase):
    def setUp(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        self.vc = PortalTestCase.make_user("t.vc", "VC")
        dean = PortalTestCase.make_user("t.dean", "DEAN", Department.objects.get(code="CSE"))
        p1 = ReportingPeriod.objects.get(year__label="2026-27", index=1)
        a = AnnualAssignment.objects.get(year=p1.year, department__code="CSE", kra__number=33)
        s = Submission.objects.create(assignment=a, period=p1, status="SUBMITTED", is_nil=True, nil_reason="Synthetic", created_by=dean)
        rev = SubmissionRevision.objects.create(submission=s, sequence=1, payload={}, is_nil=True, nil_reason="Synthetic",
                                                snapshot=svc.snapshot_of(s), evidence_manifest=[], manifest_hash="h",
                                                submitted_by=dean, submitted_at=ist(2026, 10, 1))
        s.current_revision = rev
        s.save()
        self.sub, self.rev = s, rev
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeRenderer)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.storage = tempfile.mkdtemp(prefix="kra_worker_storage_")
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
                p.wait()
        self.server.shutdown()

    def worker(self, lease=60):
        db = connection.settings_dict
        url = f"postgresql://{quote(db['USER'])}:{quote(db['PASSWORD'] or '')}@{db['HOST'] or '127.0.0.1'}:{db['PORT'] or 5432}/{db['NAME']}"
        env = {**os.environ, "DATABASE_URL": url, "RENDERER_URL": f"http://127.0.0.1:{self.server.server_address[1]}",
               "PRIVATE_STORAGE_ROOT": self.storage, "ARTIFACT_POLL_SECONDS": "0.2", "ARTIFACT_LEASE_SECONDS": str(lease),
               "PYTHONUTF8": "1"}
        p = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parents[1] / "manage.py"), "run_artifact_worker"],
                             env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.procs.append(p)
        return p

    def wait_for(self, check, seconds=30):
        end = time.time() + seconds
        while time.time() < end:
            if check():
                return True
            time.sleep(0.2)
        return False

    def test_running_worker_consumes_job_and_recovers_after_kill(self):
        FakeRenderer.delay, FakeRenderer.calls = 30, 0
        self.worker(lease=3)
        self.assertTrue(self.wait_for(lambda: WorkerHeartbeat.objects.exists()))  # heartbeat = readiness signal
        with mock.patch("django.utils.timezone.now", return_value=ist(2026, 10, 2)):
            svc.review(self.vc, self.sub.pk, self.rev.pk, "APPROVE", "", False)  # committed approval -> durable job
        self.assertTrue(self.wait_for(lambda: ApprovalArtifact.objects.filter(state="RUNNING").exists()))  # picked up automatically
        self.procs[0].kill()  # crash mid-render (no graceful release)
        self.procs[0].wait()
        self.assertEqual(ApprovalArtifact.objects.get().state, "RUNNING")
        FakeRenderer.delay = 0
        self.worker(lease=3)  # supervisor restart
        self.assertTrue(self.wait_for(lambda: ApprovalArtifact.objects.filter(state="READY").exists()))
        art = ApprovalArtifact.objects.get()
        self.assertEqual(art.attempts, 2)  # the abandoned attempt counted, the job was not duplicated
        self.assertEqual((Path(self.storage) / art.storage_key).read_bytes(), FAKE)  # shared private storage
        self.assertEqual(ApprovalArtifact.objects.count(), 1)
