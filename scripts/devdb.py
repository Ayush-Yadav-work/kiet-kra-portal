"""Local-development PostgreSQL (D-001) using the binaries bundled in the `pgserver` wheel.

  python scripts/devdb.py start   # init on first run, start on 127.0.0.1:54329, write backend/.env
  python scripts/devdb.py stop
  python scripts/devdb.py status

Never used in production: the college server runs its own PostgreSQL.
"""
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pgserver
import tzdata

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".work" / "pgdata"
LOG = ROOT / ".work" / "pg.log"
ENV = ROOT / "backend" / ".env"
PORT = 54329
BIN = Path(pgserver.__file__).parent / "pginstall" / "bin"


def run(*args, **kw):
    return subprocess.run([str(BIN / args[0]), *args[1:]], check=True, **kw)


def env_values():
    if not ENV.exists():
        return {}
    return dict(line.split("=", 1) for line in ENV.read_text().splitlines() if "=" in line and not line.startswith("#"))


def init():
    DATA.parent.mkdir(exist_ok=True)
    password = secrets.token_urlsafe(24)
    pwfile = DATA.parent / "pw.tmp"
    pwfile.write_text(password)
    try:
        run("initdb", "-D", str(DATA), "-U", "kiet", "--auth=scram-sha-256", f"--pwfile={pwfile}", "-E", "UTF8",
            "--locale=C", stdout=subprocess.DEVNULL)
    finally:
        pwfile.unlink()
    values = env_values()
    values.update({
        "DATABASE_URL": f"postgresql://kiet:{password}@127.0.0.1:{PORT}/kiet",
        "DJANGO_SECRET_KEY": values.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(50),
        "DJANGO_DEBUG": values.get("DJANGO_DEBUG", "1"),
    })
    ENV.parent.mkdir(exist_ok=True)
    ENV.write_text("# Local development only; never commit.\n" + "".join(f"{k}={v}\n" for k, v in values.items()))
    return password


def ensure_tzdata():
    """The pgserver Windows build ships without share/postgresql/timezone; supply IANA TZif files from `tzdata`."""
    target = BIN.parent / "share" / "postgresql" / "timezone"
    if not (target / "Asia" / "Kolkata").exists():
        shutil.copytree(Path(tzdata.__file__).parent / "zoneinfo", target, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__init__.py", "__pycache__"))


def start():
    ensure_tzdata()
    first = not DATA.exists()
    if first:
        init()
    if status(quiet=True):
        print("already running")
        return
    run("pg_ctl", "-D", str(DATA), "-l", str(LOG), "-o", f"-p {PORT} -c listen_addresses=127.0.0.1", "-w", "start",
        stdout=subprocess.DEVNULL)
    if first:
        url = env_values()["DATABASE_URL"]
        admin_url = url.rsplit("/", 1)[0] + "/postgres"
        run("psql", "-q", "-c", "CREATE DATABASE kiet", admin_url)
    print(f"PostgreSQL running on 127.0.0.1:{PORT} (credentials in backend/.env)")


def status(quiet=False):
    ok = subprocess.run([str(BIN / "pg_ctl"), "-D", str(DATA), "status"], capture_output=True).returncode == 0
    if not quiet:
        print("running" if ok else "stopped")
    return ok


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    if cmd == "start":
        start()
    elif cmd == "stop":
        run("pg_ctl", "-D", str(DATA), "-m", "fast", "stop")
    else:
        status()
