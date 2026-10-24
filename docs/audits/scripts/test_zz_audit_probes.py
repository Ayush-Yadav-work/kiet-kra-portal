"""AUDIT PROBES (2026-10-24). Isolated Django test database + temporary media only. Not a product test: copied to
docs/audits/evidence/ after the run and removed from tests/. Writes results to docs/audits/evidence/*.json."""
import json
import time
from datetime import timedelta
from pathlib import Path

import pymupdf
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
import io

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import User
from apps.catalogue.models import AnnualAssignment, Department, ReportingPeriod
from apps.submissions.models import ReopenGrant, Submission, SubmissionRevision
from tests import fixtures as fx
from tests.base import TEST_STORAGE, PortalTestCase, frozen, ist
from tests.test_reports import RENDERER

EVID = Path(settings.PROJECT_ROOT) / "docs" / "audits" / "evidence"
PNG = EVID / "pdf-pages"
OCT1 = ist(2026, 10, 1, 10)
PDF = b"%PDF-1.4\n% synthetic\n" + b"0" * 2000

PAYLOADS = {
    **{k: (lambda k=k: fx.kra13_payload(k, courses=2)) for k in (1, 2, 3)},
    **{k: (lambda k=k: fx.fp_payload(k, 2, 3)) for k in (4, 5, 6)},
    7: fx.kra7_payload, 8: lambda: fx.kra8_10_payload(8), 9: lambda: fx.kra9_payload(("9a", "9b")), 10: lambda: fx.kra8_10_payload(10),
    11: lambda: fx.kra11_payload(2, 4), 12: lambda: fx.kra12_payload(3), 13: lambda: fx.kra13iab_payload(2), 14: lambda: fx.kra14_payload(2),
    15: lambda: fx.kra15_payload(4), 16: lambda: fx.kra16_payload(2), 17: lambda: fx.kra17_payload(3), 18: lambda: fx.kra18_payload(2, 2),
    19: lambda: fx.kra19_payload(2), 20: lambda: fx.kra20_payload(rows=3), 21: lambda: fx.kra21_payload(2), 22: lambda: fx.kra22_payload(3),
    23: lambda: fx.kra23_payload(programmes=2, programs=2), 24: lambda: fx.kra24_payload(6),
    **{k: (lambda k=k: fx.award_payload(k, 4)) for k in (25, 26)},
    **{k: (lambda k=k: fx.event_payload(k, 2)) for k in (27, 28, 29, 30, 41, 42)},
    31: lambda: fx.kra31_payload(3), 32: lambda: fx.kra32_payload(rows=4), 33: lambda: fx.kra33_payload(2),
    **{k: (lambda k=k: fx.support_payload(k, 2)) for k in (34, 35)},
    **{k: (lambda k=k: fx.kra3637_payload(k, programmes=2)) for k in (36, 37)},
    38: lambda: fx.kra38_payload(3), 39: lambda: fx.kra39_payload(2), 40: lambda: fx.kra40_payload(2),
    43: lambda: fx.kra43_payload(2), 44: lambda: fx.kra44_payload(2), 45: lambda: fx.kra45_payload(2),
}
LONG = {33: lambda: fx.kra33_payload(3, rows=40, long_text=True), 20: lambda: fx.kra20_payload(rows=60, long_text=True),
        19: lambda: fx.kra19_payload(2, long_text=True), 15: lambda: fx.kra15_payload(40, long_text=True)}


def text_of(data):
    return " ".join("".join(p.get_text() for p in pymupdf.open(stream=data, filetype="pdf")).split())


class AuditProbes(PortalTestCase):
    def setUp(self):
        EVID.mkdir(parents=True, exist_ok=True)
        for u, last in ((self.dean_a, "Audit Dean Alpha"), (self.dean_b, "Audit Dean Beta")):
            u.first_name, u.last_name = "Synthetic", last
            u.save()
        self.a, self.b, self.v = self.client_for(self.dean_a), self.client_for(self.dean_b), self.client_for(self.vc)

    def export(self, client, sid, q=""):
        r = client.get(f"/api/v1/submissions/{sid}/export/{q}")
        return r.status_code, (b"".join(r.streaming_content) if r.status_code == 200 else r.content)

    def submit_report(self, client, dept, n, payload=None, nil=False):
        asg = AnnualAssignment.objects.get(department=dept, kra__number=n, year__label="2026-27")
        sid = self.open_draft(client, asg, self.p2)
        changes = {"is_nil": True, "nil_reason": "Synthetic: no activity"} if nil else {"payload": payload, "achievement_text": "Synthetic"}
        r = self.save(client, sid, 0, **changes)
        if r.status_code != 200:
            return sid, f"save {r.status_code}: {r.content[:300]!r}"
        if not nil:
            for cat in asg.template_version.schema.get("evidence", {}).get("required", []):
                client.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": "https://drive.google.com/file/d/synthetic",
                                                                     "category": cat, "label": f"Synthetic {cat}"}, format="json")
        v = self.detail(client, sid)["edit_version"]
        r = client.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json")
        return sid, None if r.status_code == 200 else f"submit {r.status_code}: {r.content[:400]!r}"

    # ---------- 45 templates: normal + Nil, preview + PDF ----------
    def test_template_sweep(self):
        PNG.mkdir(exist_ok=True)
        results = {}
        with frozen(OCT1):
            for n in range(1, 46):
                res = results[n] = {}
                tv = AnnualAssignment.objects.get(department=self.cse, kra__number=n, year__label="2026-27").template_version
                res["template"] = f"{tv.key} v{tv.version} ({tv.renderer_template}, {tv.schema['page']['format']}{' landscape' if tv.schema['page'].get('landscape') else ''})"
                sid, err = self.submit_report(self.a, self.cse, n, PAYLOADS[n]())
                res["normal_submit"] = err or "PASS"
                if err:
                    continue
                html = self.v.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json")
                res["vc_preview"] = "PASS" if html.status_code == 200 and "Synthetic" in html.json()["html"] else f"FAIL {html.status_code}"
                if RENDERER:
                    st, data = self.export(self.v, sid)
                    if st == 200:
                        doc = pymupdf.open(stream=data, filetype="pdf")
                        t = text_of(data)
                        res["pdf"] = f"PASS {doc.page_count}p"
                        res["pdf_has_verification"] = "Pending approval" in t
                        res["pdf_has_page_numbers"] = f"Page 1 | {doc.page_count}" in t
                        doc[0].get_pixmap(dpi=55).save(PNG / f"kra{n:02d}-p1.png")
                        if doc.page_count > 1:
                            doc[doc.page_count - 1].get_pixmap(dpi=55).save(PNG / f"kra{n:02d}-last.png")
                    else:
                        res["pdf"] = f"FAIL {st}"
                sid, err = self.submit_report(self.b, self.ece, n, nil=True)
                res["nil_submit"] = err or "PASS"
                if not err and RENDERER:
                    st, data = self.export(self.v, sid)
                    t = text_of(data) if st == 200 else ""
                    res["nil_pdf"] = "PASS" if "Head/Dean: Synthetic Audit Dean Beta" in t and "Date: 1 October 2026" in t else f"FAIL {st} {t[-200:]}"
        (EVID / "template-sweep.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
        bad = {n: r for n, r in results.items() if any(isinstance(v, str) and not v.startswith("PASS") for k, v in r.items() if k != "template")}
        self.assertEqual(bad, {})

    def test_long_content_page_breaks(self):
        if not RENDERER:
            self.skipTest("renderer not running")
        PNG.mkdir(parents=True, exist_ok=True)
        me = Department.objects.get(code="ME")
        d = self.make_user("aud.dean.me", "DEAN", me)
        d.first_name = "Synthetic"
        d.save()
        c = self.client_for(d)
        out = {}
        with frozen(OCT1):
            for n, build in LONG.items():
                sid, err = self.submit_report(c, me, n, build())
                if err:
                    out[n] = err
                    continue
                st, data = self.export(self.v, sid)
                doc = pymupdf.open(stream=data, filetype="pdf")
                heads = sum(1 for p in doc if "S. No" in p.get_text() or "Sl. No" in p.get_text() or "S.No" in p.get_text())
                out[n] = {"pages": doc.page_count, "pages_with_table_heading": heads}
                for i in (0, min(1, doc.page_count - 1), doc.page_count - 1):
                    doc[i].get_pixmap(dpi=55).save(PNG / f"long-kra{n:02d}-p{i + 1}.png")
        (EVID / "long-content.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        self.assertTrue(all(isinstance(v, dict) for v in out.values()), out)

    # ---------- security ----------
    def test_security_probes(self):
        out = {}
        with frozen(OCT1):
            sid = self.open_draft(self.a, self.asg_a, self.p2)
            for url in ("https://drive.google.com.evil.example/x", "https://evil.example/drive.google.com/x", "javascript:alert(1)",
                        "http://drive.google.com/file/d/x", "https://user@drive.google.com/file/d/x", "data:text/html,x",
                        "https://drive.google.com:8443/file/d/x"):
                r = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK", "drive_url": url, "category": "Photographs",
                                                                         "label": "x"}, format="json")
                out[f"drive_link {url}"] = r.status_code
            r = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs", "label": "trav",
                                                                     "file": SimpleUploadedFile("../../..\\evil<script>.pdf", PDF, "application/pdf")}, format="multipart")
            out["upload traversal name status"] = r.status_code
            if r.status_code == 201:
                out["upload stored filename"] = r.json().get("original_filename")
            r = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs", "label": "html",
                                                                     "file": SimpleUploadedFile("x.pdf", b"<html><script>alert(1)</script>", "application/pdf")}, format="multipart")
            out["upload html-as-pdf"] = r.status_code
            # XSS in report values reaches the preview escaped
            p = fx.kra33_payload()
            p["activities"][0]["event_name"] = "<script>alert(1)</script><img src=x onerror=alert(2)>"
            self.save(self.a, sid, self.detail(self.a, sid)["edit_version"], payload=p, achievement_text="<b onmouseover=alert(3)>x</b>")
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
            out["preview escapes <script>"] = "<script>alert(1)" not in html and "&lt;script&gt;" in html
            out["preview escapes attribute payload"] = "<img src=x onerror" not in html and "<b onmouseover" not in html
            # cross-department direct object access
            ev = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs", "label": "ok",
                                                                      "file": SimpleUploadedFile("ok.pdf", PDF, "application/pdf")}, format="multipart").json()["id"]
            for m, url in (("get", f"/api/v1/submissions/{sid}/"), ("get", f"/api/v1/submissions/{sid}/export/"), ("post", f"/api/v1/submissions/{sid}/preview/"),
                           ("get", f"/api/v1/evidence/{ev}/download/"), ("get", f"/api/v1/submissions/{sid}/history/"),
                           ("patch", f"/api/v1/submissions/{sid}/draft/"), ("post", f"/api/v1/submissions/{sid}/submit/"), ("delete", f"/api/v1/evidence/{ev}/")):
                out[f"dean B {m} {url.split('/')[3]}/{url.split('/')[-2]}"] = getattr(self.b, m)(url, {}, format="json").status_code
            # role boundaries
            for m, url in (("patch", f"/api/v1/submissions/{sid}/draft/"), ("post", f"/api/v1/submissions/{sid}/submit/")):
                out[f"VC {m} {url.split('/')[-2]}"] = getattr(self.v, m)(url, {}, format="json").status_code
            for m, url in (("get", "/api/v1/progress/?year=2026-27"), ("get", "/api/v1/analytics/?year=2026-27"), ("get", "/api/v1/admin/drafts/?year=2027-28"),
                           ("post", "/api/v1/announcements/"), ("get", "/api/v1/reopen-requests/"), ("post", "/api/v1/bulk-approvals/")):
                out[f"Dean {m} {url.split('?')[0]}"] = getattr(self.a, m)(url, {}, format="json").status_code
            # wrong-portal login, logout invalidates the session
            from rest_framework.test import APIClient
            from tests.base import PASSWORD
            c = APIClient(enforce_csrf_checks=False)
            out["dean creds on VC login"] = c.post("/api/v1/auth/vc/login/", {"username": self.dean_a.username, "password": PASSWORD}, format="json").status_code
            c2 = APIClient()
            c2.post("/api/v1/auth/dean/login/", {"username": self.dean_a.username, "password": PASSWORD}, format="json")
            out["me after login"] = c2.get("/api/v1/auth/me/").status_code
            c2.post("/api/v1/auth/logout/", {}, format="json")
            out["me after logout"] = c2.get("/api/v1/auth/me/").status_code
            # CSRF enforced on a mutating call for a session client
            c3 = APIClient(enforce_csrf_checks=True)
            c3.force_login(self.dean_a)
            out["PATCH draft without CSRF token"] = c3.patch(f"/api/v1/submissions/{sid}/draft/", {"edit_version": 0}, format="json").status_code
            # first-login password change gate
            fresh = User.objects.create_user("aud.fresh", password=PASSWORD, role="DEAN", department=Department.objects.get(code="IT"))
            out["must_change_password user: assignments"] = self.client_for(fresh).get("/api/v1/assignments/?year=2026-27").status_code
        # DB-level role constraints
        for name, kw in (("second active VC", dict(role="VC")), ("second active Dean CSE", dict(role="DEAN", department=self.cse))):
            try:
                with transaction.atomic():
                    User.objects.create(username=f"aud.{name.replace(' ', '')}", **kw)
                out[name] = "ALLOWED"
            except IntegrityError:
                out[name] = "refused (IntegrityError)"
        (EVID / "security-probes.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    # ---------- invariants ----------
    def test_invariant_probes(self):
        out = {}
        with frozen(OCT1):
            sid, err = self.submit_report(self.a, self.cse, 33, fx.kra33_payload())
            assert not err, err
            v = self.detail(self.a, sid)["edit_version"]
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json")
            out["double submit (second click)"] = r.status_code
            out["revisions after double submit"] = SubmissionRevision.objects.filter(submission_id=sid).count()
            rev = str(Submission.objects.get(pk=sid).current_revision_id)
            out["approve #1"] = self.v.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json").status_code
            out["approve #2 (repeat)"] = self.v.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev, "decision": "APPROVE"}, format="json").status_code
            out["stale draft save"] = self.save(self.b, self.open_draft(self.b, self.asg_b, self.p2), 99, achievement_text="x").status_code
        # 72-hour reopening, exact IST boundaries (P1 closed 1 Sep 2026 00:00 IST)
        with frozen(ist(2026, 9, 10, 9)):
            asg = AnnualAssignment.objects.get(department=self.cse, kra__number=34, year__label="2026-27")
            req = self.a.post(f"/api/v1/assignments/{asg.id}/periods/{self.p1.id}/reopen-requests/", {"reason": "Synthetic"}, format="json").json()
            out["reopen request from unstarted report"] = "id" in req
            out["approve reopen"] = self.v.post(f"/api/v1/reopen-requests/{req['id']}/decision/", {"approve": True}, format="json").status_code
            g = ReopenGrant.objects.get(request_id=req["id"])
            out["grant length (h)"] = (g.expires_at - g.starts_at) / timedelta(hours=1)
            sub_id = req.get("submission_id") or str(g.submission_id)
        for label, at in (("1s before expiry", g.expires_at - timedelta(seconds=1)), ("at expiry", g.expires_at)):
            with frozen(at):
                d = self.detail(self.a, sub_id)
                out[f"editable {label}"] = d["editable"]
                out[f"save {label}"] = self.save(self.a, sub_id, d["edit_version"], achievement_text="x").status_code
        other = AnnualAssignment.objects.get(department=self.cse, kra__number=35, year__label="2026-27")
        with frozen(ist(2026, 9, 10, 10)):
            r = self.a.post(f"/api/v1/assignments/{other.id}/periods/{self.p1.id}/", {})
            out["other KRA same period during grant (open draft)"] = r.status_code
        (EVID / "invariant-probes.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")



@override_settings(SESSION_COOKIE_AGE=10**8, PRIVATE_STORAGE_ROOT=TEST_STORAGE)
class AnalyticsProbes(TransactionTestCase):
    """Analytics owns its read transaction (D-074), so these run outside TestCase's wrapping transaction."""
    open_draft, save, detail = PortalTestCase.open_draft, PortalTestCase.save, PortalTestCase.detail
    client_for, make_user = PortalTestCase.client_for, staticmethod(PortalTestCase.make_user)

    def setUp(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        self.cse, self.ece = Department.objects.get(code="CSE"), Department.objects.get(code="ECE")
        self.vc = self.make_user("t.vc", "VC")
        self.dean_a, self.dean_b = self.make_user("t.dean.cse", "DEAN", self.cse), self.make_user("t.dean.ece", "DEAN", self.ece)
        self.p2 = ReportingPeriod.objects.get(year__label="2026-27", index=2)
        self.a, self.b, self.v = self.client_for(self.dean_a), self.client_for(self.dean_b), self.client_for(self.vc)

    def test_csv_and_zero_denominator(self):
        out = {}
        # completion with a zero denominator
        with frozen(OCT1):
            r = self.v.get("/api/v1/analytics/", {"year": "2028-29", "scope": "ytd"})
            out["analytics future year status"] = r.status_code
            if r.status_code == 200:
                out["analytics future year completion"] = r.json()["summary"].get("completion")
        # CSV formula injection
        with frozen(OCT1):
            s2 = self.open_draft(self.b, AnnualAssignment.objects.get(department=self.ece, kra__number=34, year__label="2026-27"), self.p2)
            self.save(self.b, s2, 0, is_nil=True, nil_reason="x", achievement_text="=HYPERLINK(\"http://x\")")
            self.b.post(f"/api/v1/submissions/{s2}/submit/", {"edit_version": 1}, format="json")
            s3 = self.open_draft(self.b, AnnualAssignment.objects.get(department=self.ece, kra__number=35, year__label="2026-27"), self.p2)
            self.save(self.b, s3, 0, is_nil=True, nil_reason="x", achievement_text=" =1+1")
            self.b.post(f"/api/v1/submissions/{s3}/submit/", {"edit_version": 1}, format="json")
            r = self.v.get("/api/v1/analytics/export/", {"year": "2026-27", "scope": "ytd", "kind": "csv", "department": "ECE"})
            body = r.content.decode("utf-8-sig") if r.status_code == 200 else ""
            out["csv status"] = r.status_code
            out["csv =HYPERLINK neutralised"] = "'=HYPERLINK" in body
            out["csv ' =1+1' (leading space) as written"] = '" =1+1"' in body or ", =1+1" in body or " =1+1" in body
        (EVID / "analytics-probes.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

    # ---------- performance: query counts ----------
    def test_query_counts(self):
        out = {}
        with frozen(OCT1):
            def measure(client, url, params=None):
                with CaptureQueriesContext(connection) as q:
                    t = time.perf_counter()
                    r = client.get(url, params or {})
                    ms = round((time.perf_counter() - t) * 1000)
                return {"status": r.status_code, "queries": len(q), "ms": ms}
            calls = (("VC progress P2", self.v, "/api/v1/progress/", {"year": "2026-27", "period": self.p2.id}),
                     ("VC analytics ytd", self.v, "/api/v1/analytics/", {"year": "2026-27", "scope": "ytd"}),
                     ("VC assignments P2", self.v, "/api/v1/assignments/", {"year": "2026-27", "period": self.p2.id}),
                     ("Dean assignments P2", self.a, "/api/v1/assignments/", {"year": "2026-27", "period": self.p2.id}),
                     ("VC reopen requests", self.v, "/api/v1/reopen-requests/", None))
            out["empty"] = {n: measure(c, u, p) for n, c, u, p in calls}
            for n in range(1, 31):  # 30 submitted reports in CSE + 30 in ECE
                for client, dept in ((self.a, self.cse), (self.b, self.ece)):
                    asg = AnnualAssignment.objects.get(department=dept, kra__number=n, year__label="2026-27")
                    s = self.open_draft(client, asg, self.p2)
                    self.save(client, s, 0, is_nil=True, nil_reason="x", achievement_text="x")
                    client.post(f"/api/v1/submissions/{s}/submit/", {"edit_version": 1}, format="json")
            out["60 submitted"] = {n: measure(c, u, p) for n, c, u, p in calls}
        (EVID / "query-counts.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
