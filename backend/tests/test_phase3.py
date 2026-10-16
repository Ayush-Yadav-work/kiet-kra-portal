"""Phase 3 template families: KRA 20 (wide records table), KRA 7 (survey averages), KRA 32 (conditional records).

Each KRA runs the same workflow checks (draft save/reload, preview, submit, reject after close with 72 h grant,
resubmit, approve, Nil, PDF) plus its own field rules. SYNTHETIC data only.
"""
import copy
import datetime

import pymupdf

from apps.catalogue.models import AnnualAssignment
from apps.submissions.models import ReopenGrant, SubmissionRevision
from tests import fixtures as fx
from tests.base import PortalTestCase, frozen, ist
from tests.test_reports import RENDERER, pdf_text


class WorkflowMixin:
    kra = None
    evidence = ()  # categories satisfying the template's minimum set
    payload = None  # () -> valid complete payload
    expect_text = ()  # strings the preview/PDF must contain

    def setUp(self):
        self.asg = AnnualAssignment.objects.get(department=self.cse, kra__number=self.kra, year__label="2026-27")
        self.a, self.vc = self.client_for(self.dean_a), self.client_for(self.vc_user())

    def vc_user(self):
        return self.vc if not hasattr(self, "_vc") else self._vc

    def new_draft(self):
        with frozen(ist(2026, 10, 1)):
            return self.open_draft(self.a, self.asg, self.p2)

    def errors_for(self, payload, strict=True, sid=None):
        sid = sid or self.new_draft()
        with frozen(ist(2026, 10, 1)):
            v = self.detail(self.a, sid)["edit_version"]
            r = self.save(self.a, sid, v, payload=payload)
            if r.status_code != 200 or not strict:
                return r.json().get("field_errors", {}) if r.status_code != 200 else {}
            return self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]

    def submit_complete(self, sid, at):
        with frozen(at):
            d = self.detail(self.a, sid)
            r = self.save(self.a, sid, d["edit_version"], payload=self.payload(), achievement_text="Synthetic: as entered")
            self.assertEqual(r.status_code, 200, r.content)
            for cat in self.evidence:
                ok = self.a.post(f"/api/v1/submissions/{sid}/evidence/", {"source_type": "DRIVE_LINK",
                                 "drive_url": "https://drive.google.com/file/d/synthetic", "category": cat,
                                 "label": f"Synthetic {cat}"}, format="json")
                self.assertEqual(ok.status_code, 201, ok.content)
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": r.json()["edit_version"]}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            return r.json()

    def test_template_assigned_and_schema_served(self):
        self.assertIsNotNone(self.asg.template_version)
        tv = self.asg.template_version
        r = self.a.get(f"/api/v1/templates/{tv.key}/{tv.version}/")
        self.assertEqual(r.status_code, 200)
        # Another department's Dean is also assigned this KRA, so the schema is readable; data stays scoped.
        self.assertEqual(self.client_for(self.dean_b).get(f"/api/v1/templates/{tv.key}/{tv.version}/").status_code, 200)

    def test_draft_save_reload_and_preview(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, 0, payload=self.payload())
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(self.detail(self.a, sid)["payload"], self.payload())  # exact round trip
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        for text in self.expect_text:
            self.assertIn(text, html)

    def test_strict_validation_requires_fields_and_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload={"activities": [{}]})
            fe = self.a.post(f"/api/v1/submissions/{sid}/validate/").json()["field_errors"]
        self.assertIn("achievement_text", fe)
        self.assertIn("evidence", fe)
        self.assertTrue(any(k.startswith("activities.0.") for k in fe), fe)

    def test_full_workflow_reject_after_close_grant_resubmit_approve(self):
        sid = self.new_draft()
        d = self.submit_complete(sid, ist(2026, 10, 20))
        rev1 = d["current_revision"]["id"]
        at = ist(2026, 11, 3, 10)  # period closed
        with frozen(at):
            r = self.vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev1, "decision": "REJECT",
                             "reason": "Synthetic correction needed", "grant_reopen": True}, format="json")
            self.assertEqual(r.json()["status"], "REJECTED")
        self.assertEqual(ReopenGrant.objects.filter(submission_id=sid).count(), 1)
        with frozen(at + datetime.timedelta(hours=5)):
            d = self.detail(self.a, sid)
            self.assertTrue(d["editable"])
            self.assertEqual(self.save(self.a, sid, d["edit_version"], remarks="corrected").status_code, 200)
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": d["edit_version"] + 1}, format="json")
            self.assertEqual(r.json()["current_revision"]["sequence"], 2)
            rev2 = r.json()["current_revision"]["id"]
            self.assertEqual(self.vc.post(f"/api/v1/submissions/{sid}/review/", {"revision": rev2, "decision": "APPROVE"},
                                          format="json").json()["status"], "APPROVED")
        self.assertEqual(SubmissionRevision.objects.get(pk=rev1).payload, self.payload())  # immutable history
        self.assertEqual(self.detail(self.a, sid)["period_entries"][1]["achievement_text"], "Synthetic: as entered")

    def test_nil_needs_reason_not_evidence(self):
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, is_nil=True, nil_reason="Synthetic: none this period")
            r = self.a.post(f"/api/v1/submissions/{sid}/submit/", {"edit_version": 1}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertIn("NIL REPORT", html)

    def test_pdf_export(self):
        if not RENDERER:
            self.skipTest("internal renderer not running")
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            self.save(self.a, sid, 0, payload=self.payload())
            r = self.a.get(f"/api/v1/submissions/{sid}/export/")
            self.assertEqual(r.status_code, 200)
            data = b"".join(r.streaming_content)
        doc = pymupdf.open(stream=data, filetype="pdf")
        text = " ".join(pdf_text(data).split()).replace("- ", "-")  # cells wrap (also after hyphens): normalise
        for t in self.expect_text:
            self.assertIn(" ".join(t.split()).replace("- ", "-"), text)
        self.assertIn("Pending approval", text)
        fonts = {f[3] for i in range(doc.page_count) for f in doc.get_page_fonts(i)}
        self.assertTrue(fonts and all("Tinos" in f for f in fonts), fonts)  # C12: no system-font fallback
        self.check_page(doc[0])

    def check_page(self, page):
        pass


class KRA20Tests(WorkflowMixin, PortalTestCase):
    kra = 20
    evidence = ("Training Certificate",)
    payload = staticmethod(lambda: fx.kra20_payload(rows=3))
    expect_text = ("Test Faculty 1 Ñúñez-Śarmā", "Example Industries Pvt Ltd Unit 1", "01 Sep 2026", "CSE")

    def check_page(self, page):
        self.assertGreater(page.rect.width, page.rect.height)  # repaired onto landscape A4

    def test_row_rules_and_columns(self):
        p = fx.kra20_payload(rows=2)
        p["activities"][0]["trainings"][0]["end_date"] = "2026-08-01"  # before start
        p["activities"][0]["trainings"][1]["faculty_name"] = ""
        p["activities"][0]["trainings"][1]["department"] = "ECE"  # auto column cannot be entered
        fe = self.errors_for(p, strict=False)
        self.assertNotIn("activities.0.trainings.0.end_date", fe)  # draft still saves
        self.assertIn("activities.0.trainings.1.department", fe)
        del p["activities"][0]["trainings"][1]["department"]
        self.assertEqual(self.errors_for(p)["activities.0.trainings.0.end_date"], ["End date cannot be before the start date."])
        p["activities"][0]["trainings"][0]["end_date"] = "2026-09-30"
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.trainings.1.faculty_name"], ["Required."])
        self.assertNotIn("activities.0.trainings.0.certificate_no", fe)  # optional column
        p["activities"][0]["trainings"][0]["mode"] = "Hybrid"
        self.assertIn("activities.0.trainings.0.mode", self.errors_for(p, strict=False))

    def test_row_cap(self):
        fe = self.errors_for(fx.kra20_payload(rows=101), strict=False)
        self.assertEqual(fe["activities.0.trainings"], ["At most 100 rows."])


class KRA7Tests(WorkflowMixin, PortalTestCase):
    kra = 7
    evidence = ("Consolidated Feedback Analysis",)
    payload = staticmethod(fx.kra7_payload)
    expect_text = ("Consolidated response of 38 of 42 faculty members", "Not applicable (consolidated report)",
                   "3.80", "4.10", "7.85 / 10", "Discussion in BoS")

    def test_decimals_kept_exact_never_rounded(self):
        p = fx.kra7_payload()
        r = p["activities"][0]["ratings"]
        r[0], r[1], r[2] = "4.255", "5.01", "0.99"
        p["activities"][0]["overall_satisfaction"] = "10.5"
        self.assertEqual(self.errors_for(p, strict=False), {})  # draft keeps "4.255" exactly as typed
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.ratings.0"], ["Use at most 2 decimal places (values are not rounded)."])
        self.assertEqual(fe["activities.0.ratings.1"], ["Must be between 1 and 5."])
        self.assertEqual(fe["activities.0.ratings.2"], ["Must be between 1 and 5."])
        self.assertIn("activities.0.overall_satisfaction", fe)
        r[0], r[1], r[2] = "abc", "4.5", "4"
        p["activities"][0]["overall_satisfaction"] = "7.85"
        self.assertEqual(self.errors_for(p, strict=False), {"activities.0.ratings.0": ["Must be a number."]})
        sid = self.new_draft()
        p["activities"][0]["ratings"][0] = "4.255"
        self.errors_for(p, strict=False, sid=sid)
        self.assertEqual(self.detail(self.a, sid)["payload"]["activities"][0]["ratings"][0], "4.255")  # not rounded

    def test_all_statements_required_and_respondents_rule(self):
        p = fx.kra7_payload()
        p["activities"][0]["ratings"] = ["4"] * 9  # one statement missing
        p["activities"][0]["respondents"] = 50
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.ratings.9"], ["Enter the consolidated average."])
        self.assertEqual(fe["activities.0.respondents"], ["Respondents cannot exceed the number of faculty members surveyed."])
        self.assertNotIn("activities.0.suggestions", fe)  # optional

    def test_ratings_list_cannot_exceed_statements(self):
        p = fx.kra7_payload()
        p["activities"][0]["ratings"] = ["4"] * 11
        self.assertEqual(self.errors_for(p, strict=False)["activities.0.ratings"], ["Invalid ratings."])


class KRA32Tests(WorkflowMixin, PortalTestCase):
    kra = 32
    evidence = ("Donation/Acknowledgement Letter",)
    payload = staticmethod(lambda: fx.kra32_payload(rows=4))
    expect_text = ("Test Alumna 1 Zoë Łukasz", "25000.00", "2500.5", "2 synthetic oscilloscopes",
                   "Amount (₹)", "no totals are calculated")

    def rows(self):
        return copy.deepcopy(fx.kra32_payload(rows=2))  # row 0 financial, row 1 equipment

    def test_financial_rows_require_payment_fields(self):
        p = self.rows()
        fin = p["activities"][0]["contributions"][0]
        for k in ("amount", "payment_mode", "receipt_no", "transaction_ref"):
            fin[k] = ""
        fe = self.errors_for(p)
        for k in ("amount", "payment_mode", "receipt_no", "transaction_ref"):
            self.assertEqual(fe[f"activities.0.contributions.0.{k}"], ["Required."])
        self.assertNotIn("activities.0.contributions.0.item_details", fe)  # not applicable to financial

    def test_non_financial_rows_need_details_and_no_payment(self):
        p = self.rows()
        eq = p["activities"][0]["contributions"][1]
        eq["item_details"] = ""
        eq["amount"] = "5000"  # stale value from a type change
        fe = self.errors_for(p)
        self.assertEqual(fe["activities.0.contributions.1.item_details"], ["Required."])
        self.assertEqual(fe["activities.0.contributions.1.amount"], ["Not applicable for this contribution type; leave blank."])
        self.assertNotIn("activities.0.contributions.1.receipt_no", fe)

    def test_amount_rules_and_no_totals(self):
        p = self.rows()
        fin = p["activities"][0]["contributions"][0]
        fin["amount"] = "100.555"
        self.assertEqual(self.errors_for(p)["activities.0.contributions.0.amount"],
                         ["Use at most 2 decimal places (values are not rounded)."])
        fin["amount"] = "0"
        self.assertEqual(self.errors_for(p)["activities.0.contributions.0.amount"], ["Must be between 0.01 and 1000000000."])
        fin["amount"] = "Rs 500"
        self.assertEqual(self.errors_for(p, strict=False)["activities.0.contributions.0.amount"], ["Must be a number."])
        sid = self.new_draft()
        with frozen(ist(2026, 10, 1)):
            r = self.save(self.a, sid, self.detail(self.a, sid)["edit_version"], payload=fx.kra32_payload(rows=4))
            self.assertEqual(r.status_code, 200, r.content)
            html = self.a.post(f"/api/v1/submissions/{sid}/preview/", {}, format="json").json()["html"]
        self.assertNotIn("Total", html.split("Records in this report")[1].split("Verification")[0].replace("no totals", ""))
        self.assertGreaterEqual(html.count('<span class="na">NA</span>'), 8)  # 4 payment cells x 2 non-financial rows


class TemplateSeedTests(PortalTestCase):
    def test_used_template_is_never_rewritten_by_seed(self):
        import io
        from django.core.management import call_command
        from apps.catalogue.models import TemplateVersion

        a = self.client_for(self.dean_a)
        asg = AnnualAssignment.objects.get(department=self.cse, kra__number=20, year__label="2026-27")
        with frozen(ist(2026, 10, 1)):
            self.open_draft(a, asg, self.p2)
        tv = asg.template_version
        TemplateVersion.objects.filter(pk=tv.pk).update(title="changed in place")
        tv.refresh_from_db()
        schema = dict(tv.schema, title="changed in place")
        TemplateVersion.objects.filter(pk=tv.pk).update(schema=schema)
        err = io.StringIO()
        call_command("seed_catalogue", stdout=io.StringIO(), stderr=err)
        self.assertIn("in use", err.getvalue())
        tv.refresh_from_db()
        self.assertEqual(tv.schema["title"], "changed in place")  # kept, not rewritten
