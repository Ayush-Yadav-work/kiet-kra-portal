"""Year/semester dropdowns, the Dean's name and the Nil submission date (D-079). SYNTHETIC names and data only."""
import copy
import unittest

from apps.catalogue.models import AnnualAssignment
from apps.reports import capabilities as caps
from apps.submissions.models import Submission, SubmissionRevision
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_reports import RENDERER, pdf_text

OCT1 = ist(2026, 10, 1, 10)  # 2026-27 P2 open


class LegacyMappingTests(unittest.TestCase):
    def term(self, key, field, dept="CSE"):
        schema = {"key": key, "sections": [{"fields": [{"id": field, "type": "text"}]}]}
        return caps.apply(schema, dept)["sections"][0]["fields"][0]

    def test_unambiguous_values_map_and_the_rest_are_kept(self):
        f = self.term("kra11", "year_semester")
        self.assertEqual([p["id"] for p in f["parts"]], ["year", "semester"])
        for text, want in (("2nd Year / Even Semester", {"year": "2nd Year", "semester": "Even Semester"}),
                           ("III year, odd sem", {"year": "3rd Year", "semester": "Odd Semester"}),
                           ("Semester 4", {"year": "2nd Year", "semester": "Even Semester"}),
                           ("1st year sem 1", {"year": "1st Year", "semester": "Odd Semester"}),
                           ("", {})):
            self.assertEqual(caps.map_legacy(text, f), want, text)
        for text in ("1st and 2nd year", "2nd year / semester 7", "Odd and even", "Final year students", "5th Year / Odd",
                     "Year 2 / semester 3 even", "2026-27"):
            self.assertEqual(caps.map_legacy(text, f), {"legacy": text}, text)  # never guessed, never discarded

    def test_options_follow_the_department_programme_length(self):
        self.assertEqual(self.term("kra11", "year_semester", "KSOM")["parts"][0]["options"], ["1st Year", "2nd Year"])
        self.assertEqual(len(self.term("kra11", "year_semester", "CSE")["parts"][0]["options"]), 4)
        self.assertEqual(caps.map_legacy("3rd Year / Odd Semester", self.term("kra11", "year_semester", "MCA")),
                         {"legacy": "3rd Year / Odd Semester"})
        sem = self.term("kra7", "semester")
        self.assertEqual([p["id"] for p in sem["parts"]], ["semester"])  # KRA 7 asks only Odd/Even
        self.assertEqual(caps.map_legacy("Odd semester", sem), {"semester": "Odd Semester"})
        self.assertEqual(caps.map_legacy("2nd year odd", sem), {"legacy": "2nd year odd"})
        self.assertEqual(self.term("kra33", "date")["type"], "text")  # unlisted fields are untouched


class DeanNameAndTermTests(PortalTestCase):
    def setUp(self):
        for u, (first, last) in ((self.dean_a, ("Synthetic", "Anand Rao")), (self.dean_b, ("Synthetic", "Bela Iyer"))):
            u.first_name, u.last_name = first, last
            u.save()
        self.a, self.b, self.v = self.client_for(self.dean_a), self.client_for(self.dean_b), self.client_for(self.vc)
        self.k11 = {d: AnnualAssignment.objects.get(department=d, kra__number=11, year__label="2026-27") for d in (self.cse, self.ece)}

    def preview(self, client, sid, **body):
        r = client.post(f"/api/v1/submissions/{sid}/preview/", body, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["html"]

    def kra11(self, client, dept, year_semester=None, hod="Mallory Spoofed"):
        sid = self.open_draft(client, self.k11[dept], self.p2)
        p = fx.kra11_payload(courses=1, modules=2)
        p["activities"][0]["hod"] = hod  # a client-supplied name is never stored or printed
        if year_semester is not None:
            p["activities"][0]["year_semester"] = year_semester
        r = self.save(client, sid, self.detail(client, sid)["edit_version"], payload=p, achievement_text="Synthetic 1 course")
        self.assertEqual(r.status_code, 200, r.content)
        return sid

    def test_two_departments_print_their_own_dean_and_the_selected_term(self):
        with frozen(OCT1):
            sa, sb = self.kra11(self.a, self.cse), self.kra11(self.b, self.ece, {"year": "2nd Year", "semester": "Even Semester"})
            self.assertEqual(Submission.objects.get(pk=sa).payload["activities"][0]["hod"], "")
            d = self.detail(self.a, sa)
            self.assertEqual(d["dean_name"], "Synthetic Anand Rao")
            self.assertEqual(d["payload"]["activities"][0]["year_semester"], {"year": "1st Year", "semester": "Odd Semester"})  # reload
            html = self.preview(self.a, sa)
            self.assertIn("Synthetic Anand Rao", html)
            self.assertIn("2026-27 / 1st Year / Odd Semester", html)
            self.assertNotIn("Mallory", html)
            spoof = copy.deepcopy(d["payload"])
            spoof["activities"][0]["hod"] = "Mallory Spoofed"
            self.assertNotIn("Mallory", self.preview(self.a, sa, payload=spoof))  # unsaved preview ignores it too
            html_b = self.preview(self.b, sb)
            self.assertIn("Synthetic Bela Iyer", html_b)
            self.assertIn("2026-27 / 2nd Year / Even Semester", html_b)
            self.assertNotIn("Anand", html_b)
            self.assertEqual(self.b.get(f"/api/v1/submissions/{sa}/").status_code, 404)  # department isolation
            for client, sid in ((self.a, sa), (self.b, sb)):
                r = client.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": self.detail(client, sid)["edit_version"]}, format="json")
                self.assertEqual(r.status_code, 200, r.content)
            rev = SubmissionRevision.objects.get(submission_id=sa)
            self.assertEqual(rev.snapshot["dean"], {"name": "Synthetic Anand Rao"})
            # later profile change: history keeps the submitted name; the VC sees the submitting Dean, not themself
            self.dean_a.last_name = "Renamed"
            self.dean_a.save()
            vc_html = self.preview(self.v, sa)
            self.assertIn("Synthetic Anand Rao", vc_html)
            self.assertNotIn("Renamed", vc_html)
            self.assertNotIn(self.vc.get_full_name(), vc_html)
            self.assertEqual(self.v.get(f"/api/v1/submissions/{sa}/").json().get("dean_name", ""), "")
            hist = self.v.get(f"/api/v1/submissions/{sa}/history/").json()
            self.assertIn("Synthetic Anand Rao", str(hist))

    def test_legacy_free_text_stays_visible_and_blocks_only_submission(self):
        with frozen(OCT1):
            sid = self.kra11(self.a, self.cse, "Final year students")  # old free text still saves as a draft
            d = self.detail(self.a, sid)
            self.assertEqual(d["payload"]["activities"][0]["year_semester"], {"legacy": "Final year students"})
            self.assertIn("2026-27 / Final year students", self.preview(self.a, sid))  # not discarded
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
            self.assertIn("could not be matched", fe["activities.0.year_semester"][0])
            kept = d["payload"]  # the editor's shape (legacy kept under "legacy") also saves
            self.assertEqual(self.save(self.a, sid, d["edit_version"], payload=kept).status_code, 200)
            kept["activities"][0]["year_semester"] = {"year": "1st Year", "semester": "", "legacy": "Final year students"}
            self.save(self.a, sid, self.detail(self.a, sid)["edit_version"], payload=kept)
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
            self.assertEqual(fe["activities.0.year_semester"], ["Select the semester."])
            bad = copy.deepcopy(kept)
            bad["activities"][0]["year_semester"] = {"year": "7th Year", "semester": "Odd Semester"}
            self.assertEqual(self.save(self.a, sid, self.detail(self.a, sid)["edit_version"], payload=bad).status_code, 400)
            # a stored historical revision keeps its free text and its typed HoD name (no snapshot name)
            d = self.detail(self.a, sid)
            kept["activities"][0]["year_semester"] = {"year": "1st Year", "semester": "Odd Semester"}
            self.save(self.a, sid, d["edit_version"], payload=kept)
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": d["edit_version"] + 1}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            rev = SubmissionRevision.objects.get(submission_id=sid)
            legacy = copy.deepcopy(rev.payload)
            legacy["activities"][0].update(year_semester="I yr / sem-II", hod="Typed Historical Head")
            snap = {k: v for k, v in rev.snapshot.items() if k != "dean"}
            SubmissionRevision.objects.filter(pk=rev.pk).update(payload=legacy, snapshot=snap)
            html = self.preview(self.v, sid)
            self.assertIn("2026-27 / I yr / sem-II", html)
            self.assertIn("Typed Historical Head", html)

    def test_missing_profile_name_allows_drafts_but_not_submission(self):
        self.dean_a.first_name = self.dean_a.last_name = ""
        self.dean_a.save()
        with frozen(OCT1):
            sid = self.kra11(self.a, self.cse)
            self.assertEqual(self.detail(self.a, sid)["dean_name"], "")  # never the username
            self.assertNotIn(self.dean_a.username, self.preview(self.a, sid))
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": self.detail(self.a, sid)["edit_version"]}, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertIn("profile", r.json()["field_errors"]["dean_name"][0])
            k33 = self.open_draft(self.a, self.asg_a, self.p2)  # Nil reports print the Head/Dean name too
            v = self.save(self.a, k33, self.detail(self.a, k33)["edit_version"], is_nil=True, nil_reason="Synthetic").json()["edit_version"]
            self.assertIn("dean_name", self.a.post(f"/api/v1/submissions/{k33}/validate/").json()["field_errors"])
            self.assertEqual(self.a.post(f"/api/v1/submissions/{k33}/submit/", {"edit_version": v}, format="json").status_code, 400)


class NilDateTests(PortalTestCase):
    def setUp(self):
        self.dean_a.first_name, self.dean_a.last_name = "Synthetic", "Anand Rao"
        self.dean_a.save()
        self.a, self.v = self.client_for(self.dean_a), self.client_for(self.vc)

    def html(self, client, sid, **body):
        return client.post(f"/api/v1/submissions/{sid}/preview/", body, format="json").json()["html"]

    def test_draft_placeholder_ist_date_and_resubmission(self):
        with frozen(OCT1):
            sid = self.open_draft(self.a, self.asg_a, self.p2)
            v = self.save(self.a, sid, 0, is_nil=True, nil_reason="Synthetic: no activity").json()["edit_version"]
            draft = self.html(self.a, sid)
            self.assertIn("Date: <span class=\"val\">Set on submission", draft)
            self.assertIn("Synthetic Anand Rao", draft)
        at = ist(2026, 10, 2, 0, 30)  # 1 October 19:00 UTC: the IST date is 2 October
        with frozen(at):
            self.assertEqual(self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json").status_code, 200)
        rev1 = SubmissionRevision.objects.get(submission_id=sid)
        with frozen(ist(2026, 10, 5, 9)):  # previews/exports later never move the date
            self.assertIn("2 October 2026", self.html(self.a, sid))
            self.assertIn("2 October 2026", self.html(self.v, sid))
            r = self.v.post(f"/api/v1/submissions/{sid}/review/", {"revision": str(rev1.id), "decision": "REJECT", "reason": "Synthetic"}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            corr = self.html(self.a, sid)
            self.assertIn("Set on resubmission (previous submission: 2 October 2026)", corr)
            self.assertIn("2 October 2026", self.html(self.v, sid))  # the VC sees the submitted version (D-078)
        with frozen(ist(2026, 10, 20, 23, 59)):
            v = self.detail(self.a, sid)["edit_version"]
            self.assertEqual(self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json").status_code, 200)
            rev2 = Submission.objects.get(pk=sid).current_revision
            self.assertEqual(rev2.sequence, 2)
            self.assertIn("20 October 2026", self.html(self.v, sid))
            self.assertIn("2 October 2026", self.html(self.v, sid, revision=str(rev1.id)))  # earlier version unchanged
        with frozen(ist(2026, 10, 25, 11)):
            self.v.post(f"/api/v1/submissions/{sid}/review/", {"revision": str(rev2.id), "decision": "APPROVE"}, format="json")
            html = self.html(self.v, sid)
            self.assertIn("Date: <span class=\"val\">20 October 2026", html)  # submission date, not the approval date
            self.assertIn("25 Oct 2026", html)  # the verification line keeps the approval time

    @unittest.skipUnless(RENDERER, "renderer not running")
    def test_nil_pdf_shows_name_and_date(self):
        with frozen(OCT1):
            sid = self.open_draft(self.a, self.asg_a, self.p2)
            v = self.save(self.a, sid, 0, is_nil=True, nil_reason="Synthetic: no activity").json()["edit_version"]
            self.assertIn("Set on submission", pdf_text(b"".join(self.a.get(f"/api/v1/submissions/{sid}/export/").streaming_content)))
            self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": v}, format="json")
            text = pdf_text(b"".join(self.v.get(f"/api/v1/submissions/{sid}/export/").streaming_content))
        self.assertIn("Head/Dean: Synthetic Anand Rao", " ".join(text.split()))
        self.assertIn("Date: 1 October 2026", " ".join(text.split()))
