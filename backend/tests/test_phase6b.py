"""Phase 6B — PDF failure handling, evidence upload failure, dashboard query counts and log hygiene. SYNTHETIC data only."""
import http.client
import logging
import socket
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection
from django.test.utils import CaptureQueriesContext

from apps.catalogue.models import AnnualAssignment
from apps.evidence.models import Evidence
from apps.reports.models import GeneratedDocument
from apps.submissions.models import Submission
from tests.base import PortalTestCase, frozen, ist
from tests.fixtures import kra33_payload

OCT1 = ist(2026, 10, 1)
PDF = b"%PDF-1.4\n% synthetic\n" + b"0" * 2000
MARKER = "PRIVATE-REPORT-TEXT-6B"


def renderer_returns(data=None, read_error=None):
    """Patch the HTTP call to the renderer: 200 with `data`, or a read that fails mid-body."""
    resp = mock.MagicMock()
    resp.read.side_effect = read_error if read_error else (lambda: data)
    cm = mock.MagicMock()
    cm.__enter__.return_value = resp
    return mock.patch("apps.reports.pdf.urllib.request.urlopen", return_value=cm)


class PdfFailureTests(PortalTestCase):
    def setUp(self):
        self.a = self.client_for(self.dean_a)
        with frozen(OCT1):
            self.sid = self.open_draft(self.a, self.asg_a, self.p2)
            self.save(self.a, self.sid, 0, payload=kra33_payload(), achievement_text=MARKER)

    def export(self, client=None):
        with frozen(OCT1):
            return (client or self.a).get(f"/api/v1/submissions/{self.sid}/export/")

    def state(self):
        return list(Submission.objects.values_list("pk", "status", "edit_version", "current_revision_id")), Evidence.objects.count()

    def test_non_pdf_success_body_is_refused_and_not_cached(self):
        before = self.state()
        for body in (b"<html>renderer error page</html>", b"", b"%PDF"):  # wrong type, empty, truncated
            with renderer_returns(body):
                r = self.export()
            self.assertEqual((r.status_code, r.json()["code"]), (502, "pdf_failed"), body)
        self.assertFalse(GeneratedDocument.objects.exists())  # a bad render is never cached for later exports
        self.assertEqual(self.state(), before)
        with renderer_returns(b"%PDF-1.4 synthetic\n%%EOF"):
            self.assertEqual(self.export().status_code, 200)  # recovers once the renderer is healthy

    def test_connection_dropped_mid_body_or_timeout_gives_clear_error(self):
        for err, code in ((http.client.IncompleteRead(b"%PDF-1.4 part"), "pdf_failed"),
                          (ConnectionResetError(), "pdf_unavailable"),
                          (socket.timeout("timed out"), "pdf_unavailable")):
            with renderer_returns(read_error=err):
                r = self.export()
            self.assertIn(r.status_code, (502, 503), err)
            self.assertEqual(r.json()["code"], code, err)
        self.assertFalse(GeneratedDocument.objects.exists())

    def test_progress_export_refuses_non_pdf(self):
        vc = self.client_for(self.vc)
        with renderer_returns(b"not a pdf"), frozen(OCT1):
            r = vc.get("/api/v1/progress/export/", {"year": "2026-27", "period": self.p2.id})
        self.assertEqual((r.status_code, r.json()["code"]), (502, "pdf_failed"))

    def test_failures_log_no_report_content(self):
        with self.assertLogs(level="DEBUG") as logs:
            logging.getLogger("probe").info("start")
            with renderer_returns(read_error=http.client.IncompleteRead(b"")):
                self.export()
            with renderer_returns(b"junk"):
                self.export()
            with frozen(OCT1):
                self.save(self.a, self.sid, 0, achievement_text=MARKER + " stale")  # 409 conflict
        text = "\n".join(logs.output)
        self.assertNotIn(MARKER, text)
        self.assertNotIn("Synthetic-Test-Pass", text)


class EvidenceUploadFailureTests(PortalTestCase):
    def files(self):
        root = Path(settings.PRIVATE_STORAGE_ROOT) / "evidence"
        return set(root.glob("*")) if root.exists() else set()

    def test_failed_upload_leaves_no_row_and_no_new_file(self):
        a = self.client_for(self.dean_a)
        a.raise_request_exception = False
        with frozen(OCT1):
            sid = self.open_draft(a, self.asg_a, self.p2)
            before = self.files()
            with mock.patch("apps.evidence.services.Evidence.objects.create", side_effect=DatabaseError("synthetic failure")):
                r = a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs",
                           "label": "Synthetic", "file": SimpleUploadedFile("p.pdf", PDF, "application/pdf")}, format="multipart")
            self.assertEqual(r.status_code, 500)
            self.assertEqual(a.get(f"/api/v1/submissions/{sid}/evidence/").json()["results"], [])  # not shown as attached
        self.assertEqual(self.files(), before)  # no orphan file written by the failed request
        self.assertFalse(list(Path(settings.PRIVATE_STORAGE_ROOT).rglob("*.part")))


class QueryCountTests(PortalTestCase):
    """Dashboard reads must not issue one query per row (N+1) as data grows."""

    def make_drafts(self, n):
        rows = AnnualAssignment.objects.filter(year__label="2026-27").select_related("department", "kra")
        for asg in sorted(rows, key=lambda a: (a.department.code != "CSE", a.department.code, a.kra.number))[:n]:  # CSE first
            Submission.objects.get_or_create(assignment=asg, period=self.p2, defaults={"created_by": self.dean_a, "edit_version": 1,
                                                                                         "status": "REJECTED" if asg.kra.number % 3 == 0 else "DRAFT"})

    def count(self, client, url):
        with frozen(OCT1), CaptureQueriesContext(connection) as q:
            r = client.get(url)
        self.assertEqual(r.status_code, 200)
        return len(q)

    def test_vc_and_dean_dashboards_constant_queries(self):
        vc, dean = self.client_for(self.vc), self.client_for(self.dean_a)
        urls = ((vc, f"/api/v1/assignments/?year=2026-27&period={self.p2.id}"),
                (dean, f"/api/v1/assignments/?year=2026-27&period={self.p2.id}"),
                (vc, f"/api/v1/progress/?year=2026-27&period={self.p2.id}&page_size=100"))
        self.make_drafts(10)
        small = [self.count(c, u) for c, u in urls]
        self.make_drafts(90)
        large = [self.count(c, u) for c, u in urls]
        self.assertEqual(small, large, "query count grows with the number of submissions")
