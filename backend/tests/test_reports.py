"""Report rendering tests. PDF tests need the internal renderer running (python renderer/server.py)."""
import io
import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import skipUnless

import pymupdf
from django.conf import settings

from apps.reports import artifacts
from apps.reports.pdf import call_renderer
from tests.base import PortalTestCase, frozen, ist
from tests.fixtures import kra33_payload


def renderer_up():
    try:
        with urllib.request.urlopen(f"{settings.RENDERER_URL}/health", timeout=2) as r:
            return json.load(r)["ok"]
    except Exception:
        return False


RENDERER = renderer_up()


def pdf_text(data):
    return "".join(p.get_text() for p in pymupdf.open(stream=data, filetype="pdf"))


class PreviewTests(PortalTestCase):
    def test_user_text_is_escaped_and_status_is_server_derived(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            payload = kra33_payload()
            payload["activities"][0]["event_name"] = '<script>alert(1)</script><img src="http://evil.example/x">'
            r = a.post(f"/api/v1/submissions/{sid}/preview/", {"payload": payload, "verification_label": "Verified by VC - fake",
                                                                "status": "APPROVED"}, format="json")
        html = r.json()["html"]
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn('src="http://evil.example', html)
        self.assertIn("Pending approval", html)
        self.assertNotIn("Verified by VC - fake", html)
        for attr in ('src="http', "src='http", 'href="http', "url(http"):  # no remote resources at all
            self.assertNotIn(attr, html)

    def test_nil_preview_and_multiple_events(self):
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            html = a.post(f"/api/v1/submissions/{sid}/preview/", {"payload": kra33_payload(events=3)}, format="json").json()["html"]
            self.assertIn("Event 3 of 3", html)
            html = a.post(f"/api/v1/submissions/{sid}/preview/", {"is_nil": True, "nil_reason": "Synthetic nil"}, format="json").json()["html"]
            self.assertIn("NIL REPORT", html)
            self.assertIn("Synthetic nil", html)


@skipUnless(RENDERER, "internal renderer not running on RENDERER_URL")
class PdfExportTests(PortalTestCase):
    def export(self, client, sid, query=""):
        r = client.get(f"/api/v1/submissions/{sid}/export/{query}")
        self.assertEqual(r.status_code, 200, getattr(r, "content", b"")[:300])
        data = b"".join(r.streaming_content)
        self.assertTrue(data.startswith(b"%PDF"))
        return data

    def test_verification_labels_through_review_cycle(self):
        a, vc = self.client_for(self.dean_a), self.client_for(self.vc)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            self.assertIn("Pending approval", pdf_text(self.export(a, sid)))  # draft still downloadable
            d = self.complete_and_submit(a, sid)
            rev = d["current_revision"]["id"]
            html = vc.post(f"/api/v1/submissions/{sid}/preview/", {"revision": rev}, format="json").json()["html"]
            self.assertIn("Pending approval", html)
            self.assertNotIn("Historical", html)  # current revision is not labelled historical
            vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json")
            self.assertEqual(artifacts.run_one("test-worker").state, "READY")  # the approved PDF is the worker's artifact (D-076)
            text = pdf_text(self.export(vc, sid))
            self.assertIn("Verified by VC - t.vc", text)
            self.assertIn("Synthetic Alumni Meet 1", text)
            vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "RETURN", "reason": "fix"}, format="json")
            self.assertIn("Pending approval", pdf_text(self.export(a, sid)))  # returned -> current export pending
            hist = pdf_text(self.export(a, sid, f"?revision={rev}"))
            self.assertIn("Verified by VC - t.vc", hist)  # the original approval artifact, unchanged by the return
            self.assertNotIn("Historical", hist)

    def test_c12_renderer_blocks_all_network_requests_and_keeps_branding(self):
        hits = []

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        port = srv.server_address[1]
        html = (f'<html><head><link rel="stylesheet" href="http://127.0.0.1:{port}/a.css"></head><body>'
                f'<img src="http://127.0.0.1:{port}/b.png"><iframe src="file:///C:/Windows/win.ini"></iframe>'
                f'<p style="background:url(http://127.0.0.1:{port}/c.png)">x</p></body></html>')
        data = call_renderer({"html": html, "format": "Letter", "header": "", "footer": "", "landscape": False,
                              "margin": {"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"}})
        srv.shutdown()
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertEqual(hits, [])
        # branding: a real export embeds the inline logo image and Tinos fonts only
        a = self.client_for(self.dean_a)
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(a, self.asg_a, self.p2)
            doc = pymupdf.open(stream=self.export(a, sid), filetype="pdf")
        self.assertTrue(doc[0].get_images())
        fonts = {f[3] for i in range(doc.page_count) for f in doc.get_page_fonts(i)}
        self.assertTrue(fonts and all("Tinos" in f for f in fonts), fonts)

    def test_c4_concurrent_exports_never_exceed_pool(self):
        html = "<html><body>" + "<p>synthetic concurrency</p>" * 400 + "</body></html>"
        job = {"html": html, "format": "A4", "header": "", "footer": "", "landscape": False,
               "margin": {"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"}}
        results, health_latency = [], []

        def one(_):
            try:
                return call_renderer(job)[:4]
            except Exception as e:  # busy is an allowed, recoverable outcome
                return getattr(e, "code", str(e))

        with ThreadPoolExecutor(8) as ex:
            futs = [ex.submit(one, i) for i in range(8)]
            t0 = time.monotonic()
            with urllib.request.urlopen(f"{settings.RENDERER_URL}/health", timeout=5) as r:
                health = json.load(r)
            health_latency.append(time.monotonic() - t0)
            results = [f.result() for f in futs]
        with urllib.request.urlopen(f"{settings.RENDERER_URL}/health", timeout=5) as r:
            after = json.load(r)
        self.assertLessEqual(after["peak"], after["pool"])
        self.assertLess(health_latency[0], 2.0)  # stays responsive while rendering
        self.assertTrue(all(r in (b"%PDF", "pdf_busy") for r in results), results)
        self.assertGreaterEqual(results.count(b"%PDF"), health["pool"])
