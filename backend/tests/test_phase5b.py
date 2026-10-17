"""Phase 5B — VC progress dataset, counts, pagination, review consistency and progress PDF (D-068). SYNTHETIC data only."""
import io
from pathlib import Path
from unittest import mock

from django.conf import settings

import pymupdf

from apps.audit.errors import ApiError
from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, Department, DraftAssignment, ReportingPeriod, TemplateVersion
from apps.submissions.models import Submission
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1)  # 2026-27 P2 open
TRICKY = "3 events <b>bold</b> & 50% — “quoted”\nsecond line"


class Phase5BTests(PortalTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.deans = {"CSE": cls.dean_a, "ECE": cls.dean_b}
        for code in ("IT", "ME", "EEE"):
            cls.deans[code] = cls.make_user(f"t.dean.{code.lower()}", "DEAN", Department.objects.get(code=code))

    def setUp(self):
        self.v = self.client_for(self.vc)
        self.sids = {}
        with frozen(NOW):
            for code, dean in self.deans.items():
                c = self.client_for(dean)
                asg = AnnualAssignment.objects.get(department__code=code, kra__number=33, year__label="2026-27")
                self.sids[code] = self.open_draft(c, asg, self.p2)
            self.complete_and_submit(self.client_for(self.dean_a), self.sids["CSE"])                       # SUBMITTED
            c = self.client_for(self.deans["IT"])                                                          # DRAFT (edited)
            self.save(c, self.sids["IT"], 0, achievement_text=TRICKY)
            c = self.client_for(self.deans["ME"])                                                          # Nil, APPROVED
            r = self.save(c, self.sids["ME"], 0, is_nil=True, nil_reason="Synthetic: no events", achievement_text="Nil")
            c.post(f"/api/v1/submissions/{self.sids['ME']}/submit/", {"edit_version": r.json()["edit_version"]}, format="json")
            self.review("ME", "APPROVE")
            c = self.client_for(self.deans["EEE"])                                                         # REJECTED, edited after
            self.complete_and_submit(c, self.sids["EEE"])
            self.review("EEE", "REJECT", "Synthetic: add photos")
            v = self.detail(c, self.sids["EEE"])["edit_version"]
            self.save(c, self.sids["EEE"], v, achievement_text="Edited after rejection (synthetic)")

    def review(self, code, decision, reason=""):
        rev = self.detail(self.v, self.sids[code])["current_revision"]["id"]
        r = self.v.post(f"/api/v1/submissions/{self.sids[code]}/review/", {"revision": rev, "decision": decision, "reason": reason}, format="json")
        assert r.status_code == 200, r.content

    def progress(self, client=None, **q):
        params = {"year": "2026-27", "period": self.p2.id, **q}
        with frozen(NOW):
            return (client or self.v).get("/api/v1/progress/", params)

    def rows(self, **q):
        return {r["department"]: r for r in self.progress(kra=33, **q).json()["results"]}

    def test_statuses_achievements_and_nil(self):
        rows = self.rows()
        self.assertEqual(len(rows), 13)  # every department's finalized KRA 33 assignment, submission or not
        st = {k: r["display_status"] for k, r in rows.items()}
        self.assertEqual((st["CSE"], st["ECE"], st["IT"], st["ME"], st["EEE"], st["CS"]),
                         ("SUBMITTED", "NOT_SUBMITTED", "DRAFT", "APPROVED", "REJECTED", "NOT_SUBMITTED"))  # untouched draft = missing
        self.assertEqual((rows["IT"]["achievement_text"], rows["IT"]["achievement_source"]), (TRICKY, "draft"))  # exact, flagged
        self.assertEqual((rows["ME"]["is_nil"], rows["ME"]["display_status"], rows["ME"]["achievement_source"]), (True, "APPROVED", "submitted"))
        eee = rows["EEE"]
        self.assertEqual((eee["achievement_text"], eee["changed_since_submission"], eee["revision_sequence"]),
                         ("1 event (synthetic)", True, 1))  # what was reviewed, not the later edit
        self.assertFalse(rows["CSE"]["changed_since_submission"])
        self.assertEqual(rows["CS"]["achievement_source"], "none")
        tgt = AnnualAssignment.objects.get(department__code="CSE", kra__number=33, year__label="2026-27").target_text
        self.assertEqual(rows["CSE"]["target_text"], tgt)

    def test_counts_filters_pagination_consistent(self):
        all_ = self.progress().json()
        self.assertEqual(all_["assigned"], 585)
        self.assertEqual(sum(all_["counts"].values()), 585)
        self.assertEqual(all_["counts"]["SUBMITTED"], 1)
        self.assertEqual(all_["counts"]["NOT_SUBMITTED"], 581)
        filtered = self.progress(status="NOT_SUBMITTED", page_size=25).json()
        self.assertEqual((filtered["total"], filtered["counts"], len(filtered["results"])), (581, all_["counts"], 25))
        seen = []
        for page in range(1, 25):
            seen += [r["assignment_id"] for r in self.progress(status="NOT_SUBMITTED", page_size=25, page=page).json()["results"]]
        self.assertEqual((len(seen), len(set(seen))), (581, 581))  # deterministic ordering: no duplicates or gaps
        combo = self.progress(department="EEE", kra=33, status="REJECTED").json()
        self.assertEqual((combo["total"], combo["counts"]["REJECTED"]), (1, 1))
        order = [(r["kra_number"], r["department"]) for r in self.progress(page_size=100).json()["results"]]
        self.assertEqual(order, sorted(order))

    def test_filter_validation(self):
        other = ReportingPeriod.objects.filter(year__label="2027-28").first()
        for q, field in (({"period": other.id}, "period"), ({"year": "1999-00"}, "year"), ({"status": "LOST"}, "status"),
                         ({"kra": "x"}, "kra"), ({"department": "NOPE"}, "department"), ({"period": "abc"}, "period")):
            r = self.progress(**q)
            self.assertEqual(r.status_code, 400, q)
            self.assertIn(field, r.json()["field_errors"])

    def test_new_current_year_assignment_and_vc_drafts(self):
        kra = KRA.objects.create(number=46, activity_text="KRA 46: Synthetic", default_template=TemplateVersion.objects.get(key="kra41"))
        y = AcademicYear.objects.get(label="2026-27")
        DraftAssignment.objects.create(department=self.cse, kra=kra, year=y, target_text="draft only", template_version=kra.default_template, created_by=self.vc)
        self.assertEqual(self.progress(kra=46).json()["total"], 0)  # VC drafts never appear
        with frozen(NOW):
            self.v.post("/api/v1/admin/years/2026-27/finalize/", {"expected_pending": 1}, format="json")
        rows = self.progress(kra=46).json()["results"]
        self.assertEqual([(r["department"], r["display_status"], r["target_text"]) for r in rows], [("CSE", "NOT_SUBMITTED", "draft only")])

    def test_review_reads_the_submitted_revision_and_history_kept(self):
        d = self.detail(self.v, self.sids["EEE"])
        rev = d["current_revision"]
        self.assertEqual((d["achievement_text"], rev["achievement_text"]), ("Edited after rejection (synthetic)", "1 event (synthetic)"))
        self.assertEqual(len(rev["evidence"]), 3)  # manifest captured at submission
        hist = self.v.get(f"/api/v1/submissions/{self.sids['EEE']}/history/").json()["revisions"]
        self.assertEqual([(h["sequence"], h["achievement_text"], [x["decision"] for x in h["decisions"]]) for h in hist],
                         [(1, "1 event (synthetic)", ["REJECT"])])

    def export(self, client=None, **q):
        params = {"year": "2026-27", "period": self.p2.id, **q}
        with frozen(NOW):
            return (client or self.v).get("/api/v1/progress/export/", params)

    def test_export_permissions(self):
        anon = self.client_class()
        self.assertIn(self.export(anon).status_code, (401, 403))
        self.assertEqual(self.export(self.client_for(self.dean_a)).status_code, 403)
        self.assertEqual(self.progress(self.client_for(self.dean_a)).status_code, 403)

    def test_export_all_rows_escaped_read_only_snapshot(self):
        captured = {}

        def fake(parts):
            captured.update(parts)
            return b"%PDF-1.4 synthetic"
        before = list(Submission.objects.order_by("pk").values_list("pk", "status", "edit_version"))
        with mock.patch("apps.submissions.views.call_renderer", side_effect=fake):
            r = self.export(status="NOT_SUBMITTED")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r["Content-Type"], r["Cache-Control"]), ("application/pdf", "private, no-store"))
        self.assertIn("attachment;", r["Content-Disposition"])
        html = captured["html"]
        self.assertEqual(html.count("<tr><td>"), 581)  # every filtered row, far beyond one page of 50
        self.assertIn("rows in this report: <b>581</b>", html)
        self.assertTrue((captured["landscape"], captured["format"]) == (True, "A4"))
        with mock.patch("apps.submissions.views.call_renderer", side_effect=fake):
            self.export(department="IT", kra=33)
        self.assertIn("3 events &lt;b&gt;bold&lt;/b&gt; &amp; 50%", captured["html"])  # escaped, exact text
        self.assertNotIn("<b>bold</b>", captured["html"])
        self.assertIn("Unsubmitted draft", captured["html"])
        self.assertEqual(list(Submission.objects.order_by("pk").values_list("pk", "status", "edit_version")), before)  # read-only

    def test_export_renderer_failure_and_limits(self):
        with mock.patch("apps.submissions.views.call_renderer", side_effect=ApiError(503, "pdf_unavailable", "The PDF service is unavailable.")):
            r = self.export()
        self.assertEqual((r.status_code, r.json()["code"]), (503, "pdf_unavailable"))
        with mock.patch("apps.submissions.progress.MAX_ROWS", 10):
            r = self.export()
        self.assertEqual((r.status_code, r.json()["code"]), (400, "too_many_rows"))  # refused, never truncated

    def test_real_renderer_multipage(self):
        """Uses the running internal renderer when available; skipped (not passed) otherwise."""
        import urllib.request
        try:
            urllib.request.urlopen("http://127.0.0.1:8790/health", timeout=2)
        except Exception:
            self.skipTest("renderer not running")
        r = self.export()
        self.assertEqual(r.status_code, 200, r.content[:200])
        out = Path(settings.PROJECT_ROOT) / ".work" / "renders" / "progress"
        out.mkdir(parents=True, exist_ok=True)
        (out / "sample.pdf").write_bytes(r.content)  # synthetic sample for visual review (git-ignored)
        doc = pymupdf.open(stream=io.BytesIO(r.content), filetype="pdf")
        self.assertGreater(doc.page_count, 5)
        self.assertTrue(all("Dept." in p.get_text() for p in doc))  # header row repeats on every page
        self.assertIn("rows in this report: 585", doc[0].get_text().replace("\n", " "))
