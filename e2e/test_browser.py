"""Browser regression tests. Run them only through the isolated runner, which gives them their own database and servers:

  python e2e/run_isolated.py            # disposable <db>_e2e database, Django :8001, Vite :5174 (D-067)

SYNTHETIC values only; nothing reaches the developer's working database.
"""
import json
import os
import time
import re
import sys
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))  # synthetic fixtures

ROOT = Path(__file__).resolve().parent.parent
if os.environ.get("KRA_E2E_ISOLATED") != "1":  # the suite writes data: never against the developer's working database
    sys.exit("Run the browser tests through e2e/run_isolated.py (it uses a separate, disposable database).")
BASE = os.environ["KRA_E2E_BASE"]
CREDS = dict(re.findall(r"^(?:VC|DEAN)\s+(\S+)\s+(\S+)$", Path(os.environ["KRA_E2E_CREDENTIALS"]).read_text(), re.M))


def login(page, portal, username):
    page.goto(f"{BASE}/{portal}/login")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password", exact=True).fill(CREDS[username])
    page.get_by_role("button", name="Sign in").click()


def api(page, method, path, body=None):
    token = next(c["value"] for c in page.context.cookies() if c["name"] == "csrftoken")
    r = page.request.fetch(f"{BASE}/api/v1{path}", method=method, headers={"X-CSRFToken": token, "Content-Type": "application/json"},
                           data=json.dumps(body) if body is not None else None)
    return r.status, (r.json() if "json" in r.headers.get("content-type", "") else None)


def open_ece_kra(page, kra_number):
    """Open the ECE workspace for the open period; returns submission id."""
    page.goto(f"{BASE}/dean/dashboard")
    _, rows = api(page, "GET", "/periods/?year=2026-27")
    period = next(p for p in rows["results"] if p["is_open"])
    _, data = api(page, "GET", f"/assignments/?year=2026-27&period={period['id']}")
    asg = next(a for a in data["results"] if a["kra"]["number"] == kra_number)
    page.goto(f"{BASE}/dean/kra/{asg['id']}/{period['id']}")
    page.get_by_role("tab", name="Report").wait_for()
    page.wait_for_load_state("networkidle")  # workspace fully loaded before typing (slow machines)
    _, info = api(page, "GET", f"/assignments/{asg['id']}/periods/{period['id']}/")
    return info["submission_id"]


def open_info(page, assignment_id, period_id):
    """Submission id of an assignment/period workspace (row already created by opening it)."""
    _, info = api(page, "GET", f"/assignments/{assignment_id}/periods/{period_id}/")
    return info["submission_id"]


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.ctx = self.browser.new_context(viewport={"width": 1400, "height": 900})
        self.page = self.ctx.new_page()

    def tearDown(self):
        self.ctx.close()

    def test_portals_reject_wrong_role(self):
        p = self.page
        login(p, "vc", "demo.dean.ece")
        # Repeated runs within 15 min hit the real rate limiter; either message proves the rejection.
        expect(p.get_by_role("alert")).to_contain_text(re.compile("Invalid username or password for this portal|Too many failed attempts"))
        self.assertEqual(p.request.get(f"{BASE}/api/v1/auth/me/").status, 401)  # no session was created
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url(f"{BASE}/dean/dashboard")
        p.goto(f"{BASE}/vc/dashboard")
        p.wait_for_url(f"{BASE}/dean/dashboard")  # typed URL cannot cross roles

    def test_c7_preview_keeps_scroll_while_editing_50_row_table(self):
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 33)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        rows = [{"alumni_name": f"Test Alumnus {i}", "batch_programme": "2019", "organization": "Example Org",
                 "nature": "Mentoring", "date_activity": "1 Oct", "students_benefited": i} for i in range(50)]
        status, _ = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"],
                        "payload": {"activities": [{"event_name": "Synthetic 50-row event", "engagements": rows}]}})
        self.assertEqual(status, 200)
        p.reload()
        frame = p.frame_locator("iframe[title='Report preview']")
        expect(frame.get_by_text("Test Alumnus 49")).to_be_visible(timeout=10000)
        handle = p.locator("iframe[title='Report preview']").element_handle().content_frame()
        handle.evaluate("window.scrollTo(0, 1500)")
        before = handle.evaluate("window.scrollY")
        self.assertGreater(before, 1000)
        with p.expect_response(lambda r: "/preview/" in r.url and r.status == 200):
            p.locator("input[name='activities.0.engagements.25.alumni_name']").fill("Edited Alumnus 25")
        frame.get_by_text("Edited Alumnus 25").wait_for()
        p.wait_for_timeout(300)
        after = p.locator("iframe[title='Report preview']").element_handle().content_frame().evaluate("window.scrollY")
        self.assertAlmostEqual(after, before, delta=5, msg="preview scroll position must be preserved (C7)")

    def test_c3_evidence_upload_during_autosave_no_conflict(self):
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 33)
        p.locator("input[name='activities.0.chapter_name']").fill("Synthetic chapter typed before upload")
        # Upload while the debounced autosave is pending/in flight, through the Evidence tab (tab switch flushes).
        p.get_by_role("tab", name="Evidence").click()
        p.get_by_label("Category").select_option("Photographs")
        p.get_by_label("Label").fill("Synthetic photo")
        p.set_input_files("#ev-file", files=[{"name": "photo.png", "mimeType": "image/png",
                                               "buffer": b"\x89PNG\r\n\x1a\n" + b"0" * 512}])
        p.get_by_role("button", name="Add evidence").click()
        expect(p.get_by_text("Synthetic photo").first).to_be_visible()
        p.get_by_role("tab", name="Report").click()
        p.locator("input[name='activities.0.chapter_name']").fill("Synthetic chapter typed after upload")
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        self.assertEqual(p.get_by_text("Conflict").count(), 0)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        self.assertEqual(d["payload"]["activities"][0]["chapter_name"], "Synthetic chapter typed after upload")

    # ---- Phase 3 templates ----
    def test_kra32_conditional_payment_fields(self):
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 32)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": {"activities": [{}]}})
        p.reload()
        p.get_by_role("button", name="+ Add record").click()
        row = "activities.0.contributions.0"
        p.locator(f"select[name='{row}.contribution_type']").select_option("Financial Contribution")
        p.locator(f"input[name='{row}.amount']").fill("1500.75")
        expect(p.get_by_label("Item/Asset Details (non-financial): not applicable")).to_be_visible()
        p.locator(f"select[name='{row}.contribution_type']").select_option("Equipment/Asset")
        expect(p.get_by_label("Amount (₹): not applicable")).to_be_visible()  # payment fields switch to NA
        p.locator(f"textarea[name='{row}.item_details']").fill("Synthetic projector")
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        _, d = api(p, "GET", f"/submissions/{sid}/")
        rec = d["payload"]["activities"][0]["contributions"][0]
        self.assertEqual(rec["amount"], "")  # stale payment value cleared, not silently kept
        self.assertEqual(rec["item_details"], "Synthetic projector")
        frame = p.frame_locator("iframe[title='Report preview']")
        expect(frame.get_by_text("Synthetic projector")).to_be_visible(timeout=10000)

    def test_kra7_decimal_kept_exactly_through_autosave_and_reload(self):
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 7)
        p.locator("[id='activities.0.consolidated_by']").fill(f"Test run {int(time.time())}")  # forces a real save
        p.locator("[id='activities.0.ratings.0']").fill("3.80")
        p.locator("[id='activities.0.overall_satisfaction']").fill("7.50")
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        p.reload()
        expect(p.locator("[id='activities.0.ratings.0']")).to_have_value("3.80")
        expect(p.locator("[id='activities.0.overall_satisfaction']")).to_have_value("7.50")
        frame = p.frame_locator("iframe[title='Report preview']")
        expect(frame.get_by_text("7.50 / 10")).to_be_visible(timeout=10000)

    def test_kra20_card_editor_saves_record(self):
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 20)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": {"activities": [{}]}})
        p.reload()
        p.get_by_role("button", name="+ Add record").click()
        p.get_by_role("button", name="+ Add record").click()
        p.locator("input[name='activities.0.trainings.1.faculty_name']").fill("Synthetic Faculty Two")
        p.locator("input[name='activities.0.trainings.1.start_date']").fill("2026-09-01")
        p.locator("input[name='activities.0.trainings.1.end_date']").fill("2026-08-01")  # bad order still saves as draft
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        _, d = api(p, "GET", f"/submissions/{sid}/")
        self.assertEqual(len(d["payload"]["activities"][0]["trainings"]), 2)
        _, v = api(p, "POST", f"/submissions/{sid}/validate/")
        self.assertIn("activities.0.trainings.1.end_date", v["field_errors"])

    def test_kra1_2_3_save_reload_preview_export(self):
        """Course family: each KRA keeps its own draft; save, reload, preview and export work for all three."""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sids = {}
        for n in (1, 2, 3):
            sid = sids[n] = open_ece_kra(p, n)
            name = f"activities.0.course_name"
            label = f"Synthetic browser course KRA {n} {int(time.time())}"  # unique per run so a save is always needed
            p.locator(f"input[name='{name}']").fill(label)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator(f"input[name='{name}']")).to_have_value(label)
            frame = p.frame_locator("iframe[title='Report preview']")
            expect(frame.get_by_text(label)).to_be_visible(timeout=10000)
            term = {1: "Detail of New Courses", 2: "Detail of Value Added Courses", 3: "Detail of Online Courses (MOOCs)"}[n]
            expect(frame.get_by_text(term)).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"))
        self.assertEqual(len(set(sids.values())), 3)
        for n in (1, 2, 3):  # no value leaked between KRAs
            _, d = api(p, "GET", f"/submissions/{sids[n]}/")
            self.assertTrue(d["payload"]["activities"][0]["course_name"].startswith(f"Synthetic browser course KRA {n} "))

    def test_kra36_37_save_reload_preview_export_and_vc_review(self):
        """FDP/STP family: Dean save/reload/preview/export for KRAs 36 and 37; KRA 37 submitted from the UI and approved
        by the VC on the real review page; the exported PDF then carries the VC verification label."""
        import pymupdf
        from tests.fixtures import kra3637_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sids = {}
        for n in (36, 37):
            sid = sids[n] = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            if d["status"] in ("SUBMITTED", "APPROVED"):  # left by a previous run: VC returns it so the run can repeat
                vc = self.browser.new_context()
                vp = vc.new_page()
                login(vp, "vc", "demo.vc")
                vp.wait_for_url("**/vc/dashboard")
                decision = "APPROVE" if d["status"] == "SUBMITTED" else "RETURN"
                api(vp, "POST", f"/submissions/{sid}/review/", {"revision": d["current_revision"]["id"], "decision": decision,
                                                                "reason": "Synthetic e2e reset"})
                if decision == "APPROVE":
                    api(vp, "POST", f"/submissions/{sid}/review/", {"revision": d["current_revision"]["id"],
                                                                    "decision": "RETURN", "reason": "Synthetic e2e reset"})
                vc.close()
                p.reload()
                p.wait_for_load_state("networkidle")
            title = f"Synthetic browser programme KRA {n} {int(time.time())}"
            p.locator("input[name='activities.0.programme_title']").fill(title)
            expect(p.locator("input[name='activities.0.programme_title']")).to_have_value(title)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator("input[name='activities.0.programme_title']")).to_have_value(title)
            frame = p.frame_locator("iframe[title='Report preview']")
            expect(frame.get_by_text(title)).to_be_visible(timeout=10000)
            expect(frame.get_by_text({36: "Staff Participation", 37: "Faculty Participation"}[n])).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"))
        self.assertNotEqual(sids[36], sids[37])

        # Complete KRA 37 through the API, then submit with the UI button.
        sid = sids[37]
        _, d = api(p, "GET", f"/submissions/{sid}/")
        payload = kra3637_payload(37)
        payload["activities"][0]["programme_title"] = title
        status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                         "achievement_text": "1 (synthetic)"})
        self.assertEqual(status, 200, body)
        p.reload()
        p.once("dialog", lambda dlg: dlg.accept())
        p.get_by_role("button", name=re.compile("^(Submit|Resubmit)$")).click()
        expect(p.get_by_text("Read-only: submitted and awaiting VC review.")).to_be_visible(timeout=10000)

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900})
        vp = vc.new_page()
        login(vp, "vc", "demo.vc")
        vp.wait_for_url("**/vc/dashboard")
        vp.goto(f"{BASE}/vc/review/{sid}")
        vp.get_by_role("button", name="Approve").click()
        expect(vp.get_by_text("Approved", exact=True).first).to_be_visible(timeout=10000)
        vc.close()

        r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
        text = "".join(pg.get_text() for pg in pymupdf.open(stream=r.body(), filetype="pdf"))
        self.assertIn("Verified by VC - Demo Vice-Chancellor", text)

    def test_kra8_9_10_surveys_save_reload_preview_export(self):
        """Survey family: KRAs 8 and 10 save/reload/preview/export; KRA 9 variant ticking in the UI keeps 9b data
        when deselected and the preview shows only the selected variant(s)."""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        stamp = int(time.time())
        frame = p.frame_locator("iframe[title='Report preview']")
        for n in (8, 10):
            sid = open_ece_kra(p, n)
            p.locator("[id='activities.0.collection_period']").fill(f"Synthetic period {n} {stamp}")
            p.locator("[id='activities.0.ratings.0']").fill("4.50")
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator("[id='activities.0.ratings.0']")).to_have_value("4.50")
            expect(frame.get_by_text(f"Synthetic period {n} {stamp}")).to_be_visible(timeout=10000)
            expect(frame.get_by_text("Curriculum Feedback Survey Form").first).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"))

        sid = open_ece_kra(p, 9)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": {"activities": [{}]}})
        p.reload()
        box9a = p.get_by_label("9a — Alumni with more than 4 years professional experience", exact=True)
        box9b = p.get_by_label("9b — Alumni with less than 4 years professional experience", exact=True)
        box9a.check()
        box9b.check()
        p.locator("[id='activities.0.v9a_ratings.0']").fill("4.25")
        p.locator("[id='activities.0.v9b_ratings.0']").fill("3.75")
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        expect(frame.get_by_text("ALUMNI FEEDBACK FORM (9b)")).to_be_visible(timeout=10000)
        box9b.uncheck()  # deselect 9b: its data stays, the preview drops it
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        p.reload()
        expect(p.locator("[id='activities.0.v9b_ratings.0']")).to_have_value("3.75")
        expect(frame.get_by_text("ALUMNI FEEDBACK FORM (9a)")).to_be_visible(timeout=10000)
        expect(frame.get_by_text("ALUMNI FEEDBACK FORM (9b)")).to_have_count(0)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        act = d["payload"]["activities"][0]
        self.assertEqual((act["v9a_ratings"][0], act["v9b_ratings"][0]), ("4.25", "3.75"))
        r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
        self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"))


    def test_kra19_save_reload_preview_export_and_vc_review(self):
        """KRA 19: two visits in one submission; Dean save/reload/preview/export; UI submit; VC approves on the review page."""
        import pymupdf
        from tests.fixtures import kra19_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 19)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        if d["status"] in ("SUBMITTED", "APPROVED"):  # left by a previous run: VC returns it so the run can repeat
            vc = self.browser.new_context()
            vp = vc.new_page()
            login(vp, "vc", "demo.vc")
            vp.wait_for_url("**/vc/dashboard")
            for decision in (["APPROVE"] if d["status"] == "SUBMITTED" else []) + ["RETURN"]:
                api(vp, "POST", f"/submissions/{sid}/review/", {"revision": d["current_revision"]["id"], "decision": decision,
                                                                "reason": "Synthetic e2e reset"})
            vc.close()
            p.reload()
            p.wait_for_load_state("networkidle")
            _, d = api(p, "GET", f"/submissions/{sid}/")
        status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": kra19_payload(2),
                                                                         "achievement_text": "Synthetic: 116 student participations"})
        self.assertEqual(status, 200, body)
        p.reload()
        p.wait_for_load_state("networkidle")
        name = f"Synthetic browser plant {int(time.time())}"
        p.locator("input[name='activities.0.industry_name']").fill(name)
        expect(p.locator("input[name='activities.0.industry_name']")).to_have_value(name)
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        p.reload()
        expect(p.locator("input[name='activities.0.industry_name']")).to_have_value(name)
        frame = p.frame_locator("iframe[title='Report preview']")
        expect(frame.get_by_text(name).first).to_be_visible(timeout=10000)
        expect(frame.get_by_text("Visit 2 of 2")).to_be_visible()
        r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
        self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"))

        p.once("dialog", lambda dlg: dlg.accept())
        p.get_by_role("button", name=re.compile("^(Submit|Resubmit)$")).click()
        expect(p.get_by_text("Read-only: submitted and awaiting VC review.")).to_be_visible(timeout=10000)

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900})
        vp = vc.new_page()
        login(vp, "vc", "demo.vc")
        vp.wait_for_url("**/vc/dashboard")
        vp.goto(f"{BASE}/vc/review/{sid}")
        vp.get_by_role("button", name="Approve").click()
        expect(vp.get_by_text("Approved", exact=True).first).to_be_visible(timeout=10000)
        vc.close()

        r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
        text = "".join(pg.get_text() for pg in pymupdf.open(stream=r.body(), filetype="pdf"))
        self.assertIn("Verified by VC - Demo Vice-Chancellor", text)
        self.assertIn(name, text)

    def test_kra18_17_13_save_reload_preview_export(self):
        """Industry-collaboration batch: for KRAs 18, 17 and 13 a complete synthetic draft is stored, one field edited in the UI,
        saved, reloaded, previewed and exported."""
        from tests.fixtures import kra13iab_payload, kra17_payload, kra18_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        cases = {18: (kra18_payload(2, 2), "activities.0.org_name", "MoU 2 of 2"),
                 17: (kra17_payload(3), "activities.0.centres.0.centre_name", "Industry Coordinator"),
                 13: (kra13iab_payload(2), "activities.0.committee_name", "Membership 2 of 2")}
        for n, (payload, field, marker) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            value = f"Synthetic browser value KRA {n} {int(time.time())}"
            box = p.locator(f"[name='{field}']")
            box.fill(value)
            expect(box).to_have_value(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator(f"[name='{field}']")).to_have_value(value)
            frame = p.frame_locator("iframe[title='Report preview']")
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            expect(frame.get_by_text(marker).first).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_kra15_22_31_38_table_reports_save_reload_preview_export(self):
        """Table batch: for KRAs 15, 22, 31 and 38 a complete synthetic draft is stored, one card cell edited in the form, saved,
        reloaded, previewed (one table, value visible) and exported."""
        from tests.fixtures import kra15_payload, kra22_payload, kra31_payload, kra38_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        cases = {15: (kra15_payload(3), "enterprise", "Entrepreneurs (Faculty / Alumni / Student)"),
                 22: (kra22_payload(3), "title", "Career Counselling Activities Conducted"),
                 31: (kra31_payload(3), "name", "Hackathons / Ideathons Organized"),
                 38: (kra38_payload(3), "faculty_name", "Name of the Organising Institution")}
        for n, (payload, column, marker) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            value = f"Synthetic browser value KRA {n} {int(time.time())}"
            box = p.locator(f"[name='activities.0.records.1.{column}']")
            box.fill(value)
            expect(box).to_have_value(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator(f"[name='activities.0.records.1.{column}']")).to_have_value(value)
            frame = p.frame_locator("iframe[title='Report preview']")
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            expect(frame.get_by_text(marker).first).to_be_visible()
            expect(frame.locator("table.records")).to_have_count(1)
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_kra4_5_6_and_24_forms(self):
        """KRAs 4–6: programme field edited, saved, reloaded, previewed and exported per KRA. KRA 24: switching a record to
        Higher Education in the form keeps the placement values (saved, reloaded) but leaves them out of the preview."""
        from tests.fixtures import fp_payload, kra24_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")

        def load(n, payload):
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            return sid

        frame = p.frame_locator("iframe[title='Report preview']")
        for n in (4, 5, 6):
            sid = load(n, fp_payload(n, 2, 3))
            value = f"Synthetic programme KRA {n} {int(time.time())}"
            p.locator("[name='activities.0.programme_name']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator("[name='activities.0.programme_name']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            expect(frame.get_by_text(f"KRA {n}: {['Field project', 'Research project', 'Internship'][n - 4]} component")).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

        payload = kra24_payload(2)
        employer = payload["activities"][0]["records"][0]["employer"]
        sid = load(24, payload)
        expect(frame.get_by_text(employer)).to_be_visible(timeout=10000)
        p.locator("[name='activities.0.records.0.category']").select_option("Higher Education")
        expect(p.get_by_label("Name of the employer (placement): not applicable").first).to_have_value("NA (entered value kept, not used)")
        p.locator("[name='activities.0.records.0.institution']").fill("Example University E2E (synthetic)")
        p.locator("[name='activities.0.records.0.admitted_programme']").fill("M.Tech E2E")
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        p.reload()
        p.wait_for_load_state("networkidle")
        _, d = api(p, "GET", f"/submissions/{sid}/")
        row = d["payload"]["activities"][0]["records"][0]
        self.assertEqual((row["category"], row["employer"]), ("Higher Education", employer))  # kept, not erased
        expect(frame.get_by_text("Example University E2E (synthetic)")).to_be_visible(timeout=10000)
        expect(frame.get_by_text(employer)).to_have_count(0)
        p.locator("[name='activities.0.records.0.category']").select_option("Placement")
        expect(p.locator("[name='activities.0.records.0.employer']")).to_have_value(employer)
        r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
        self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"))

    def test_kra12_25_26_awards(self):
        """Awards batch: KRA 12 award title edited in its card; KRAs 25/26 a team award's member list edited (one record, several
        names) — each saved, reloaded, previewed and exported."""
        from tests.fixtures import award_payload, kra12_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        cases = {12: (kra12_payload(2), "activities.0.awards.0.award_title", None),
                 25: (award_payload(25, 2), "activities.0.records.1.student_names", "\n"),
                 26: (award_payload(26, 2), "activities.0.records.1.student_names", "\n")}
        for n, (payload, field, sep) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            stamp = int(time.time())
            value = f"Synthetic award {n} {stamp}" if sep is None else f"Team member A {stamp}{sep}Team member B {stamp}"
            p.locator(f"[name='{field}']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator(f"[name='{field}']")).to_have_value(value)
            expect(frame.get_by_text(f"Team member B {stamp}" if sep else value).first).to_be_visible(timeout=10000)
            if sep:
                expect(frame.locator("table.records tbody tr")).to_have_count(2)  # team award stays one row
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_kra27_28_29_30_events(self):
        """Events batch: for KRAs 27–30 two synthetic events are stored, the second event's KRA-specific field edited in the form,
        saved, reloaded, previewed (both events, edited value) and exported."""
        from tests.fixtures import event_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        specific = {27: "sport", 28: "cultural_activity", 29: "theme", 30: "club_name"}
        for n, field in specific.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": event_payload(n, 2),
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            p.get_by_role("tab", name=re.compile("Event 2")).click()
            value = f"Synthetic {field} {n} {int(time.time())}"
            box = p.locator(f"[name='activities.1.{field}']")
            box.fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            p.wait_for_load_state("networkidle")  # select the tab after the workspace's post-load re-render
            p.get_by_role("tab", name=re.compile("Event 2")).click()
            expect(p.locator(f"[name='activities.1.{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            expect(frame.get_by_text("Event 2 of 2")).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_kra43_44_45_reports(self):
        """KRAs 43–45: two synthetic events stored; on event 2 a field is edited in the form (43 conference name, 44 theme,
        45 event name); saved, reloaded, previewed and exported. KRA 43: switching indexing to "Verified in Scopus" shows the
        reference field and submission requires it."""
        from tests.fixtures import kra43_payload, kra44_payload, kra45_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        cases = {43: (kra43_payload(2), "conference_name", "Conference 2"), 44: (kra44_payload(2), "theme", "Activity 2"),
                 45: (kra45_payload(2), "event_name", "Event 2")}
        for n, (payload, field, tab) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            p.get_by_role("tab", name=re.compile(tab)).click()
            value = f"Synthetic {field} {n} {int(time.time())}"
            p.locator(f"[name='activities.1.{field}']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            p.wait_for_load_state("networkidle")  # the workspace re-renders once evidence/preview load; select the tab after
            p.get_by_role("tab", name=re.compile(tab)).click()
            expect(p.locator(f"[name='activities.1.{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")
            if n == 43:  # event 2 is "Planned / applied for"; verified needs a reference at submission
                p.locator("[name='activities.1.indexing_status']").select_option("Verified in Scopus")
                p.get_by_role("button", name="Save draft").click()
                expect(p.get_by_role("status")).to_contain_text("Saved")
                status, body = api(p, "POST", f"/submissions/{sid}/validate/")
                self.assertIn("activities.1.indexing_reference", body["field_errors"])
                expect(frame.get_by_text("Verified in Scopus").first).to_be_visible(timeout=10000)

    def test_kra21_39_adapted_reports(self):
        """KRA 21: programme title edited and an optional qualifier row's exam edited; KRA 39: a receipt amount edited (kept
        exactly) — saved, reloaded, previewed and exported."""
        from tests.fixtures import kra21_payload, kra39_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        cases = {21: (kra21_payload(1, qualifiers=2), "activities.0.programme_title", "Synthetic programme {}"),
                 39: (kra39_payload(1), "activities.0.receipts.1.amount_inr", "123456.{:02d}")}
        for n, (payload, field, pattern) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            value = pattern.format(int(time.time()) % 100)
            p.locator(f"[name='{field}']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator(f"[name='{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            if n == 39:
                self.assertEqual(d["payload"]["activities"][0]["receipts"][1]["amount_inr"], value)  # stored as typed
            else:
                expect(frame.get_by_text("supporting information only").first).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_workspace_keeps_event_selection_and_input_across_loads(self):
        """Regression: a second load of the submission (React StrictMode runs the load effect twice in development; any
        late or stale load behaves the same) remounted the editor, resetting the selected event tab and discarding typed
        input. The duplicate detail request is delayed in the page so the race is deterministic. Also checks autosave,
        removing the selected event and switching KRA without a full page load."""
        from tests.fixtures import event_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 27)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        payload = event_payload(27, 2)
        status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                         "achievement_text": "Synthetic"})
        self.assertEqual(status, 200, body)
        p.add_init_script("""(() => {
          const f = window.fetch; let n = 0;
          window.fetch = (input, init) => {
            const url = typeof input === 'string' ? input : input.url;
            if (/\\/api\\/v1\\/submissions\\/[0-9a-f-]{36}\\/$/.test(url) && !(init && init.method && init.method !== 'GET') && ++n === 2)
              return new Promise((r) => setTimeout(r, 1500)).then(() => f(input, init));
            return f(input, init);
          };
        })()""")
        p.reload()
        tab2 = p.get_by_role("tab", name=re.compile("^Event 2"))
        tab2.click()  # before the delayed duplicate load completes
        value = f"Typed during load {int(time.time())}"
        box = p.locator("[name='activities.1.sport']")
        box.fill(value)
        p.wait_for_timeout(2500)  # the delayed load has finished by now
        expect(tab2).to_have_attribute("aria-selected", "true")
        expect(box).to_have_value(value)
        expect(p.get_by_role("status")).to_contain_text("Saved", timeout=10000)  # autosave completion keeps the view
        expect(tab2).to_have_attribute("aria-selected", "true")
        expect(box).to_have_value(value)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        self.assertEqual(d["payload"]["activities"][1]["sport"], value)

        p.once("dialog", lambda dlg: dlg.accept())
        p.get_by_role("button", name="Remove event 2").click()  # removing the selected event selects a remaining one
        expect(p.get_by_role("tab", name=re.compile("^Event 1"))).to_have_attribute("aria-selected", "true")
        expect(p.get_by_role("tab", name=re.compile("^Event 2"))).to_have_count(0)
        expect(p.locator("[name='activities.0.event_title']")).to_have_value(payload["activities"][0]["event_title"])
        expect(p.get_by_role("status")).to_contain_text("Saved", timeout=10000)

        # In-app navigation to another KRA: nothing from KRA 27 (selection or fields) is carried over.
        _, rows = api(p, "GET", "/periods/?year=2026-27")
        period = next(x for x in rows["results"] if x["is_open"])
        _, data = api(p, "GET", f"/assignments/?year=2026-27&period={period['id']}")
        asg28 = next(a for a in data["results"] if a["kra"]["number"] == 28)
        p.evaluate("url => { history.pushState({}, '', url); dispatchEvent(new PopStateEvent('popstate')) }",
                   f"/dean/kra/{asg28['id']}/{period['id']}")
        expect(p.get_by_role("heading", name=re.compile("^KRA 28"))).to_be_visible(timeout=10000)
        p.wait_for_load_state("networkidle")
        expect(p.locator("[name='activities.0.sport']")).to_have_count(0)
        expect(p.locator("[name='activities.0.cultural_activity']")).to_have_count(1)
        _, d28 = api(p, "GET", f"/submissions/{open_info(p, asg28['id'], period['id'])}/")
        self.assertNotIn(value, str(d28["payload"]))

    def test_kra14_16_34_35_project_formats(self):
        """KRAs 14, 16, 34, 35: one field edited per KRA in the form (34/35: a payment amount, stored exactly as typed); saved,
        reloaded, previewed and exported."""
        from tests.fixtures import kra14_payload, kra16_payload, support_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        cases = {14: (kra14_payload(1), "activities.0.students.1.name", "Synthetic member {}"),
                 16: (kra16_payload(1), "activities.0.training", "Synthetic training {}"),
                 34: (support_payload(34, 1), "activities.0.payments.1.amount_inr", "4321.{:02d}"),
                 35: (support_payload(35, 1), "activities.0.payments.0.amount_inr", "1234.{:02d}")}
        for n, (payload, field, pattern) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.wait_for_load_state("networkidle")
            value = pattern.format(int(time.time()) % 100)
            p.locator(f"[name='{field}']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            expect(p.locator(f"[name='{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            if n in (34, 35):
                _, d = api(p, "GET", f"/submissions/{sid}/")
                row = int(field.split(".")[3])
                self.assertEqual(d["payload"]["activities"][0]["payments"][row]["amount_inr"], value)  # exact, as typed
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_kra40_41_42_project_formats(self):
        """KRA 40: a follow-up action's progress edited; an action pointing to a missing finding is refused at validation.
        KRAs 41/42: the KRA-specific detail edited on event 2. Each saved, reloaded, previewed and exported."""
        from tests.fixtures import event_payload, kra40_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        cases = {40: (kra40_payload(1), "activities.0.actions.1.progress", None),
                 41: (event_payload(41, 2), "activities.1.theme_details", "Event 2"),
                 42: (event_payload(42, 2), "activities.1.topics", "Event 2")}
        for n, (payload, field, tab) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            if tab:
                p.get_by_role("tab", name=re.compile(tab)).click()
            value = f"Synthetic value KRA {n} {int(time.time())}"
            p.locator(f"[name='{field}']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            if tab:
                p.get_by_role("tab", name=re.compile(tab)).click()
            expect(p.locator(f"[name='{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")
            if n == 40:
                p.locator("[name='activities.0.actions.0.finding_ref']").fill("F9")
                p.get_by_role("button", name="Save draft").click()
                expect(p.get_by_role("status")).to_contain_text("Saved")  # the draft keeps an unmatched reference
                _, v = api(p, "POST", f"/submissions/{sid}/validate/")
                self.assertIn("activities.0.actions.0.finding_ref", v["field_errors"])

    def test_kra11_23_save_reload_preview_export(self):
        """KRAs 11 and 23 (previously checked by hand only): a field of course/programme 2 edited, saved, reloaded, previewed
        and exported."""
        from tests.fixtures import kra11_payload, kra23_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        frame = p.frame_locator("iframe[title='Report preview']")
        cases = {11: (kra11_payload(2), "activities.1.faculty_coordinators", "Course 2"),
                 23: (kra23_payload(2), "activities.1.programme_title", "Programme 2")}
        for n, (payload, field, tab) in cases.items():
            sid = open_ece_kra(p, n)
            _, d = api(p, "GET", f"/submissions/{sid}/")
            self.assertEqual(d["status"], "DRAFT", f"KRA {n}: demo row not editable")
            status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                             "achievement_text": "Synthetic"})
            self.assertEqual(status, 200, body)
            p.reload()
            p.get_by_role("tab", name=re.compile(tab)).click()
            value = f"Synthetic value KRA {n} {int(time.time())}"
            p.locator(f"[name='{field}']").fill(value)
            p.get_by_role("button", name="Save draft").click()
            expect(p.get_by_role("status")).to_contain_text("Saved")
            p.reload()
            p.get_by_role("tab", name=re.compile(tab)).click()
            expect(p.locator(f"[name='{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

    def test_phase5a_vc_assignment_workflow(self):
        """Phase 5A: Dean denied; VC copies 2026-27 into 2027-28 drafts (repeats show conflicts), edits an ECE target
        (saved exactly), then adds and finalizes one ECE draft for 2028-29 through the review dialog; the Dean then sees it
        and a finalized target cannot change. Rerunnable: each run finalizes the next free ECE KRA for 2028-29."""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        status, _ = api(p, "GET", "/admin/years/")
        self.assertEqual(status, 403)
        p.goto(f"{BASE}/vc/assignments")
        p.wait_for_url("**/dean/dashboard")  # VC screen not reachable for a Dean

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900})
        v = vc.new_page()
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        v.get_by_role("link", name="Assignments").click()
        expect(v.get_by_role("heading", name="KRA assignments and targets")).to_be_visible()  # the dashboard also has a year picker
        v.get_by_label("Academic year").select_option("2027-28")
        v.get_by_label("Department").select_option("ECE")
        v.get_by_role("button", name="Copy 2026-27 assignments into drafts").click()
        expect(v.get_by_role("status")).to_contain_text("into 2027-28 drafts")
        target = f"Synthetic target {int(time.time())} — 50% / NA"
        box = v.get_by_label("Target for KRA 1", exact=True)
        box.fill(target)
        v.get_by_role("row", name=re.compile(r"^KRA 1 ")).get_by_role("button", name="Save").click()
        v.reload()
        v.get_by_label("Academic year").select_option("2027-28")
        v.get_by_label("Department").select_option("ECE")
        expect(v.get_by_label("Target for KRA 1", exact=True)).to_have_value(target)  # stored exactly
        _, drafts = api(v, "GET", "/admin/drafts/?year=2027-28&department=ECE")
        self.assertEqual(next(x for x in drafts if x["kra"]["number"] == 1)["target_text"], target)
        _, again = api(v, "POST", "/admin/years/2027-28/copy/", {"source_year": "2026-27"})
        self.assertEqual(again["created"], 0)  # repeated copy never overwrites

        v.get_by_label("Academic year").select_option("2028-29")
        v.get_by_label("Department").select_option("ECE")
        pick = v.get_by_label("New draft KRA")
        expect(pick.locator("option").nth(1)).to_be_attached()
        kra = pick.locator("option").nth(1).get_attribute("value")
        pick.select_option(kra)
        v.get_by_label("New draft target").fill("Synthetic 2028-29 target: 1 Per Year")
        v.get_by_role("button", name="Add draft").click()
        expect(v.get_by_label(f"Target for KRA {kra}", exact=True)).to_have_value("Synthetic 2028-29 target: 1 Per Year")
        _, years = api(v, "GET", "/admin/years/")
        pending = next(y for y in years if y["label"] == "2028-29")["drafts_pending"]
        v.get_by_role("button", name=re.compile("Review and finalize")).click()
        expect(v.get_by_role("dialog", name="Finalize review")).to_contain_text(f"Finalize {pending} draft")
        v.get_by_role("button", name="Confirm finalize").click()
        expect(v.get_by_role("status")).to_contain_text(f"Finalized {pending} assignment(s) for 2028-29")
        expect(v.get_by_label(f"Target for KRA {kra}", exact=True)).to_have_count(0)  # finalized row is read-only
        _, drafts = api(v, "GET", "/admin/drafts/?year=2028-29&department=ECE")
        d = next(x for x in drafts if x["kra"]["number"] == int(kra))
        status, body = api(v, "PATCH", f"/admin/drafts/{d['id']}/", {"target_text": "changed"})
        self.assertEqual((status, body["code"]), (409, "finalized"))
        vc.close()

        _, rows = api(p, "GET", "/assignments/?year=2028-29")
        mine = [r for r in rows["results"] if r["kra"]["number"] == int(kra)]
        self.assertEqual([(r["department"]["code"], r["target_text"]) for r in mine], [("ECE", "Synthetic 2028-29 target: 1 Per Year")])

    def test_phase5b_progress_filters_review_and_export(self):
        """Phase 5B: an ECE draft achievement appears under Department=ECE / Status=Draft marked as unsubmitted; the review
        page's back link keeps the filters; Export PDF downloads all filtered rows; Deans are refused."""
        import pymupdf

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 20)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        note = f"Synthetic progress check {int(time.time())}"
        status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "achievement_text": note})
        self.assertEqual(status, 200, body)
        self.assertEqual(api(p, "GET", "/progress/?year=2026-27&period=1")[0], 403)
        r = p.request.get(f"{BASE}/api/v1/progress/export/?year=2026-27&period=1")
        self.assertEqual(r.status, 403)

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        v = vc.new_page()
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        v.get_by_label("Department").select_option("ECE")
        v.get_by_label("Status").select_option("DRAFT")
        row = v.get_by_role("row", name=re.compile(note))
        expect(row).to_contain_text("Unsubmitted draft")
        filtered_url = v.url
        self.assertIn("department=ECE", filtered_url)
        row.get_by_role("link", name="View & history").click()
        v.get_by_role("tab", name="Achievement").click()
        expect(v.get_by_text("Not submitted yet — unreviewed draft values.")).to_be_visible()
        v.get_by_role("link", name="← Progress").click()
        expect(v.get_by_role("row", name=re.compile(note))).to_be_visible()
        self.assertEqual(v.url, filtered_url)  # filters preserved

        v.get_by_label("Status").select_option("")  # all statuses for ECE: more rows than one page
        expect(v.get_by_text(re.compile(r"^45 rows$"))).to_be_visible()
        with v.expect_download() as dl:
            v.get_by_role("button", name=re.compile("Export PDF")).click()
        path = dl.value.path()
        doc = pymupdf.open(path)
        text = " ".join(pg.get_text() for pg in doc).replace("\n", " ")
        self.assertIn(note, text)
        self.assertIn("rows in this report: 45", text)
        self.assertIn("Unsubmitted draft", text)
        self.assertTrue(dl.value.suggested_filename.startswith("KRA_progress_2026-27_P"))
        vc.close()

if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1], verbosity=2)
