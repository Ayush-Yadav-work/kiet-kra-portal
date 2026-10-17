"""Phase 6B: local PDF-reliability, failure-recovery and mixed-workload measurements on disposable data (never the working DB).

  python e2e/run_perf.py               # all stages; results -> .work/perf-results.json
  python e2e/run_perf.py --seconds 20  # shorter workload stages
  python e2e/run_perf.py --keep        # keep <db>_perf and .work/perf for inspection

Recreates <working db>_perf, migrates, seeds the catalogue, demo accounts and e2e/perf_seed.py data, then starts its OWN Django
(:8002, Django's threaded server — Gunicorn does not run on Windows) and its OWN renderer (:8791) so outage/crash faults never touch
a shared renderer. Evidence goes to .work/perf/private. Afterwards both are stopped, the database dropped and .work/perf removed.
Local figures describe this machine only; they are not production capacity.
"""
import http.cookiejar
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import psutil
import psycopg
import pymupdf

from run_isolated import BACKEND, PY, ROOT, stop, up, wait, working_database_url

WORK = ROOT / ".work" / "perf"
API = "http://127.0.0.1:8002/api/v1"
RENDERER = "http://127.0.0.1:8791"
MARKER = "PERF-PRIVATE-MARKER-6B"
results = {"stages": {}}


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def req(self, method, path, body=None):
        token = next((c.value for c in self.jar if c.name == "csrftoken"), "")
        r = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                   headers={"Content-Type": "application/json", "X-CSRFToken": token})
        t = time.perf_counter()
        try:
            with self.op.open(r, timeout=120) as resp:
                status, data, headers = resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            status, data, headers = e.code, e.read(), e.headers
        return status, data, headers, time.perf_counter() - t

    def login(self, role, username, password):
        self.req("GET", "/auth/csrf/")
        s = self.req("POST", f"/auth/{role.lower()}/login/", {"username": username, "password": password})[0]
        assert s == 200, (username, s)
        return self


class Recorder:
    def __init__(self):
        self.lock, self.data = threading.Lock(), {}

    def add(self, op, status, seconds):
        with self.lock:
            self.data.setdefault(op, []).append((status, seconds))

    def summary(self):
        out = {}
        for op, rows in sorted(self.data.items()):
            ms = sorted(s * 1000 for _, s in rows)
            pct = lambda p: round(ms[min(len(ms) - 1, int(p / 100 * len(ms)))], 1)
            codes = {}
            for st, _ in rows:
                codes[st] = codes.get(st, 0) + 1
            out[op] = {"n": len(rows), "p50_ms": pct(50), "p95_ms": pct(95), "max_ms": round(ms[-1], 1),
                       "mean_ms": round(statistics.mean(ms), 1), "status": codes}
        return out


def health():
    try:
        with urllib.request.urlopen(RENDERER + "/health", timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None


def chromium(proc):
    """(process count, RSS MB) of the renderer and its Chromium children."""
    try:
        procs = [proc] + proc.children(recursive=True)
        return len(procs) - 1, round(sum(p.memory_info().rss for p in procs if p.is_running()) / 2**20)
    except psutil.Error:
        return 0, 0


def db_state(url):
    with psycopg.connect(url) as c:
        q = lambda sql: c.execute(sql).fetchone()[0]
        return {"submissions": q("SELECT md5(string_agg(id::text || status || edit_version || coalesce(current_revision_id::text,''), ',' ORDER BY id)) FROM submissions_submission"),
                "revisions": q("SELECT count(*) FROM submissions_submissionrevision"), "decisions": q("SELECT count(*) FROM submissions_reviewdecision"),
                "evidence": q("SELECT md5(string_agg(id::text || removed, ',' ORDER BY id)) FROM evidence_evidence")}


def is_pdf(data):
    return data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")


def main():
    keep = "--keep" in sys.argv
    seconds = int(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 30
    work_url = urlparse(working_database_url())
    name = f"{work_url.path.lstrip('/')}_perf"
    assert name.endswith("_perf") and name != work_url.path.lstrip("/")  # never the working database
    db_url = urlunparse(work_url._replace(path=f"/{name}"))
    admin = urlunparse(work_url._replace(path="/postgres"))
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{name}"')
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    creds = WORK / "credentials.txt"
    env = {**os.environ, "DATABASE_URL": db_url, "DJANGO_DEBUG": "1", "PRIVATE_STORAGE_ROOT": str(WORK / "private"), "PYTHONUTF8": "1",
           "RENDERER_URL": RENDERER, "RENDERER_PORT": "8791", "PERF_MARKER": MARKER, "PERF_CREDENTIALS": str(creds)}
    manage = [PY, str(BACKEND / "manage.py")]
    for cmd in (["migrate", "--noinput"], ["seed_catalogue"], ["seed_demo", "--credentials", str(creds)]):
        subprocess.run(manage + cmd, cwd=BACKEND, env=env, check=True, capture_output=True)
    seeded = subprocess.run(manage + ["shell", "-c", (ROOT / "e2e" / "perf_seed.py").read_text(encoding="utf-8")], cwd=BACKEND,
                            env=env, check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1]
    results["dataset"] = json.loads(seeded)
    accounts = [l.split() for l in creds.read_text().splitlines()[1:] if l.strip()]
    secrets_ = [a[2] for a in accounts]
    results["environment"] = {"os": platform.platform(), "cpus": os.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
                              "python": platform.python_version(), "app_server": "Django runserver (threaded, DEBUG=1, --noreload); Gunicorn unsupported on Windows",
                              "renderer": "renderer/server.py pool=2 queue=4 job_timeout=40s", "django_renderer_timeout_s": 45,
                              "postgres": psycopg.connect(db_url).execute("SHOW server_version").fetchone()[0]}

    logs = {k: open(WORK / f"{k}.log", "wb") for k in ("django", "renderer")}
    renderer = {}

    def start_renderer(extra=None):
        renderer["p"] = subprocess.Popen([PY, str(ROOT / "renderer" / "server.py")], cwd=ROOT, env={**env, **(extra or {})},
                                         stdout=logs["renderer"], stderr=subprocess.STDOUT)
        for _ in range(90):
            h = health()
            if h:
                time.sleep(3)  # let both workers launch Chromium
                return
            time.sleep(1)
        raise SystemExit("renderer did not start")

    django = None
    try:
        start_renderer()
        django = subprocess.Popen(manage + ["runserver", "127.0.0.1:8002", "--noreload"], cwd=BACKEND, env=env,
                                  stdout=logs["django"], stderr=subprocess.STDOUT)
        wait(API + "/auth/csrf/", "Django (perf)")
        vc = Client().login("VC", *[a[1:3] for a in accounts if a[0] == "VC"][0])
        deans = [Client().login("DEAN", a[1], a[2]) for a in accounts if a[0] == "DEAN"]
        period = json.loads(vc.req("GET", "/periods/?year=2026-27")[1])
        periods = period["results"] if isinstance(period, dict) else period
        p2 = next(p["id"] for p in periods if p["index"] == 2)
        rows = json.loads(vc.req("GET", f"/progress/?year=2026-27&period={p2}&page_size=100&department=CSE")[1])["results"]
        sid = {r["kra_number"]: r["submission_id"] for r in rows}
        ece = json.loads(vc.req("GET", f"/progress/?year=2026-27&period={p2}&page_size=100&department=ECE&status=SUBMITTED")[1])["results"]
        rproc = psutil.Process(renderer["p"].pid)
        before = db_state(db_url)

        # ---- PDF: single exports (normal, long, wide, full progress) ----
        single = {}
        for label, path in (("normal_report", f"/submissions/{ece[0]['submission_id']}/export/"),
                            ("long_report_kra33", f"/submissions/{sid[33]}/export/"), ("wide_table_kra31", f"/submissions/{sid[31]}/export/"),
                            ("progress_all_585", f"/progress/export/?year=2026-27&period={p2}")):
            s, data, h, t = vc.req("GET", path)
            single[label] = {"status": s, "seconds": round(t, 2), "valid_pdf": is_pdf(data), "pages": pymupdf.open(stream=data, filetype="pdf").page_count if is_pdf(data) else None,
                             "kb": len(data) // 1024, "cache_control": h.get("Cache-Control"), "content_type": h.get("Content-Type")}
        s, data, h, t = vc.req("GET", f"/submissions/{sid[33]}/export/")
        single["long_report_repeat_cached"] = {"status": s, "seconds": round(t, 2)}
        single["anonymous_export_status"] = Client().req("GET", f"/progress/export/?year=2026-27&period={p2}")[0]
        results["stages"]["pdf_single"] = single

        # ---- PDF: burst above capacity (12 distinct progress exports at once; pool 2 + queue 4) ----
        depts = [d["code"] for d in json.loads(vc.req("GET", "/departments/")[1])]
        procs_before = chromium(rproc)
        out, peak = [], {"active": 0, "queued": 0}
        stop_poll = threading.Event()

        def poll():
            while not stop_poll.is_set():
                h = health() or {}
                peak["active"] = max(peak["active"], h.get("active", 0))
                peak["queued"] = max(peak["queued"], h.get("queued", 0))
                time.sleep(0.05)
        threading.Thread(target=poll, daemon=True).start()
        clients = [Client().login("VC", *[a[1:3] for a in accounts if a[0] == "VC"][0]) for _ in range(12)]

        def one(i):
            s, data, h, t = clients[i].req("GET", f"/progress/export/?year=2026-27&period={p2}&department={depts[i % len(depts)]}&kra={'' if i < 6 else i}")
            out.append({"status": s, "seconds": round(t, 2), "valid_pdf": is_pdf(data) if s == 200 else None,
                        "code": None if s == 200 else json.loads(data).get("code")})
        threads = [threading.Thread(target=one, args=(i,)) for i in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        time.sleep(1)
        stop_poll.set()
        results["stages"]["pdf_burst"] = {"requests": 12, "outcomes": sorted((o["status"], o["code"] or "", o["seconds"]) for o in out),
                                          "all_200_are_valid_pdf": all(o["valid_pdf"] for o in out if o["status"] == 200),
                                          "renderer_peak_active": max(peak["active"], (health() or {}).get("peak", 0)), "renderer_peak_queued": peak["queued"],
                                          "chromium_procs_rss_mb_before": procs_before, "after": chromium(rproc)}

        # ---- PDF: renderer job timeout (renderer restarted with a 1 s job limit) ----
        stop(renderer["p"]); renderer["p"].wait(10)
        start_renderer({"RENDERER_JOB_TIMEOUT": "1"})
        s, data, h, t = vc.req("GET", f"/progress/export/?year=2026-27&period={p2}")
        timeout_case = {"status": s, "code": json.loads(data).get("code") if s != 200 else None, "seconds": round(t, 2)}
        time.sleep(8)  # the running job finishes in the worker after the timeout reply
        s2, data2, _, _ = vc.req("GET", f"/progress/export/?year=2026-27&period={p2}&department=CSE&kra=1")
        timeout_case["next_small_export"] = {"status": s2, "valid_pdf": is_pdf(data2) if s2 == 200 else None}
        timeout_case["chromium_procs_rss_mb"] = chromium(psutil.Process(renderer["p"].pid))
        results["stages"]["pdf_timeout"] = timeout_case

        # ---- PDF: renderer outage and restart (Django keeps running) ----
        stop(renderer["p"]); renderer["p"].wait(10)
        s, data, h, t = vc.req("GET", f"/progress/export/?year=2026-27&period={p2}&department=ME")
        outage = {"while_down": {"status": s, "code": json.loads(data).get("code"), "seconds": round(t, 2)}}
        s, data, h, t = vc.req("GET", f"/submissions/{sid[33]}/export/")
        outage["while_down_cached_report"] = {"status": s, "valid_pdf": is_pdf(data) if s == 200 else None}
        start_renderer()
        s, data, h, t = vc.req("GET", f"/progress/export/?year=2026-27&period={p2}&department=ME")
        outage["after_restart"] = {"status": s, "valid_pdf": is_pdf(data) if s == 200 else None, "seconds": round(t, 2)}
        results["stages"]["pdf_outage"] = outage

        # ---- PDF: Chromium crash inside a running renderer ----
        rproc = psutil.Process(renderer["p"].pid)
        killed = 0
        for p in rproc.children(recursive=True):
            if "chrom" in p.name().lower() or "headless" in p.name().lower():
                try:
                    p.kill(); killed += 1
                except psutil.Error:
                    pass
        time.sleep(1)
        crash = {"chromium_processes_killed": killed, "attempts": []}
        for i in range(4):
            s, data, h, t = vc.req("GET", f"/progress/export/?year=2026-27&period={p2}&department=IT&kra={i + 1}")
            crash["attempts"].append({"status": s, "code": None if s == 200 else json.loads(data).get("code"),
                                      "valid_pdf": is_pdf(data) if s == 200 else None, "seconds": round(t, 2)})
        crash["renderer_health_after"] = health()
        crash["chromium_procs_rss_mb_after"] = chromium(rproc)
        results["stages"]["pdf_chromium_crash"] = crash
        results["stages"]["pdf_integrity_unchanged"] = db_state(db_url) == before

        # ---- mixed workload: Dean dashboard/detail/save/preview + VC progress/detail/exports ----
        own = {}
        for d in deans:
            r = json.loads(d.req("GET", f"/assignments/?year=2026-27&period={p2}")[1])["results"]
            own[id(d)] = [x["submission"]["id"] for x in r if x["submission"]["display_status"] == "DRAFT"]

        def dean_loop(c, until, rec):
            while time.time() < until:
                s, _, _, t = c.req("GET", f"/assignments/?year=2026-27&period={p2}"); rec.add("dean_dashboard", s, t)
                sub = random.choice(own[id(c)])
                s, b, _, t = c.req("GET", f"/submissions/{sub}/"); rec.add("dean_report_read", s, t)
                s, _, _, t = c.req("PATCH", f"/submissions/{sub}/draft/", {"edit_version": json.loads(b)["edit_version"],
                                                                         "remarks": f"perf {time.time():.3f}"}); rec.add("dean_save", s, t)
                s, _, _, t = c.req("POST", f"/submissions/{sub}/preview/", {}); rec.add("dean_preview", s, t)

        def vc_loop(c, until, rec):
            n = 0
            while time.time() < until:
                n += 1
                q = {"year": "2026-27", "period": p2, "page": random.randint(1, 3)}
                q.update({k: v for k, v in (("department", random.choice(depts + [""])), ("status", random.choice(["", "DRAFT", "SUBMITTED", "APPROVED"])),
                                            ("kra", random.choice(["", str(random.randint(1, 45))]))) if v})
                s, b, _, t = c.req("GET", "/progress/?" + urlencode(q)); rec.add("vc_progress", s, t)
                ids = [r["submission_id"] for r in json.loads(b).get("results", []) if r["submission_id"]] if s == 200 else []
                if ids:
                    s, _, _, t = c.req("GET", f"/submissions/{random.choice(ids)}/"); rec.add("vc_review_read", s, t)
                if n % 6 == 0:
                    s, _, _, t = c.req("GET", f"/progress/export/?year=2026-27&period={p2}&department={random.choice(depts)}"); rec.add("vc_progress_pdf", s, t)
                if n % 6 == 3 and ids:
                    s, _, _, t = c.req("GET", f"/submissions/{random.choice(ids)}/export/"); rec.add("vc_report_pdf", s, t)

        for n_deans, n_vc in ((4, 1), (8, 2), (13, 2)):
            rec, until = Recorder(), time.time() + seconds
            vcs = [Client().login("VC", *[a[1:3] for a in accounts if a[0] == "VC"][0]) for _ in range(n_vc)]
            threads = [threading.Thread(target=dean_loop, args=(d, until, rec)) for d in deans[:n_deans]] + \
                      [threading.Thread(target=vc_loop, args=(c, until, rec)) for c in vcs]
            cpu0 = psutil.cpu_percent(None)
            t0 = time.time()
            [t.start() for t in threads]
            [t.join() for t in threads]
            summary = rec.summary()
            total = sum(v["n"] for v in summary.values())
            errors = sum(n for v in summary.values() for st, n in v["status"].items() if st >= 500 and st != 503)
            results["stages"][f"mixed_{n_deans}deans_{n_vc}vc"] = {"concurrent_users": n_deans + n_vc, "seconds": round(time.time() - t0, 1),
                                                                   "requests": total, "throughput_rps": round(total / (time.time() - t0), 1),
                                                                   "server_errors_5xx_excl_busy": errors, "cpu_percent_machine": psutil.cpu_percent(None),
                                                                   "ops": summary}
    finally:
        if django:
            stop(django)
        if renderer.get("p"):
            stop(renderer["p"])
        time.sleep(1)
        for f in logs.values():
            f.close()
        text = "\n".join((WORK / f"{k}.log").read_text(encoding="utf-8", errors="replace") for k in logs)
        results["log_scan"] = {"lines": text.count("\n"), "report_marker_hits": text.count(MARKER),
                               "password_hits": sum(text.count(s) for s in secrets_) if "secrets_" in locals() else None,
                               "tracebacks": text.count("Traceback")}
        (ROOT / ".work" / "perf-results.json").write_text(json.dumps(results, indent=1, default=str))
        if not keep:
            with psycopg.connect(admin, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            shutil.rmtree(WORK, ignore_errors=True)
    print(json.dumps(results, indent=1, default=str))


if __name__ == "__main__":
    main()
