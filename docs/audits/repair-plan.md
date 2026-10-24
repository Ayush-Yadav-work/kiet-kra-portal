# Repair plan (from `full-portal-audit.md`, 2026-10-24)

Ordered by urgency. Each batch is one or a few small commits with its own acceptance checks. Run the standard checks after every batch:
- `python backend/manage.py test tests --parallel 1` with the renderer running;
- `python e2e/run_isolated.py`;
- `npx tsc -b && npm run build`.

## Batch A — security hardening ✅ done 2026-10-24 (D-080)

Implemented as below, except A1: it uses a PostgreSQL table with atomic upserts instead of Django's database cache. Django's cache `incr` is not atomic across workers, and the table needs no deploy step or new service. Results: `full-portal-audit.md` › *Batch A results*.

| Step | Finding | Change | Acceptance check | Commit |
|---|---|---|---|---|
| A1 | H1 | Configure `CACHES` from the environment. Use Django's database cache: `createcachetable` in deploy steps, no new dependency. Refuse to start with `DEBUG=0` and `LocMemCache`. | New test: two clients on separate processes (or two cache-sharing test clients after `cache.clear()` between "workers") hit the same counter. `check --deploy` custom check fails with LocMem when `DEBUG=0`. | "Shared cache for login throttling" |
| A2 | L1 | Drive links: require `parsed.port in (None, 443)`. | Probe `https://drive.google.com:8443/…` → 400; existing evidence tests pass. | "Evidence: reject non-default ports in Drive links" |
| A3 | L2 | CSV guard: neutralise when `s.lstrip(" \t\r\n")` starts with a trigger character. | Unit test with `" =1+1"`, `"\t=1"`, `"  @SUM"` → prefixed with `'`. | "Analytics CSV: neutralise formulas after leading whitespace" |

## Batch B — deployability and recovery (blocks production; depends on A1)

| Step | Change | Acceptance check |
|---|---|---|
| B1 | Web service and renderer service definitions (systemd units like the worker's, or Compose). Gunicorn config (workers, timeouts ≥ renderer timeout). | Services start on a Linux VM. `/health/` and `/health/artifacts/` are green. The worker heartbeat is visible. |
| B2 | Nginx: TLS, `X-Forwarded-Proto`, `client_max_body_size` aligned with `EVIDENCE_MAX_FILE_BYTES`, SPA static files with a CSP (`default-src 'self'`; `frame-src 'self'` for the preview), long-cache hashed assets. | `check --deploy` clean except the agreed HSTS decision. Upload over the size limit → 413 from the proxy. SPA loads with no CSP violations. |
| B3 | Backups: nightly `pg_dump` plus private-media sync with retention; documented restore runbook. | **A restore drill** onto a fresh host: log in and download one evidence file and one approved PDF from the restore. |
| B4 | Upload malware scanning (ClamAV daemon or the institution's scanner) before evidence becomes downloadable. Reject or quarantine on detection. | An EICAR test file is rejected; normal PDFs/JPEGs pass. |
| B5 | Linux repeat of `e2e/run_perf.py` and a long-uptime renderer memory check. | Recorded numbers in `docs/validation.md`; renderer RSS stable over N hours. |

Commit boundaries: B1+B2 together ("Production service and proxy definitions"); B3 ("Backup and restore runbook"); B4 ("Upload malware scanning"); B5 is a docs-only commit of measurements.

## Batch C — UX and accessibility (independent of B)

| Step | Finding | Change | Acceptance check |
|---|---|---|---|
| C1 | M1 | Login background to WebP/AVIF (~1920 px) with `srcset`; compress the banner and logo. | Built assets: login image ≤ 350 kB. Login screenshot unchanged at 375/1440. |
| C2 | M2 | Shared checkbox/radio size ≥ 20 px with ≥ 44 px clickable label rows; enlarge "View all" and back links. | UI-audit harness reports no interactive target < 24 px on the 13 screens; browser suite passes. |
| C3 | L4 | Scroll hint (edge fade) on the overflowing main nav; card layout for the announcements table below 640 px. | At 375/768 every nav item is reachable with a visible cue; no announcement column is cut. |
| C4 | L3 | Paginate `reopen-requests/` like the other lists. | Test with 210 requests: page 2 shows the remainder. |

## Batch D — institutional confirmations (decisions before code)

| Item | Decision needed | Code impact if confirmed |
|---|---|---|
| M3 | Acceptance of all 45 report formats (checklist `docs/acceptance-checklist.md`) | Per-format corrections as new template versions |
| L5 | Should the KRA 12 "Dean", KRA 45 "HoD/Dean" and KRA 13 "Competent Authority" boxes show the Dean's name? | One line per field in `apps/reports/capabilities.py: FIELDS` or the templates |
| L6 | Years of study for ASH and KSOP (and any 5-year programmes) | `PROGRAMME_YEARS` entries |
| — | HSTS `includeSubDomains`/`preload`; policy questions in `docs/progress.md` (reopening for ended years, VC review window) | Settings / service rules |

## Recommended next repair batch

Batch A is done. Next: **B1–B3**, in parallel with the Batch D conversations; production cannot go live without deployment definitions and a tested restore. B2 must forward the real client IP (`REMOTE_ADDR`) for the login throttle.
