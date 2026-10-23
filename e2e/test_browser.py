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


def approved_pdf(page, sid, seconds=240):
    """Approved PDFs come from the artifact worker started by run_isolated (D-076): 202 "processing" until ready, never
    another document. Returns the PDF bytes."""
    deadline = time.time() + seconds
    while True:
        r = page.request.get(f"{BASE}/api/v1/submissions/{sid}/export/", headers={"Accept": "application/json"})
        if r.status == 200:
            return r.body()
        assert r.status == 202 and r.json()["code"] == "pdf_processing", (r.status, r.text()[:200])
        assert time.time() < deadline, "approved PDF not produced by the worker in time"
        time.sleep(2)


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

    def test_phase6b_failed_autosave_and_upload_recover(self):
        """Phase 6B: a failed autosave keeps typed values and says so; the next change saves everything; a failed upload is
        reported and never listed as attached."""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 33)
        field = p.locator("input[name='activities.0.chapter_name']")
        fail = lambda route: route.fulfill(status=500, content_type="application/json",
                                           body='{"code":"error","message":"Synthetic server failure","field_errors":{}}') \
            if route.request.method == "PATCH" else route.continue_()
        p.route("**/api/v1/submissions/*/draft/", fail)
        field.fill("Typed while the server fails")
        expect(p.get_by_role("status")).to_contain_text("Save failed — will retry on next change", timeout=10000)
        expect(field).to_have_value("Typed while the server fails")  # typed content preserved
        p.unroute("**/api/v1/submissions/*/draft/")
        p.locator("input[name='activities.0.chapter_name']").fill("Typed while the server fails, then recovered")
        expect(p.get_by_role("status")).to_contain_text("Saved", timeout=10000)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        self.assertEqual(d["payload"]["activities"][0]["chapter_name"], "Typed while the server fails, then recovered")
        p.reload()
        expect(p.locator("input[name='activities.0.chapter_name']")).to_have_value("Typed while the server fails, then recovered")

        p.route("**/api/v1/submissions/*/evidence/", lambda route: route.abort() if route.request.method == "POST" else route.continue_())
        p.get_by_role("tab", name="Evidence").click()
        p.get_by_label("Category").select_option("Photographs")
        p.get_by_label("Label").fill("Synthetic upload that fails")
        p.set_input_files("#ev-file", files=[{"name": "f.png", "mimeType": "image/png", "buffer": b"\x89PNG\r\n\x1a\n" + b"0" * 512}])
        p.get_by_role("button", name="Add evidence").click()
        expect(p.get_by_role("alert")).to_contain_text("Cannot reach the server")  # network failure is reported
        p.unroute("**/api/v1/submissions/*/evidence/")
        self.assertEqual(p.get_by_text("Synthetic upload that fails", exact=True).count(), 0)
        _, ev = api(p, "GET", f"/submissions/{sid}/evidence/")
        self.assertNotIn("Synthetic upload that fails", [e["label"] for e in ev["results"]])

    def test_phase6c_tabs_names_markers_inactive_fields_and_phone_width(self):
        """Phase 6C: keyboard tabs with panels; named table cells; required markers follow applicability (KRA 32);
        inactive fields hidden with an explanation and their values kept (KRA 4); VC header usable at 375 px."""
        semantics = """() => {
          const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
          const named = e => (e.getAttribute('aria-label') || (e.labels && [...e.labels].map(l => l.textContent).join('')) || e.getAttribute('title')
                              || (['BUTTON', 'A'].includes(e.tagName) && e.textContent) || '').trim();
          return {unnamed: [...document.querySelectorAll('input:not([type=hidden]),select,textarea,button,a[href]')].filter(vis).filter(e => !named(e)).length,
                  tabs_without_panel: [...document.querySelectorAll('[role=tab]')].filter(t => !document.getElementById(t.getAttribute('aria-controls'))).length,
                  tablist_non_tabs: document.querySelectorAll('[role=tablist] > :not([role=tab])').length};
        }"""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        open_ece_kra(p, 33)
        report = p.get_by_role("tab", name="Report", exact=True)
        report.focus()
        p.keyboard.press("ArrowRight")
        expect(p.get_by_role("tab", name="Evidence", exact=True)).to_have_attribute("aria-selected", "true")
        expect(p.get_by_role("tabpanel", name="Evidence")).to_be_visible()
        p.keyboard.press("Home")
        expect(report).to_have_attribute("aria-selected", "true")
        expect(report).to_be_focused()
        if p.get_by_label("Alumni Name, row 1", exact=True).count() == 0:
            p.get_by_role("button", name="+ Add row").first.click()
        expect(p.get_by_label("Alumni Name, row 1", exact=True)).to_be_visible()  # table cells have accessible names
        self.assertEqual(p.evaluate(semantics), {"unnamed": 0, "tabs_without_panel": 0, "tablist_non_tabs": 0})

        open_ece_kra(p, 32)
        if p.locator("select[name='activities.0.contributions.0.contribution_type']").count() == 0:
            p.get_by_role("button", name="+ Add record").first.click()
        kind = p.locator("select[name='activities.0.contributions.0.contribution_type']")
        amount = p.locator("label[for='activities.0.contributions.0.amount']")
        details = p.locator("label[for='activities.0.contributions.0.item_details']")
        kind.select_option("Equipment/Asset")
        expect(amount).not_to_contain_text("*")  # not applicable -> not marked required
        expect(details).to_contain_text("*")
        kind.select_option("Financial Contribution")
        expect(amount).to_contain_text("*")
        expect(details).not_to_contain_text("*")

        sid = open_ece_kra(p, 4)
        answer = p.locator("select[name='activities.0.has_component']")
        answer.select_option("Yes")
        name = f"Synthetic component {int(time.time())}"
        p.locator("[name='activities.0.component_name']").fill(name)
        answer.select_option("No")
        expect(p.locator("[name='activities.0.component_name']")).to_have_count(0)  # hidden, not cleared
        expect(p.get_by_text("do not apply to your current answers").first).to_be_visible()
        expect(p.get_by_text("are not checked for submission or included in the printed report").first).to_be_visible()
        frame = p.frame_locator("iframe[title='Report preview']")
        expect(frame.locator("body")).not_to_contain_text(name, timeout=10000)  # inactive value kept but not printed
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        _, d = api(p, "GET", f"/submissions/{sid}/")
        self.assertEqual((d["payload"]["activities"][0]["has_component"], d["payload"]["activities"][0]["component_name"]), ("No", name))
        answer.select_option("Yes")
        expect(p.locator("[name='activities.0.component_name']")).to_have_value(name)

        vc = self.browser.new_context(viewport={"width": 375, "height": 812})
        v = vc.new_page()
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        v.wait_for_load_state("networkidle")
        self.assertEqual(v.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)
        box = v.get_by_role("button", name="Sign out").bounding_box()
        self.assertLessEqual(box["x"] + box["width"], 375)
        vc.close()

    def test_phase6c_measured_contrast_of_shared_controls(self):
        """Phase 6C follow-up: computed colours (alpha composited over the real background) for input borders (3:1),
        placeholders (4.5:1) and the error marker on an unselected tab (3:1, a graphical indicator with text alternative)."""
        measure = r"""(sel) => {
          const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', {willReadFrequently: true});
          const rgba = c => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; };
          const over = (t, u) => [0, 1, 2].map(i => t[3] * t[i] + (1 - t[3]) * u[i]);
          const bgOf = el => { const ch = []; for (let e = el; e; e = e.parentElement) ch.push(rgba(getComputedStyle(e).backgroundColor)); let c = [255, 255, 255]; for (const b of ch.reverse()) c = over(b, c); return c; };
          const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
          const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const el = document.querySelector(sel); const cs = getComputedStyle(el);
          const pbg = bgOf(el.parentElement), bg = bgOf(el);
          return {border: ratio(over(rgba(cs.borderTopColor), pbg), pbg), placeholder: ratio(over(rgba(getComputedStyle(el, '::placeholder').color), bg), bg),
                  color: ratio(over(rgba(cs.color), bg), bg)};
        }"""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        open_ece_kra(p, 33)
        m = p.evaluate(measure, "input.input[placeholder]")
        self.assertGreaterEqual(m["border"], 3.0, m)
        self.assertGreaterEqual(m["placeholder"], 4.5, m)
        p.get_by_role("tab", name="Report", exact=True).click()
        p.get_by_role("button", name=re.compile("^Submit")).click()  # incomplete report: evidence marked as needing attention
        expect(p.get_by_role("tab", name=re.compile("Evidence.*needs attention"))).to_be_visible()
        if p.get_by_role("tab", name=re.compile("^Evidence")).get_attribute("aria-selected") == "true":
            p.get_by_role("tab", name="Report", exact=True).click()
        p.wait_for_timeout(400)  # buttons animate colour for 150 ms (UI-1); measure the settled state
        dot = p.evaluate(measure, "[role=tab][aria-selected=false] span[aria-hidden]")
        self.assertGreaterEqual(dot["color"], 3.0, dot)

    def test_ui2_dashboards_counts_attention_filters(self):
        """UI-2: Dean cards reconcile with the list; a rejected Nil report and an approved P1 reopening appear once each in
        "Needs your attention" with real deadlines and actions; rapid period changes settle on the last choice; VC status cards
        toggle the status filter without changing the counts; pagination and Clear filters work; no page overflow at 375 px."""
        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 42)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        s, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "is_nil": True, "nil_reason": "Synthetic: no activity"})
        self.assertEqual(s, 200, body)
        self.assertEqual(api(p, "POST", f"/submissions/{sid}/submit/", {"edit_version": body["edit_version"]})[0], 200)
        _, periods = api(p, "GET", "/periods/?year=2026-27")
        p1 = next(x for x in periods["results"] if x["index"] == 1)
        _, p1rows = api(p, "GET", f"/assignments/?year=2026-27&period={p1['id']}")
        asg41 = next(a for a in p1rows["results"] if a["kra"]["number"] == 41)
        s, req = api(p, "POST", f"/assignments/{asg41['id']}/periods/{p1['id']}/reopen-requests/", {"reason": "Synthetic correction"})
        self.assertEqual(s, 201, req)

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900}); v = vc.new_page()
        login(v, "vc", "demo.vc"); v.wait_for_url("**/vc/dashboard")
        _, det = api(v, "GET", f"/submissions/{sid}/")
        reason = f"Synthetic UI-2 reason {int(time.time())}"
        self.assertEqual(api(v, "POST", f"/submissions/{sid}/review/", {"revision": det["current_revision"]["id"], "decision": "REJECT", "reason": reason})[0], 200)
        self.assertEqual(api(v, "POST", f"/reopen-requests/{req['id']}/decision/", {"approve": True})[0], 200)

        p.goto(f"{BASE}/dean/dashboard")
        attn = p.get_by_role("region", name=re.compile("Needs your attention"))
        kra42 = attn.get_by_role("listitem").filter(has_text="KRA 42 · P2")
        expect(kra42).to_contain_text("Rejected by the Vice Chancellor")
        expect(kra42).to_contain_text(reason)
        expect(kra42).to_contain_text("Period closes")
        expect(kra42.get_by_role("link", name=re.compile("^Correct & resubmit"))).to_be_visible()
        kra41 = attn.get_by_role("listitem").filter(has_text="KRA 41 ·")
        expect(kra41).to_contain_text("Reopening ends")
        expect(kra41).to_contain_text("Reopened for correction")
        cards = p.get_by_role("region", name=re.compile("reports by status"))
        nums = [int(t) for t in re.findall(r"(?<![\d.])\b(\d+)\b(?![\d.%])", cards.inner_text())]  # counts only, not the "12.5%" shares
        self.assertEqual(nums[0], sum(nums[1:6]))  # Assigned = Not submitted + Draft + Submitted + Rejected + Approved
        self.assertEqual(nums[0], p.locator("table.report-table tbody tr").count())
        row = p.locator("table.report-table tbody tr").filter(has=p.get_by_text("Rejected", exact=True)).first
        expect(row).to_contain_text("by Demo Vice-Chancellor")
        period = p.get_by_label("Reporting period")
        period.select_option(str(p1["id"]))
        period.select_option(next(str(x["id"]) for x in periods["results"] if x["index"] == 2))  # rapid switch back
        expect(p.get_by_role("heading", name=re.compile("^P2 Reports"))).to_be_visible()
        p.wait_for_timeout(800)
        expect(p.get_by_role("heading", name=re.compile("^P2 Reports"))).to_be_visible()  # no late P1 response overwrote it
        kra42.get_by_role("link", name=re.compile("^Correct & resubmit")).click()
        p.wait_for_url(f"**/dean/kra/**")

        v.reload(); v.wait_for_load_state("networkidle")  # after the API approvals above
        cards_v = v.get_by_role("region", name="Report counts")
        expect(cards_v.get_by_role("button", name=re.compile("Rejected"))).to_be_visible()
        before = cards_v.inner_text()
        v.get_by_role("button", name=re.compile("Rejected")).click()
        expect(v.get_by_role("button", name=re.compile("Rejected"))).to_have_attribute("aria-pressed", "true")
        self.assertIn("status=REJECTED", v.url)
        expect(v.get_by_role("row", name=re.compile("Nil")).first).to_be_visible()
        self.assertEqual(cards_v.inner_text(), before)  # counts ignore the status filter
        v.get_by_role("button", name="Clear filters").click()
        self.assertNotIn("status=", v.url)
        expect(v.get_by_text(re.compile(r"page 1 of \d+"))).to_be_visible()
        v.get_by_role("button", name="Next").click()
        expect(v.get_by_text(re.compile(r"page 2 of \d+"))).to_be_visible()
        for page in (p, v):
            page.set_viewport_size({"width": 375, "height": 812})
        p.goto(f"{BASE}/dean/dashboard"); p.wait_for_load_state("networkidle")
        v.wait_for_timeout(300)
        for page in (p, v):
            self.assertEqual(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)
        vc.close()

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

        text = "".join(pg.get_text() for pg in pymupdf.open(stream=approved_pdf(p, sid), filetype="pdf"))  # from the worker (D-076)
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
        # Phase 6C: an unticked variant's fields are hidden with a note, never cleared
        expect(p.locator("[id='activities.0.v9b_ratings.0']")).to_have_count(0)
        expect(p.get_by_text("does not apply to your current answers").first).to_be_visible()
        expect(frame.get_by_text("ALUMNI FEEDBACK FORM (9a)")).to_be_visible(timeout=10000)
        expect(frame.get_by_text("ALUMNI FEEDBACK FORM (9b)")).to_have_count(0)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        act = d["payload"]["activities"][0]
        self.assertEqual((act["v9a_ratings"][0], act["v9b_ratings"][0]), ("4.25", "3.75"))
        box9b.check()  # ticking 9b again shows the kept value
        expect(p.locator("[id='activities.0.v9b_ratings.0']")).to_have_value("3.75")
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

        text = "".join(pg.get_text() for pg in pymupdf.open(stream=approved_pdf(p, sid), filetype="pdf"))  # from the worker (D-076)
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

    def test_term_dropdowns_dean_name_and_nil_date_placeholder(self):
        """D-079: an unmatched old year/semester entry stays visible; dropdowns replace it; the Head of the Department is the
        signed-in Dean's profile name (read-only); a Nil draft shows 'Set on submission'."""
        from tests.fixtures import kra11_payload

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 11)
        payload = kra11_payload(1)
        payload["activities"][0].update(year_semester="Final year students", hod="Spoofed Name")
        _, d = api(p, "GET", f"/submissions/{sid}/")
        status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "payload": payload,
                                                                         "is_nil": False, "achievement_text": "Synthetic"})
        self.assertEqual(status, 200, body)
        p.reload()
        p.wait_for_load_state("networkidle")
        expect(p.get_by_text("Earlier entry: “Final year students”")).to_be_visible()
        dean = p.locator("[id='activities.0.hod']")
        expect(dean).to_have_value("Demo Dean ECE")
        expect(dean).to_have_attribute("readonly", "")
        year, sem = p.locator("select[name='activities.0.year_semester.year']"), p.locator("select[name='activities.0.year_semester.semester']")
        expect(year.locator("option")).to_have_text(["Select year of study…", "1st Year", "2nd Year", "3rd Year", "4th Year"])
        year.select_option("4th Year")
        sem.select_option("Even Semester")
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")
        p.reload()
        p.wait_for_load_state("networkidle")
        expect(year).to_have_value("4th Year")
        expect(sem).to_have_value("Even Semester")
        expect(p.get_by_text("Earlier entry:")).to_have_count(0)
        frame = p.frame_locator("iframe[title='Report preview']")
        expect(frame.get_by_text("2026-27 / 4th Year / Even Semester")).to_be_visible(timeout=10000)
        expect(frame.get_by_text("Demo Dean ECE").first).to_be_visible()
        expect(frame.get_by_text("Spoofed Name")).to_have_count(0)
        p.get_by_label("Nil submission — no activity for this KRA in this period").check()
        p.locator("#nilr").fill("Synthetic: no activity")
        expect(p.get_by_text("Set on submission")).to_be_visible()
        expect(frame.get_by_text("Set on submission")).to_be_visible(timeout=10000)
        p.get_by_label("Nil submission — no activity for this KRA in this period").uncheck()  # leave the demo row as found
        p.get_by_role("button", name="Save draft").click()
        expect(p.get_by_role("status")).to_contain_text("Saved")

    def test_phase5a_vc_assignment_workflow(self):
        """VC Phase 1 (supersedes the Phase 5A flow): Dean denied; VC copies 2026-27 into 2027-28 drafts through the copy review,
        edits ECE's KRA 33 target exactly (Changed filter), finalises ECE KRA 33 only (starts in P1), the ECE Dean then sees exactly
        that target while other drafts stay editable; remove/restore a draft; analytics with comparison and PDF/CSV exports."""
        import pymupdf

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        self.assertEqual(api(p, "GET", "/admin/years/")[0], 403)
        self.assertEqual(api(p, "GET", "/analytics/?year=2026-27")[0], 403)
        for path in ("/vc/assignments", "/vc/analytics"):
            p.goto(f"{BASE}{path}")
            p.wait_for_url("**/dean/dashboard")  # VC screens are not reachable for a Dean

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        v = vc.new_page()
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        v.get_by_role("link", name="Annual assignments").click()
        expect(v.get_by_role("heading", name="Annual assignments")).to_be_visible()
        v.get_by_label("Academic year").select_option("2027-28")
        v.get_by_role("button", name="Copy previous year setup").click()
        review = v.get_by_role("region", name="Copy review")
        expect(review).to_contain_text("new draft allocations to create")
        review.get_by_role("button", name=re.compile(r"^Create \d+ drafts")).click()
        expect(v.get_by_role("status")).to_contain_text("draft allocation(s) from 2026-27")
        v.get_by_role("combobox", name=re.compile("^KRA")).select_option("33")
        target = f"Synthetic target {int(time.time())} — 50% / NA"
        box = v.get_by_label("New target for ECE KRA 33", exact=True)
        box.fill(target)
        expect(v.get_by_text("Unsaved change")).to_be_visible()
        v.get_by_role("button", name="Save ECE KRA 33").click()
        expect(v.get_by_role("status")).to_contain_text("Saved the ECE KRA 33 draft target")
        expect(v.get_by_role("button", name="Changed targets (1)")).to_be_visible()

        v.get_by_label("Select ECE KRA 33 draft").check()
        v.get_by_role("button", name="Review and finalise 1").click()
        fin = v.get_by_role("region", name="Finalise review")
        expect(fin).to_contain_text("Reporting starts in")
        expect(fin).to_contain_text(target)
        fin.get_by_role("button", name="Finalise and send 1").click()
        expect(v.get_by_role("status")).to_contain_text("Finalised and sent 1 assignment(s) for 2027-28")
        expect(v.get_by_label("New target for ECE KRA 33", exact=True)).to_have_count(0)  # finalised row is read-only
        expect(v.get_by_label("New target for CSE KRA 33", exact=True)).to_be_visible()  # unselected drafts stay editable

        v.get_by_label("Select ME KRA 33 draft").check()
        v.get_by_role("button", name=re.compile("Remove 1 from this year")).click()
        expect(v.get_by_role("status")).to_contain_text("Removed 1 draft")
        v.get_by_role("button", name="Removed (1)").click()
        v.get_by_role("button", name="Restore ME KRA 33").click()
        expect(v.get_by_role("status")).to_contain_text("Restored")

        _, rows = api(p, "GET", "/assignments/?year=2027-28")
        self.assertEqual([(r["kra"]["number"], r["target_text"], r["effective_start_period"]["index"]) for r in rows["results"]], [(33, target, 1)])

        v.get_by_role("link", name="Analytics").click()
        expect(v.get_by_role("heading", name="Report approval analytics")).to_be_visible()
        expect(v.get_by_text(re.compile(r"^\d+ of \d+ reports approved$"))).to_be_visible()
        v.get_by_label("Scope").select_option("year")
        v.get_by_text(re.compile("^Departments:")).click()
        for code in ("CSE", "ECE"):  # URL-driven checkboxes update on the next render
            box = v.get_by_label(f"{code} — ", exact=False).first
            box.click()
            expect(box).to_be_checked()
        expect(v.get_by_text("Approved / expected by reporting period")).to_be_visible()  # comparison of two departments
        expect(v.get_by_text(re.compile(r"of 540 reports approved$"))).to_be_visible()  # 2 departments × 45 KRAs × 6 periods
        v.get_by_text(re.compile("^Departments:")).click()  # close the department list before using the buttons it covers
        with v.expect_download() as dl:
            v.get_by_role("button", name="Export PDF").click()
        text = " ".join(pg.get_text() for pg in pymupdf.open(dl.value.path())).replace("\n", " ")
        self.assertIn("of 540 reports approved", text)
        with v.expect_download() as dl:
            v.get_by_role("button", name="Export CSV").click()
        self.assertEqual(len(Path(dl.value.path()).read_text(encoding="utf-8-sig").splitlines()), 541)  # header + every slot
        v.set_viewport_size({"width": 375, "height": 812})
        for path in ("/vc/analytics?year=2026-27", "/vc/assignments?year=2027-28&kra=33"):
            v.goto(f"{BASE}{path}"); v.wait_for_load_state("networkidle")
            self.assertEqual(v.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, path)
        vc.close()

    def test_phase5b_progress_filters_review_and_export(self):
        """Phase 5B + draft privacy (D-078): an ECE Dean's saved draft is plain "Not submitted" for the VC — no Draft filter,
        no text, no link, no direct access, also from an old status=DRAFT bookmark and in the PDF export; the review page's back
        link keeps the filters (on a submitted report); Export PDF downloads all filtered rows; Deans are refused."""
        import subprocess

        import pymupdf

        p = self.page
        login(p, "dean", "demo.dean.ece")
        p.wait_for_url("**/dean/dashboard")
        sid = open_ece_kra(p, 20)
        _, d = api(p, "GET", f"/submissions/{sid}/")
        note = f"Synthetic progress check {int(time.time())}"
        status, body = api(p, "PATCH", f"/submissions/{sid}/draft/", {"edit_version": d["edit_version"], "achievement_text": note})
        self.assertEqual(status, 200, body)
        self.assertEqual(api(p, "GET", f"/submissions/{sid}/")[1]["display_status"], "DRAFT")  # the Dean still sees the draft
        self.assertEqual(api(p, "GET", "/progress/?year=2026-27&period=1")[0], 403)
        r = p.request.get(f"{BASE}/api/v1/progress/export/?year=2026-27&period=1")
        self.assertEqual(r.status, 403)
        _, periods = api(p, "GET", "/periods/?year=2026-27")
        open_p = next(x for x in periods["results"] if x["is_open"])
        seed = (  # one submitted ECE report (KRA 22) to open from the list
            "from apps.catalogue.models import AnnualAssignment, ReportingPeriod\n"
            "from apps.accounts.models import User\n"
            "from apps.submissions.models import Submission, SubmissionRevision\n"
            "from apps.submissions.services import snapshot_of\n"
            "from django.utils import timezone\n"
            f"p = ReportingPeriod.objects.get(pk={open_p['id']})\n"
            "dean = User.objects.get(username='demo.dean.ece')\n"
            "a = AnnualAssignment.objects.get(year=p.year, department__code='ECE', kra__number=22)\n"
            "s, _ = Submission.objects.get_or_create(assignment=a, period=p, defaults=dict(created_by=dean))\n"
            "if s.current_revision_id is None:\n"
            "    s.status, s.edit_version, s.is_nil, s.nil_reason = 'SUBMITTED', 2, True, 'Synthetic nil'\n"
            "    r = SubmissionRevision.objects.create(submission=s, sequence=1, payload={}, is_nil=True, nil_reason='Synthetic nil', snapshot=snapshot_of(s),\n"
            "        evidence_manifest=[], manifest_hash='h', submitted_by=dean, submitted_at=timezone.now())\n"
            "    s.current_revision = r; s.save()\n")
        subprocess.run([sys.executable, str(ROOT / "backend" / "manage.py"), "shell", "-c", seed], cwd=ROOT / "backend", check=True, capture_output=True)

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900}, accept_downloads=True)
        v = vc.new_page()
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        self.assertEqual(api(v, "GET", f"/submissions/{sid}/")[0], 404)  # same as no report
        v.get_by_label("Department").select_option("ECE")
        options = v.get_by_label("Status").locator("option").all_inner_texts()
        self.assertNotIn("Draft", options)
        expect(v.get_by_role("button", name=re.compile(r"^\d+\s*Draft"))).to_have_count(0)  # no Draft card
        v.get_by_label("KRA number").fill("20")
        row = v.locator("table.report-table tbody tr").first
        expect(row).to_contain_text("Not submitted")
        expect(row).to_contain_text("No report yet")
        expect(row).not_to_contain_text(note)
        v.goto(f"{BASE}/vc/dashboard?year=2026-27&period={open_p['id']}&department=ECE&kra=20&status=DRAFT")  # old bookmark
        expect(v.get_by_role("button", name=re.compile(r"^\d+\s*Not submitted"))).to_have_attribute("aria-pressed", "true")
        expect(v.locator("table.report-table tbody tr").first).to_contain_text("Not submitted")
        self.assertNotIn(note, v.content())

        v.goto(f"{BASE}/vc/dashboard?year=2026-27&period={open_p['id']}&department=ECE&status=SUBMITTED")
        filtered_url = v.url
        row = v.get_by_role("row", name=re.compile("Synthetic nil"))
        row.get_by_role("link", name="Review").click()
        v.get_by_role("link", name="← Progress").click()
        expect(v.get_by_role("row", name=re.compile("Synthetic nil"))).to_be_visible()
        self.assertEqual(v.url, filtered_url)  # filters preserved

        v.get_by_label("Status").select_option("")  # all statuses for ECE: more rows than one page
        expect(v.get_by_text(re.compile(r"^45 rows$"))).to_be_visible()
        with v.expect_download() as dl:
            v.get_by_role("button", name=re.compile("Export PDF")).click()
        path = dl.value.path()
        doc = pymupdf.open(path)
        text = " ".join(pg.get_text() for pg in doc).replace("\n", " ")
        self.assertNotIn(note, text)  # draft text never reaches the VC export
        self.assertNotIn("Unsubmitted draft", text)
        self.assertIn("rows in this report: 45", text)
        self.assertTrue(dl.value.suggested_filename.startswith("KRA_progress_2026-27_P"))
        vc.close()

    def test_phase2_bulk_approval_preview_artifacts_and_announcements(self):
        """VC Phase 2: quick previews of exact revisions never request a PDF; selected and all-filtered bulk approval
        (60 synthetic Nil reports in the closed P1 -> 50 + 10 server batches); the running artifact worker produces the
        approved PDF without any manual step; an ECE-only announcement is invisible to CSE, unread for ECE until opened,
        unread again after a content edit; the Analytics shortcut only prepares a draft; no overflow at 375 px."""
        import subprocess

        import pymupdf

        seed = (
            "from apps.catalogue.models import AnnualAssignment, ReportingPeriod\n"
            "from apps.accounts.models import User\n"
            "from apps.submissions.models import Submission, SubmissionRevision\n"
            "from apps.submissions.services import snapshot_of\n"
            "from django.utils import timezone\n"
            "p1 = ReportingPeriod.objects.get(year__label='2026-27', index=1)\n"
            "dean = User.objects.get(username='demo.dean.ece')\n"
            "qs = AnnualAssignment.objects.filter(year=p1.year, department__code__in=['ME', 'IT']).order_by('department__code', 'kra__number')[:60]\n"
            "for a in qs:\n"
            "    if Submission.objects.filter(assignment=a, period=p1).exists(): continue\n"
            "    s = Submission.objects.create(assignment=a, period=p1, status='SUBMITTED', edit_version=2, created_by=dean, is_nil=True,\n"
            "                                  nil_reason='Synthetic nil for bulk approval')\n"
            "    r = SubmissionRevision.objects.create(submission=s, sequence=1, payload={}, is_nil=True, nil_reason='Synthetic nil for bulk approval',\n"
            "        snapshot=snapshot_of(s), evidence_manifest=[], manifest_hash='h', submitted_by=dean, submitted_at=timezone.now())\n"
            "    s.current_revision = r; s.save()\n")
        subprocess.run([sys.executable, str(ROOT / "backend" / "manage.py"), "shell", "-c", seed], cwd=ROOT / "backend", check=True,
                       capture_output=True)

        vc = self.browser.new_context(viewport={"width": 1400, "height": 900})
        v = vc.new_page()
        pdf_requests = []
        v.on("request", lambda r: pdf_requests.append(r.url) if "/export/" in r.url else None)
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        _, periods = api(v, "GET", "/periods/?year=2026-27")
        p1 = next(p for p in periods["results"] if p["index"] == 1)["id"]
        v.goto(f"{BASE}/vc/dashboard?year=2026-27&period={p1}&department=IT&status=SUBMITTED")
        expect(v.get_by_text("Nil reason: Synthetic nil for bulk approval").first).to_be_visible()
        expect(v.get_by_text("Evidence items submitted: 0").first).to_be_visible()

        # quick preview: exact revision HTML in the sandboxed frame; switching rows and closing never requests a PDF
        v.get_by_role("button", name="Quick preview of IT KRA 1", exact=True).click()
        drawer = v.get_by_role("complementary", name="IT · KRA 1", exact=True)
        expect(drawer).to_contain_text("Submitted revision 1")
        expect(v.frame_locator("iframe[title='Report preview']").locator("body")).to_contain_text("NIL REPORT")
        v.get_by_role("checkbox", name="Select IT KRA 2 for approval").check()  # selection survives the drawer
        drawer.get_by_role("button", name="Next report").click()  # switch inside the drawer
        expect(v.get_by_role("complementary", name="IT · KRA 2", exact=True)).to_be_visible()
        v.keyboard.press("Escape")
        expect(v.get_by_role("complementary")).to_have_count(0)
        self.assertEqual(pdf_requests, [])
        expect(v.get_by_role("checkbox", name="Select IT KRA 2 for approval")).to_be_checked()

        # selected reports: one confirmation, then the server processes them
        v.get_by_role("checkbox", name="Select IT KRA 1 for approval").check()
        v.get_by_role("button", name="Approve selected (2)").click()
        panel = v.get_by_role("region", name="Bulk approval")
        panel.get_by_role("button", name="Approve 2 reports").click()
        expect(panel.get_by_role("status")).to_have_text("Finished: processed 2 of 2.")
        panel.get_by_role("button", name="Close").click()

        # all reports matching the filters, across pages: 58 left -> batches of 50 and 8, reported only when complete
        v.goto(f"{BASE}/vc/dashboard?year=2026-27&period={p1}&status=SUBMITTED")
        btn = v.get_by_role("button", name=re.compile(r"^Approve all matching filters \((\d+) awaiting review\)"))
        total = int(re.search(r"\((\d+) awaiting", btn.inner_text()).group(1))
        self.assertGreaterEqual(total, 58)
        btn.click()
        panel = v.get_by_role("region", name="Bulk approval")
        expect(panel).to_contain_text(f"All eligible reports matching filters — {total} reports awaiting review")
        panel.get_by_role("button", name=f"Approve {total} reports").click()
        expect(panel.get_by_role("status")).to_have_text(f"Finished: processed {total} of {total}.", timeout=60000)
        expect(panel).to_contain_text(f"Approved: {total}")
        _, runs = api(v, "GET", "/bulk-approvals/")
        self.assertEqual((runs["results"][0]["total"], runs["results"][0]["counts"]["APPROVED"]), (total, total))

        # the configured worker renders the retained approved PDF on its own (no manual step)
        _, rows = api(v, "GET", f"/progress/?year=2026-27&period={p1}&department=IT&kra=1")
        sid = rows["results"][0]["submission_id"]
        text = " ".join(pg.get_text() for pg in pymupdf.open(stream=approved_pdf(v, sid), filetype="pdf"))
        self.assertIn("Verified by VC - Demo Vice-Chancellor", text)

        # announcement to ECE only
        v.goto(f"{BASE}/vc/announcements/new")
        title = f"Synthetic notice {int(time.time())}"
        v.get_by_label("Title").fill(title)
        v.get_by_label(re.compile("^Message")).fill("Please check https://example.org/kra before Friday.")
        v.get_by_label("Selected departments").check()
        v.get_by_label(re.compile("^ECE — ")).check()
        v.get_by_role("button", name="Save draft").click()
        expect(v.get_by_role("status")).to_contain_text("Draft saved.")
        v.get_by_role("button", name="Review and publish").click()
        review = v.get_by_role("region", name="Publish review")
        expect(review).to_contain_text("Publish to 1 department(s): ECE")
        review.get_by_role("button", name="Publish now").click()
        expect(v.get_by_role("status")).to_contain_text("Published.")
        nid = v.url.rsplit("/", 1)[1]

        cse = self.page
        login(cse, "dean", "demo.dean.cse")
        cse.wait_for_url("**/dean/dashboard")
        self.assertEqual(api(cse, "GET", f"/announcements/{nid}/")[0], 404)  # not a recipient, even by URL
        ece = self.browser.new_context(viewport={"width": 1400, "height": 900}).new_page()
        login(ece, "dean", "demo.dean.ece")
        ece.wait_for_url("**/dean/dashboard")
        nav = ece.get_by_role("navigation", name="Main")
        expect(nav.get_by_role("link", name=re.compile(r"^Announcements \d+ unread$"))).to_be_visible()
        notices = ece.get_by_role("region", name=re.compile("^Announcements"))
        notices.get_by_role("link", name=title).click()
        expect(ece.get_by_role("heading", name=title)).to_be_visible()
        expect(ece.locator('a[href="https://example.org/kra"]')).to_have_attribute("rel", "noopener noreferrer")  # plain text, http(s) links only
        ece.goto(f"{BASE}/dean/announcements")
        expect(ece.get_by_role("link", name=re.compile(re.escape(title)))).not_to_contain_text("Unread")
        _, n = api(v, "GET", f"/announcements/{nid}/")
        self.assertEqual(api(v, "PATCH", f"/announcements/{nid}/", {"edit_version": n["edit_version"], "body": "Changed: please check today."})[0], 200)
        ece.reload()
        expect(ece.get_by_role("link", name=re.compile(re.escape(title)))).to_contain_text("Unread")  # content edit: unread again

        # Analytics shortcut: an editable draft only
        v.goto(f"{BASE}/vc/analytics?year=2026-27&scope=period&period={p1}")
        v.get_by_role("button", name="Announce to pending departments").click()
        box = v.get_by_role("region", name="Announce to pending departments")
        box.get_by_role("button", name="Find pending departments").click()
        expect(box).to_contain_text("department(s):")
        box.get_by_role("button", name="Create draft announcement").click()
        expect(v.get_by_text("Prepared from Analytics for departments with pending reports")).to_be_visible()
        expect(v.get_by_role("button", name="Review and publish")).to_be_visible()  # still a draft

        for page, path in ((v, "/vc/announcements"), (v, f"/vc/dashboard?year=2026-27&period={p1}"), (ece, "/dean/announcements")):
            page.set_viewport_size({"width": 375, "height": 812})
            page.goto(f"{BASE}{path}")
            page.wait_for_load_state("networkidle")
            self.assertEqual(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, path)
        ece.context.close()
        vc.close()


    def test_dean_status_cards_filter_and_reopen_denial_feedback(self):
        """Dean dashboard: every status card filters the report list (counts unchanged, toggle/Assigned clears, keyboard,
        zero-match state, status kept across period changes). A VC denial of a reopening request shows its exact reason on
        the dashboard and in the workspace, also after reload."""
        import subprocess

        seed = (
            "from apps.catalogue.models import AnnualAssignment, ReportingPeriod\n"
            "from apps.accounts.models import User\n"
            "from apps.submissions.models import Submission, SubmissionRevision, ReviewDecision\n"
            "from apps.submissions.services import snapshot_of\n"
            "from django.utils import timezone\n"
            "p2 = ReportingPeriod.objects.get(year__label='2026-27', index=2)\n"
            "dean, vc = User.objects.get(username='demo.dean.cse'), User.objects.get(username='demo.vc')\n"
            "a = {x.kra.number: x for x in AnnualAssignment.objects.filter(year=p2.year, department__code='CSE').select_related('kra')}\n"
            "for kra, status, ev in ((1, 'SUBMITTED', 2), (2, 'APPROVED', 2), (3, 'REJECTED', 2), (4, 'DRAFT', 2), (5, 'DRAFT', 0)):\n"
            "    s, _ = Submission.objects.get_or_create(assignment=a[kra], period=p2, defaults=dict(created_by=dean))\n"
            "    s.status, s.edit_version, s.achievement_text = status, ev, 'synthetic'\n"
            "    if status != 'DRAFT':\n"
            "        r = SubmissionRevision.objects.create(submission=s, sequence=s.revisions.count() + 1, payload={}, is_nil=False, snapshot=snapshot_of(s),\n"
            "            evidence_manifest=[], manifest_hash='h', submitted_by=dean, submitted_at=timezone.now())\n"
            "        s.current_revision = r\n"
            "        if status == 'REJECTED': ReviewDecision.objects.create(revision=r, reviewer=vc, reviewer_name='Demo', decision='REJECT', reason='synthetic', created_at=timezone.now())\n"
            "    s.save()\n")
        subprocess.run([sys.executable, str(ROOT / "backend" / "manage.py"), "shell", "-c", seed], cwd=ROOT / "backend", check=True, capture_output=True)

        p = self.page
        login(p, "dean", "demo.dean.cse")
        p.wait_for_url("**/dean/dashboard")
        _, periods = api(p, "GET", "/periods/?year=2026-27")
        pid = {x["index"]: x["id"] for x in periods["results"]}
        p.goto(f"{BASE}/dean/dashboard?year=2026-27&period={pid[2]}")
        reports = p.get_by_role("region", name=re.compile("^P2 Reports"))
        rows = reports.locator("tbody tr")
        expect(rows.first).to_be_visible()

        def card(label):
            return p.get_by_role("button", name=re.compile(rf"^\d+\s*{label}(\s*[\d.]+%)?$"))  # count, label, share (redesign v2)

        def value(label):
            return int(re.match(r"\d+", card(label).inner_text()).group(0))

        labels = ("Assigned", "Not submitted", "Draft", "Submitted", "Rejected", "Approved")
        counts = {l: value(l) for l in labels}
        self.assertEqual(sum(counts[l] for l in labels[1:]), counts["Assigned"])
        self.assertTrue(all(counts[l] >= 1 for l in labels))
        expect(card("Assigned")).to_have_attribute("aria-pressed", "true")
        for label in labels[1:]:
            card(label).click()
            expect(card(label)).to_have_attribute("aria-pressed", "true")
            expect(card("Assigned")).to_have_attribute("aria-pressed", "false")
            expect(rows).to_have_count(counts[label])
            for i in range(counts[label]):
                expect(rows.nth(i).locator("td[data-col=status]")).to_contain_text(label)
            self.assertEqual({l: value(l) for l in labels}, counts)  # headline counts never follow the filter
        card("Approved").click()  # active card again: cleared
        expect(card("Assigned")).to_have_attribute("aria-pressed", "true")
        card("Draft").focus()
        p.keyboard.press("Enter")
        expect(card("Draft")).to_have_attribute("aria-pressed", "true")
        card("Assigned").focus()
        p.keyboard.press("Space")  # Assigned clears the status filter
        expect(card("Draft")).to_have_attribute("aria-pressed", "false")
        expect(rows).to_have_count(counts["Assigned"])

        card("Approved").click()
        expect(card("Approved")).to_have_attribute("aria-pressed", "true")
        p.get_by_label("Reporting period").select_option(str(pid[3]))  # upcoming period: the filter is kept, zero matches
        expect(card("Approved")).to_have_attribute("aria-pressed", "true")
        expect(p.get_by_text("No P3 reports are approved.")).to_be_visible()
        p.get_by_label("Reporting period").select_option(str(pid[2]))
        expect(p.get_by_role("region", name=re.compile("^P2 Reports")).locator("tbody tr")).to_have_count(counts["Approved"])

        # reopening request for a closed period, denied by the VC with a reason
        _, data = api(p, "GET", f"/assignments/?year=2026-27&period={pid[1]}")
        asg = next(r for r in data["results"] if r["kra"]["number"] == 6)
        reason = f"Synthetic denial {int(time.time())}: window closed on <time>"
        status, req = api(p, "POST", f"/assignments/{asg['id']}/periods/{pid[1]}/reopen-requests/", {"reason": "Missed by a day (synthetic)"})
        self.assertEqual(status, 201, req)
        vc = self.browser.new_context(viewport={"width": 1400, "height": 900})
        v = vc.new_page()
        login(v, "vc", "demo.vc")
        v.wait_for_url("**/vc/dashboard")
        v.goto(f"{BASE}/vc/reopen-requests")
        item = v.get_by_role("listitem").filter(has_text="Missed by a day (synthetic)").filter(has_text="CSE")
        expect(item.get_by_role("button", name="Deny")).to_be_disabled()  # a reason is required
        item.get_by_label("Decision reason").fill(reason)
        item.get_by_role("button", name="Deny").click()
        expect(item).to_have_count(0)  # decided: it leaves the Pending list
        vc.close()

        p.goto(f"{BASE}/dean/dashboard?year=2026-27&period={pid[1]}")
        attention = p.get_by_role("region", name=re.compile("^Needs your attention"))
        entry = attention.get_by_role("listitem").filter(has_text="KRA 6 · P1")
        expect(entry).to_contain_text("Reopening request denied by the Vice Chancellor")
        expect(entry).to_contain_text(reason)  # exact text, rendered as text
        entry.get_by_role("link", name=re.compile("^View request history")).click()
        box = p.get_by_role("region", name="Reopening request")
        expect(box).to_contain_text("Reopening request denied by the Vice Chancellor — KRA 6")
        expect(box).to_contain_text(f"Reason: {reason}")
        p.reload()
        expect(p.get_by_role("region", name="Reopening request")).to_contain_text(f"Reason: {reason}")  # persists after reload

        p.set_viewport_size({"width": 375, "height": 812})
        p.goto(f"{BASE}/dean/dashboard?year=2026-27&period={pid[2]}&status=SUBMITTED")
        expect(card("Submitted")).to_have_attribute("aria-pressed", "true")
        expect(p.get_by_role("region", name=re.compile("^P2 Reports")).locator("tbody tr")).to_have_count(counts["Submitted"])
        self.assertEqual(p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)


    def test_ui_polish_table_cells_contain_text_and_department_list_is_on_top(self):
        """UI polish (reference/ui/bugs): announcement rows with long text and long audiences keep every cell's content inside
        its own cell (no text drawn over neighbouring columns); the Analytics department list opens above the cards below it,
        fits the viewport (scrolling internally), works with the keyboard and closes with Escape — at the bug screenshots'
        viewports, at 200% zoom (half-width CSS viewport) and near the bottom of the viewport."""
        v = self.page
        login(v, "vc", "demo.vc"); v.wait_for_url("**/vc/dashboard")
        body = ("Our records show at least one report for your assigned KRAs in P2: September – October 2026 that is not yet submitted, "
                "is still a draft, or was rejected or returned for correction. Please review your KRA dashboard. ") * 2
        many = ["ASH", "CS", "CSE", "CSE (AI)", "CSE (AIML)", "CSIT", "ECE", "EEE", "IT", "KSOM", "KSOP", "MCA", "ME"]
        for i in range(3):
            st, _ = api(v, "POST", "/announcements/", {"title": f"Reports pending for 2026-27 ({i})", "body": body,
                                                         "audience": {"departments": many[:11]} if i < 2 else {"all": True}, "pinned": i == 2})
            self.assertEqual(st, 201)
        contained = """() => [...document.querySelectorAll('main table td')].flatMap((td) => {
            const c = td.getBoundingClientRect();
            return [...td.querySelectorAll('*')].filter((e) => getComputedStyle(e).position !== 'absolute' && e.getClientRects().length)
              .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.left < c.left - 1 || r.right > c.right + 1) })
              .map((e) => `${e.tagName}:${e.textContent.slice(0, 30)}`) })"""
        in_panel = """() => [...document.querySelectorAll('main .panel')].flatMap((p) => {
            const c = p.getBoundingClientRect();
            return [...p.querySelectorAll('*')].filter((e) => !e.closest('.overflow-x-auto, details') && getComputedStyle(e).position !== 'absolute'
              && e.getClientRects().length).filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.left < c.left - 1 || r.right > c.right + 1) })
              .map((e) => `${e.tagName}:${e.textContent.slice(0, 30)}`) })"""
        for w, h in ((1507, 710), (1440, 900), (1024, 768), (768, 1024), (720, 450), (375, 812)):
            v.set_viewport_size({"width": w, "height": h})
            v.goto(f"{BASE}/vc/announcements"); v.wait_for_load_state("networkidle")
            self.assertEqual(v.evaluate(in_panel), [], f"text outside its panel at {w}px")
            expect(v.get_by_role("link", name="Reports pending for 2026-27 (0)", exact=True)).to_be_visible()
            self.assertEqual(v.evaluate(contained), [], f"text outside its cell at {w}px")
            self.assertEqual(v.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, w)

        on_top = """(el) => { const r = el.getBoundingClientRect(); const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
            return !!hit && (hit === el || el.contains(hit) || hit.contains(el)) }"""
        for w, h, scroll in ((1520, 710, 0), (1440, 900, 0), (1024, 768, 0), (768, 1024, 0), (720, 450, 0), (375, 812, 0), (1440, 900, 1)):
            v.set_viewport_size({"width": w, "height": h})
            v.goto(f"{BASE}/vc/analytics?year=2026-27&scope=ytd"); v.wait_for_load_state("networkidle")
            expect(v.get_by_text(re.compile(r"reports approved$"))).to_be_visible()
            self.assertEqual(v.evaluate(in_panel), [], f"analytics text outside its panel at {w}px")
            summary = v.get_by_text(re.compile("^Departments:"))
            if scroll:  # trigger near the bottom edge of the viewport: the list must still fit on screen
                v.evaluate("(y) => window.scrollTo(0, y)", summary.bounding_box()["y"] + v.evaluate("window.scrollY") - (h - 80))
            summary.click()
            panel = v.locator("details[open] > div").first
            expect(panel).to_be_visible()
            box = panel.bounding_box()
            self.assertGreaterEqual(box["y"], 0, f"list above the viewport at {w}px")
            self.assertLessEqual(box["y"] + box["height"], h + 1, f"list below the viewport at {w}px")
            self.assertLessEqual(box["x"] + box["width"], w + 1, f"list past the right edge at {w}px")
            first, last = v.get_by_label("ASH — ", exact=False), v.get_by_label("ME — ", exact=False)
            self.assertTrue(first.evaluate(on_top), f"first option hidden at {w}px")
            last.scroll_into_view_if_needed()
            self.assertTrue(last.evaluate(on_top), f"last option hidden at {w}px")
            last.focus(); v.keyboard.press("Space")  # keyboard selection
            v.wait_for_url(re.compile("department=ME"))
            expect(v.locator("details[open]")).to_have_count(1)  # the list stays open while choosing
            v.keyboard.press("Escape")
            expect(v.locator("details[open]")).to_have_count(0)
            expect(summary).to_be_focused()  # focus returns to the trigger
            self.assertEqual(v.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, w)


    def test_login_pages_required_fields_keyboard_and_roles(self):
        """Login (reference/ui/redesign-v2/login-reference.png): both role pages render their own role; empty fields are
        named rather than silently refused; Enter submits; the password can be shown; a wrong password is rejected without a
        session; the correct account signs in from the keyboard; no page overflow on a phone."""
        p = self.page
        for portal, other in (("dean", "VC"), ("vc", "Dean")):
            p.goto(f"{BASE}/{portal}/login")
            expect(p.get_by_role("heading", name="Welcome Back")).to_be_visible()
            nav = p.get_by_role("navigation", name="Sign in as")
            expect(nav.locator("[aria-current=page]")).to_contain_text("Dean" if portal == "dean" else "VC")
            expect(nav.get_by_role("link", name=re.compile(f"^{other}"))).to_have_attribute("href", "/vc/login" if portal == "dean" else "/dean/login")
        p.goto(f"{BASE}/dean/login")
        p.get_by_role("button", name="Sign In").click()
        expect(p.get_by_text("Enter your username.")).to_be_visible()
        expect(p.get_by_text("Enter your password.")).to_be_visible()
        expect(p.get_by_label("Username")).to_be_focused()
        expect(p.get_by_label("Username")).to_have_attribute("aria-invalid", "true")
        p.keyboard.type("demo.dean.ece")
        expect(p.get_by_text("Enter your username.")).to_have_count(0)
        p.keyboard.press("Enter")  # keyboard submission with the password still empty
        expect(p.get_by_label("Password", exact=True)).to_be_focused()
        p.keyboard.type("not-the-password")
        p.get_by_role("button", name="Show password").click()
        expect(p.get_by_label("Password", exact=True)).to_have_attribute("type", "text")
        expect(p.get_by_role("button", name="Hide password")).to_have_attribute("aria-pressed", "true")
        p.get_by_label("Password", exact=True).press("Enter")
        expect(p.get_by_role("alert")).to_contain_text(re.compile("Invalid username or password for this portal|Too many failed attempts"))
        self.assertEqual(p.request.get(f"{BASE}/api/v1/auth/me/").status, 401)
        p.get_by_label("Password", exact=True).fill(CREDS["demo.dean.ece"])
        p.get_by_label("Password", exact=True).press("Enter")
        p.wait_for_url("**/dean/dashboard")
        ctx = self.browser.new_context(viewport={"width": 375, "height": 812}); m = ctx.new_page()
        for portal in ("dean", "vc"):
            m.goto(f"{BASE}/{portal}/login"); m.wait_for_load_state("networkidle")
            self.assertEqual(m.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, portal)
            box = m.get_by_role("button", name="Sign In").bounding_box()
            self.assertLessEqual(box["x"] + box["width"], 375)
        ctx.close()

if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1], verbosity=2)
