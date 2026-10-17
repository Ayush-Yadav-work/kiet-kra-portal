"""Internal PDF renderer (plan C4, C12, D-009).

One process, a fixed pool of Chromium browsers (RENDERER_POOL, default 2) = the global concurrency limit.
Each worker thread owns its own Playwright + browser (sync Playwright objects are thread-bound).
Listens on 127.0.0.1 only; accepts server-generated HTML from Django; aborts every non-data: request.

  POST /pdf  {"html", "header", "footer", "format", "landscape", "margin"}  -> application/pdf
  GET  /health                                                               -> {"ok", "pool", "queued"}
"""
import json
import logging
import os
import queue
import threading
from concurrent.futures import Future
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

HOST = "127.0.0.1"
PORT = int(os.environ.get("RENDERER_PORT", "8790"))
POOL = int(os.environ.get("RENDERER_POOL", "2"))
MAX_QUEUE = int(os.environ.get("RENDERER_MAX_QUEUE", str(POOL * 2)))
JOB_TIMEOUT = float(os.environ.get("RENDERER_JOB_TIMEOUT", "40"))
MAX_BODY = 20 * 1024 * 1024
FORMATS = {"Letter", "A4"}

log = logging.getLogger("renderer")
jobs: "queue.Queue[tuple[dict, Future]]" = queue.Queue(maxsize=MAX_QUEUE)
stats = {"active": 0, "peak": 0}
stats_lock = threading.Lock()


def _block_non_data(route):
    if route.request.url.startswith("data:"):
        route.continue_()
    else:
        route.abort()


def render(browser, job):
    context = browser.new_context(java_script_enabled=False, offline=True)
    try:
        context.route("**/*", _block_non_data)
        page = context.new_page()
        page.set_content(job["html"], wait_until="load", timeout=JOB_TIMEOUT * 1000)
        page.evaluate("document.fonts.ready")  # inline @font-face must finish before printing
        return page.pdf(
            format=job["format"],
            landscape=bool(job.get("landscape")),
            print_background=True,
            display_header_footer=True,
            header_template=job.get("header") or "<span></span>",
            footer_template=job.get("footer") or "<span></span>",
            margin=job.get("margin"),
            prefer_css_page_size=False,
        )
    finally:
        context.close()


def worker(n):
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-gpu", "--no-first-run"])
        log.info("worker %s ready (chromium %s)", n, browser.version)
        while True:
            job, fut = jobs.get()
            if fut.set_running_or_notify_cancel():
                with stats_lock:
                    stats["active"] += 1
                    stats["peak"] = max(stats["peak"], stats["active"])
                try:
                    if not browser.is_connected():
                        browser = p.chromium.launch(args=["--disable-gpu", "--no-first-run"])
                    try:
                        fut.set_result(render(browser, job))
                    except Exception:
                        if browser.is_connected():
                            raise
                        # Chromium died (crash/killed) and the loss is only noticed when a job fails: relaunch, retry once
                        log.warning("worker %s: browser disconnected; relaunching and retrying the job once", n)
                        browser = p.chromium.launch(args=["--disable-gpu", "--no-first-run"])
                        fut.set_result(render(browser, job))
                except Exception as e:  # report, keep worker alive
                    log.exception("render failed")
                    fut.set_exception(e)
                finally:
                    with stats_lock:
                        stats["active"] -= 1


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            with stats_lock:
                body = {"ok": True, "pool": POOL, "queued": jobs.qsize(), **stats}
            self._send(200, json.dumps(body).encode())
        else:
            self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        if self.path != "/pdf":
            return self._send(404, b'{"error":"not found"}')
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY:
            return self._send(413, b'{"error":"bad size"}')
        try:
            job = json.loads(self.rfile.read(length))
            assert isinstance(job.get("html"), str) and job.get("format") in FORMATS
        except Exception:
            return self._send(400, b'{"error":"bad request"}')
        fut: Future = Future()
        try:
            jobs.put_nowait((job, fut))
        except queue.Full:
            return self._send(503, b'{"error":"busy"}')
        try:
            pdf = fut.result(timeout=JOB_TIMEOUT)
        except TimeoutError:
            fut.cancel()
            return self._send(504, b'{"error":"timeout"}')
        except Exception:
            return self._send(500, b'{"error":"render failed"}')
        self._send(200, pdf, "application/pdf")

    def log_message(self, fmt, *args):
        log.info("%s - %s", self.address_string(), fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for n in range(POOL):
        threading.Thread(target=worker, args=(n,), daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("renderer listening on http://%s:%s pool=%s queue=%s", HOST, PORT, POOL, MAX_QUEUE)
    server.serve_forever()


if __name__ == "__main__":
    main()
