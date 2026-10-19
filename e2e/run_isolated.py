"""Run the browser suite against a disposable database so it never changes the developer's working database (D-067).

  python e2e/run_isolated.py              # whole suite
  python e2e/run_isolated.py -k phase5a   # unittest -k filter
  python e2e/run_isolated.py --keep       # keep the <db>_e2e database afterwards for debugging

It recreates <working db name>_e2e on the same local PostgreSQL, migrates and seeds it (workbook catalogue + synthetic demo
accounts written to .work/e2e/), starts its own Django (:8001) and Vite (:5174, proxying to :8001) with evidence stored
under .work/e2e/private, plus the approved-PDF artifact worker on the same database and storage (D-076), runs
e2e/test_browser.py, then stops them and drops the database. The PDF renderer is stateless and shared; it is started here
only if none is running on :8790.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg

ROOT = Path(__file__).resolve().parent.parent
BACKEND, FRONTEND, WORK = ROOT / "backend", ROOT / "frontend", ROOT / ".work" / "e2e"
PY = sys.executable


def working_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url and (BACKEND / ".env").exists():
        for line in (BACKEND / ".env").read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    if not url:
        sys.exit("DATABASE_URL not found (backend/.env).")
    return url


def up(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def wait(url, what, seconds=90):
    for _ in range(seconds):
        if up(url):
            return
        time.sleep(1)
    raise SystemExit(f"{what} did not start ({url}).")


def stop(proc):
    if proc and proc.poll() is None:
        if os.name == "nt":  # Vite/npx spawn child processes
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.terminate()


def main():
    keep = "--keep" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--keep"]
    work_url = urlparse(working_database_url())
    name = work_url.path.lstrip("/")
    e2e_name = f"{name}_e2e"
    assert e2e_name.endswith("_e2e") and e2e_name != name  # never the working database
    admin = urlunparse(work_url._replace(path="/postgres"))
    with psycopg.connect(admin, autocommit=True) as c:
        c.execute(f'DROP DATABASE IF EXISTS "{e2e_name}" WITH (FORCE)')
        c.execute(f'CREATE DATABASE "{e2e_name}"')
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    env = {**os.environ, "DATABASE_URL": urlunparse(work_url._replace(path=f"/{e2e_name}")), "DJANGO_DEBUG": "1",
           "PRIVATE_STORAGE_ROOT": str(WORK / "private"), "PYTHONUTF8": "1",
           "DJANGO_CSRF_TRUSTED_ORIGINS": "http://localhost:5174"}
    manage = [PY, str(BACKEND / "manage.py")]
    for cmd in (["migrate", "--noinput"], ["seed_catalogue"], ["seed_demo", "--credentials", str(WORK / "demo-credentials.txt")]):
        subprocess.run(manage + cmd, cwd=BACKEND, env=env, check=True, capture_output=True)
    procs = []
    try:
        if not up("http://127.0.0.1:8790/health"):
            procs.append(subprocess.Popen([PY, str(ROOT / "renderer" / "server.py")], cwd=ROOT, env=env))
            wait("http://127.0.0.1:8790/health", "Renderer")
        procs.append(subprocess.Popen(manage + ["runserver", "127.0.0.1:8001", "--noreload"], cwd=BACKEND, env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        worker_log = (WORK / "artifact-worker.log").open("w")
        procs.append(subprocess.Popen(manage + ["run_artifact_worker"], cwd=BACKEND, env={**env, "ARTIFACT_POLL_SECONDS": "1"},
                                      stdout=worker_log, stderr=subprocess.STDOUT))
        procs.append(subprocess.Popen(["npx.cmd" if os.name == "nt" else "npx", "vite", "--port", "5174", "--strictPort"], cwd=FRONTEND,
                                      env={**env, "KRA_API_TARGET": "http://127.0.0.1:8001"},
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait("http://127.0.0.1:8001/api/v1/auth/csrf/", "Django (e2e)")
        wait("http://localhost:5174/", "Vite (e2e)")
        test_env = {**env, "KRA_E2E_ISOLATED": "1", "KRA_E2E_BASE": "http://localhost:5174",
                    "KRA_E2E_CREDENTIALS": str(WORK / "demo-credentials.txt")}
        rc = subprocess.run([PY, "-m", "unittest", "-v", *args, "test_browser"], cwd=ROOT / "e2e", env=test_env).returncode
    finally:
        for p in reversed(procs):
            stop(p)
        if not keep:
            time.sleep(1)
            with psycopg.connect(admin, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{e2e_name}" WITH (FORCE)')
            shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
