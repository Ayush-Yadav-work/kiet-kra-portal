"""Audit harness: inject a temporary screenshot/measurement test into e2e/test_browser.py, run it with
`python e2e/run_isolated.py -k zz_ui_audit` (isolated <db>_e2e database), then restore the file.
Usage: python docs/audits/scripts/ui_audit_inject.py <out_dir>"""
import sys
from pathlib import Path

out = sys.argv[1]
p = Path("e2e/test_browser.py"); s = p.read_text(encoding="utf-8")
test = f'''
    def test_zz_ui_audit(self):
        import json
        from tests.fixtures import kra13_payload, kra33_payload
        out = Path(r"{out}"); out.mkdir(parents=True, exist_ok=True)
        metrics = {{}}
        MEASURE = """() => {{
          const vw = innerWidth, overflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
          const vis = (e) => {{ const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' }};
          const clipped = [...document.querySelectorAll('main *')].filter((e) => vis(e) && ['hidden','clip'].includes(getComputedStyle(e).overflowX)
              && e.scrollWidth > e.clientWidth + 2 && e.children.length === 0 && e.textContent.trim()).map((e) => e.textContent.trim().slice(0, 40)).slice(0, 6);
          const small = [...document.querySelectorAll('button, a[href], input:not([type=hidden]), select, [role=tab]')].filter(vis)
              .filter((e) => {{ const r = e.getBoundingClientRect(); return (r.height < 24 || r.width < 24) && !(e.tagName === 'A' && getComputedStyle(e).display === 'inline') }})
              .map((e) => (e.getAttribute('aria-label') || e.textContent || e.name || e.type || e.tagName).trim().slice(0, 30)).slice(0, 8);
          const unlabeled = [...document.querySelectorAll('input:not([type=hidden]), select, textarea, button')].filter(vis).filter((e) => {{
              const lab = e.labels && e.labels.length, aria = e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.title;
              return !lab && !aria && !(e.tagName === 'BUTTON' && e.textContent.trim()) }}).map((e) => e.name || e.id || e.tagName).slice(0, 8);
          const offscreen = [...document.querySelectorAll('main button, main a[href], main input, main select')].filter(vis)
              .filter((e) => {{ const r = e.getBoundingClientRect(); return r.right > vw + 1 || r.left < -1 }}).map((e) => (e.textContent || e.name || '').trim().slice(0, 30)).slice(0, 6);
          return {{overflow, clipped, small, unlabeled, offscreen}} }}"""
        anon = self.browser.new_context().new_page()
        vctx = self.browser.new_context(); v = vctx.new_page(); login(v, "vc", "demo.vc"); v.wait_for_url("**/vc/dashboard")
        d = self.page; login(d, "dean", "demo.dean.ece"); d.wait_for_url("**/dean/dashboard")
        # realistic content: KRA 1 draft with 2 courses; KRA 33 submitted (for the VC review page) with a long rejection reason history
        sid1 = open_ece_kra(d, 1)
        _, x = api(d, "GET", f"/submissions/{{sid1}}/")
        prev1 = x["payload"]
        api(d, "PATCH", f"/submissions/{{sid1}}/draft/", {{"edit_version": x["edit_version"], "payload": kra13_payload(1, courses=2)}})
        sid33 = open_ece_kra(d, 33)
        _, x = api(d, "GET", f"/submissions/{{sid33}}/")
        sid34 = open_ece_kra(d, 34)  # a submitted Nil report with a long reason, for the VC review screen
        _, x = api(d, "GET", f"/submissions/{{sid34}}/")
        if x["status"] == "DRAFT":
            _, s34 = api(d, "PATCH", f"/submissions/{{sid34}}/draft/", {{"edit_version": x["edit_version"], "is_nil": True, "achievement_text": "Nil",
                "nil_reason": "Synthetic long reason: " + "no activity was possible in this period because of scheduling constraints; " * 6}})
            api(d, "POST", f"/submissions/{{sid34}}/submit/", {{"edit_version": s34["edit_version"]}})
        api(v, "POST", "/announcements/", {{"title": "Audit notice with a deliberately long title to check wrapping across narrow screens and tables",
            "body": "Synthetic body. " * 30, "audience": {{"all": True}}}})
        screens = [(anon, "login-dean", "/dean/login"), (anon, "login-vc", "/vc/login"),
                   (d, "dean-dashboard", "/dean/dashboard"), (d, "dean-workspace-kra1", f"/dean/kra/{{{{a1}}}}"), (d, "dean-announcements", "/dean/announcements"),
                   (v, "vc-dashboard", "/vc/dashboard"), (v, "vc-assignments", "/vc/assignments?year=2027-28"), (v, "vc-analytics", "/vc/analytics?year=2026-27&scope=ytd"),
                   (v, "vc-announcements", "/vc/announcements"), (v, "vc-announcement-new", "/vc/announcements/new"), (v, "vc-reopen", "/vc/reopen-requests"),
                   (v, "vc-kras", "/vc/kras")]
        _, rows = api(d, "GET", "/periods/?year=2026-27"); per = next(q for q in rows["results"] if q["is_open"])
        _, data = api(d, "GET", f"/assignments/?year=2026-27&period={{per['id']}}"); a1 = next(a for a in data["results"] if a["kra"]["number"] == 1)["id"]
        _, subs = api(v, "GET", f"/progress/?year=2026-27&period={{per['id']}}&status=SUBMITTED")
        rs = [r for r in subs["results"] if r.get("submission_id")]
        if rs:
            screens.append((v, "vc-review", f"/vc/review/{{rs[0]['submission_id']}}"))
        for w, h in ((375, 812), (768, 1024), (1024, 768), (1440, 900)):
            for page, name, path in screens:
                path = path.replace("{{a1}}", f"{{a1}}/{{per['id']}}")
                page.set_viewport_size({{"width": w, "height": h}})
                page.goto(f"{{BASE}}{{path}}"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(350)
                page.screenshot(path=str(out / f"{{name}}-{{w}}.png"), full_page=(w in (375, 1440)))
                metrics[f"{{name}}@{{w}}"] = page.evaluate(MEASURE)
        # keyboard: first 12 tab stops on the Dean workspace have a visible focus outline
        d.set_viewport_size({{"width": 1440, "height": 900}}); d.goto(f"{{BASE}}/dean/kra/{{a1}}/{{per['id']}}"); d.wait_for_load_state("networkidle")
        stops = []
        for i in range(25):
            d.keyboard.press("Tab")
            stops.append(d.evaluate("(() => {{ const e = document.activeElement; const cs = getComputedStyle(e); return [(e.getAttribute('aria-label') || e.textContent || e.name || e.tagName).trim().slice(0, 28), cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2 || cs.boxShadow !== 'none'] }})()"))
        metrics["dean-workspace keyboard tab stops"] = stops
        # 200% zoom ≈ 720 px CSS viewport
        for page, name, path in ((d, "dean-workspace-kra1", f"/dean/kra/{{a1}}/{{per['id']}}"), (v, "vc-analytics", "/vc/analytics?year=2026-27&scope=ytd"), (v, "vc-assignments", "/vc/assignments?year=2027-28")):
            page.set_viewport_size({{"width": 720, "height": 450}}); page.goto(f"{{BASE}}{{path}}"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(300)
            page.screenshot(path=str(out / f"{{name}}-zoom200.png")); metrics[f"{{name}}@zoom200"] = page.evaluate(MEASURE)
        api(d, "PATCH", f"/submissions/{{sid1}}/draft/", {{"edit_version": api(d, "GET", f"/submissions/{{sid1}}/")[1]["edit_version"], "payload": prev1}})
        (out / "ui-metrics.json").write_text(json.dumps(metrics, indent=1), encoding="utf-8")
'''
a = "\n    def test_phase5a_vc_assignment_workflow(self):"
assert s.count(a) == 1
p.write_text(s.replace(a, test + a, 1), encoding="utf-8")
print("injected")
