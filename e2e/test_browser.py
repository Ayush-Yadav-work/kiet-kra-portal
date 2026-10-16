"""Browser regression tests against the running local stack (Vite :5173, Django :8000, renderer :8790).

  python e2e/test_browser.py            # needs `manage.py seed_demo`; uses the synthetic demo.dean.ece account

They change only demo data (ECE draft rows in the open period). SYNTHETIC values only.
"""
import json
import time
import re
import sys
import unittest
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))  # synthetic fixtures

ROOT = Path(__file__).resolve().parent.parent
BASE = "http://localhost:5173"
CREDS = dict(re.findall(r"^(?:VC|DEAN)\s+(\S+)\s+(\S+)$", (ROOT / ".work" / "demo-credentials.txt").read_text(), re.M))


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
            p.get_by_role("tab", name=re.compile("Event 2")).click()
            expect(p.locator(f"[name='activities.1.{field}']")).to_have_value(value)
            expect(frame.get_by_text(value).first).to_be_visible(timeout=10000)
            expect(frame.get_by_text("Event 2 of 2")).to_be_visible()
            r = p.request.get(f"{BASE}/api/v1/submissions/{sid}/export/?inline=1")
            self.assertEqual((r.status, r.headers["content-type"]), (200, "application/pdf"), f"KRA {n}")

if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1], verbosity=2)
