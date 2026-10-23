"""Draft privacy (D-078): the VC cannot tell a saved, never-submitted draft from an untouched slot, cannot read unsubmitted
content through any endpoint, and after a rejection sees only the submitted version until the Dean resubmits. Deans keep
their own draft view."""
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalogue.models import AcademicYear, AnnualAssignment
from apps.submissions import analytics
from apps.submissions.models import ReopenGrant
from tests.base import PortalTestCase, frozen, ist
from tests.fixtures import kra33_payload

OCT1 = ist(2026, 10, 1)  # 2026-27: P1 closed, P2 open
PDF = b"%PDF-1.4\n% synthetic\n" + b"0" * 2000
SECRET = "Synthetic unsubmitted draft text"


class DraftPrivacyTests(PortalTestCase):
    def setUp(self):
        self.a, self.v = self.client_for(self.dean_a), self.client_for(self.vc)

    def draft(self, asg=None):
        """A saved draft with content and a file, never submitted."""
        sid = self.open_draft(self.a, asg or self.asg_a, self.p2)
        v = self.detail(self.a, sid)["edit_version"]
        self.assertEqual(self.save(self.a, sid, v, achievement_text=SECRET, payload=kra33_payload()).status_code, 200)
        r = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs", "label": "Draft photo",
                                                                  "file": SimpleUploadedFile("d.pdf", PDF, "application/pdf")}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        return sid, r.json()["id"]

    def progress(self, **q):
        return self.v.get("/api/v1/progress/", {"year": "2026-27", "period": self.p2.id, **q}).json()

    def test_vc_lists_cannot_distinguish_a_saved_draft_from_an_untouched_slot(self):
        with frozen(OCT1):
            before = self.progress()
            self.draft()
            after = self.progress()
            self.assertNotIn("DRAFT", after["counts"])
            self.assertEqual(after["counts"], before["counts"])  # saving a draft changes nothing the VC can see
            self.assertEqual(after["assigned"], sum(after["counts"].values()))
            row = next(r for r in self.progress(department="CSE", kra=33)["results"])
            untouched = next(r for r in self.progress(department="ECE", kra=33)["results"])
            strip = lambda r: {k: v for k, v in r.items() if k not in ("assignment_id", "department", "department_name", "target_text")}
            self.assertEqual(strip(row), strip(untouched))  # identical shape and values: no id, no achievement, no flag
            self.assertEqual((row["display_status"], row["submission_id"], row["achievement_text"]), ("NOT_SUBMITTED", None, ""))
            old = self.v.get("/api/v1/progress/", {"year": "2026-27", "period": self.p2.id, "status": "DRAFT", "department": "CSE", "kra": 33})
            self.assertEqual(old.status_code, 200)  # old bookmark: treated as Not submitted
            self.assertIn(str(self.asg_a.id), [r["assignment_id"] for r in old.json()["results"]])
            rows = self.v.get(f"/api/v1/assignments/?year=2026-27&period={self.p2.id}").json()["results"]
            mine = next(r for r in rows if r["id"] == str(self.asg_a.id))
            self.assertEqual(mine["submission"], {"id": None, "display_status": "NOT_SUBMITTED"})
            self.assertIsNone(self.v.get(f"/api/v1/assignments/{self.asg_a.id}/periods/{self.p2.id}/").json()["submission_id"])
            dean_rows = self.a.get(f"/api/v1/assignments/?year=2026-27&period={self.p2.id}").json()["results"]
            self.assertEqual(next(r for r in dean_rows if r["id"] == str(self.asg_a.id))["submission"]["display_status"], "DRAFT")  # Dean keeps it

    def test_vc_cannot_reach_draft_content_through_direct_endpoints(self):
        with frozen(OCT1):
            sid, ev = self.draft()
            with mock.patch("apps.reports.pdf.call_renderer", return_value=b"%PDF-1.4 x %%EOF") as renderer:
                for method, url, body in (("get", f"/api/v1/submissions/{sid}/", None), ("get", f"/api/v1/submissions/{sid}/history/", None),
                                          ("get", f"/api/v1/submissions/{sid}/export/", None), ("get", f"/api/v1/submissions/{sid}/evidence/", None),
                                          ("post", f"/api/v1/submissions/{sid}/preview/", {}), ("get", f"/api/v1/evidence/{ev}/download/", None),
                                          ("post", f"/api/v1/submissions/{sid}/review/", {"decision": "APPROVE"})):
                    r = getattr(self.v, method)(url, body or {}, format="json") if method == "post" else self.v.get(url)
                    self.assertEqual(r.status_code, 404, f"{method} {url}")  # same answer as a report that does not exist
                    self.assertNotIn(SECRET, r.content.decode(errors="ignore"))
                renderer.assert_not_called()
            self.assertEqual(self.a.get(f"/api/v1/submissions/{sid}/").json()["achievement_text"], SECRET)  # Dean unaffected
            self.assertEqual(self.a.get(f"/api/v1/evidence/{ev}/download/").status_code, 200)
            b = self.client_for(self.dean_b)
            self.assertEqual(b.get(f"/api/v1/submissions/{sid}/").status_code, 404)  # department isolation unchanged

    def test_after_rejection_vc_sees_only_the_submitted_version_until_resubmission(self):
        with frozen(OCT1):
            sid, old_ev = self.draft()
            d = self.complete_and_submit(self.a, sid)
            submitted = d["current_revision"]["achievement_text"]
            rev1 = d["current_revision"]["id"]
            self.assertEqual(self.v.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev1, "decision": "REJECT", "reason": "fix"},
                                         format="json").status_code, 200)
            v = self.detail(self.a, sid)["edit_version"]
            self.save(self.a, sid, v, achievement_text=SECRET)  # correction in progress
            new = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "FILE", "category": "Photographs", "label": "New photo",
                                                                        "file": SimpleUploadedFile("n.pdf", PDF, "application/pdf")}, format="multipart").json()["id"]
            det = self.v.get(f"/api/v1/submissions/{sid}/").json()
            self.assertEqual((det["status"], det["display_status"], det["achievement_text"], det["edit_version"]), ("REJECTED", "REJECTED", submitted, None))
            self.assertNotIn(SECRET, str(det))
            row = self.progress(department="CSE", kra=33)["results"][0]
            self.assertEqual((row["display_status"], row["achievement_text"]), ("REJECTED", submitted))  # not relabelled
            listed = [e["id"] for e in self.v.get(f"/api/v1/submissions/{sid}/evidence/").json()["results"]]
            self.assertIn(old_ev, listed)
            self.assertNotIn(new, listed)
            self.assertEqual(self.v.get(f"/api/v1/evidence/{old_ev}/download/").status_code, 200)  # submitted evidence stays available
            self.assertEqual(self.v.get(f"/api/v1/evidence/{new}/download/").status_code, 404)
            html = self.v.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
            self.assertNotIn(SECRET, html)
            seen = []
            with mock.patch("apps.reports.pdf.call_renderer", side_effect=lambda p: seen.append(p["html"]) or b"%PDF-1.4 x %%EOF"):
                self.assertEqual(self.v.get(f"/api/v1/submissions/{sid}/export/").status_code, 200)
            self.assertNotIn(SECRET, seen[0])
            # resubmission makes the corrected version (and its new evidence) visible
            d = self.detail(self.a, sid)
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": d["edit_version"]}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(self.v.get(f"/api/v1/submissions/{sid}/").json()["achievement_text"], SECRET)
            self.assertEqual(self.v.get(f"/api/v1/evidence/{new}/download/").status_code, 200)

    def test_analytics_bulk_and_reopening_follow_the_rule(self):
        with frozen(OCT1):
            sid, _ = self.draft()
            year = AcademicYear.objects.get(label="2026-27")
            f = {"year": year, "scope": "period", "period": self.p2, "departments": ["CSE", "ECE"], "kras": [33], "status": "", "page": 1, "page_size": 50}
            r = analytics.compute(analytics.load(f, OCT1), f, OCT1)
            self.assertNotIn("DRAFT", r["breakdown"])
            self.assertEqual(r["breakdown"]["NOT_SUBMITTED"], 2)  # the CSE draft and the untouched ECE slot alike
            self.assertEqual(sum(r["breakdown"].values()), r["summary"]["expected"])
            self.assertTrue(all(d["achievement_text"] == "" and d["submission_id"] is None for d in r["details"]))
            bulk = self.v.post("/api/v1/bulk-approvals/", {"idempotency_key": "k", "scope": "selection",
                                                            "items": [{"submission": sid, "revision": "00000000-0000-0000-0000-000000000000"}]}, format="json")
            self.assertEqual(bulk.json()["excluded"], [{"submission": sid, "reason": "not awaiting review (not submitted)"}])
            # a reopening request before any submission stays visible and decidable, without exposing a report
            asg = AnnualAssignment.objects.get(year=year, department=self.cse, kra__number=34)
            req = self.a.post(f"/api/v1/assignments/{asg.id}/periods/{self.p1.id}/reopen-requests/", {"reason": "Synthetic"}, format="json").json()
            listed = next(x for x in self.v.get("/api/v1/reopen-requests/").json() if x["id"] == req["id"])
            self.assertFalse(listed["submitted"])
            self.assertEqual(self.v.get(f"/api/v1/submissions/{listed['submission_id']}/").status_code, 404)
            self.assertEqual(self.v.post(f"/api/v1/reopen-requests/{req['id']}/decision/", {"approve": True}, format="json").status_code, 200)
            self.assertEqual(ReopenGrant.objects.filter(request_id=req["id"]).count(), 1)
