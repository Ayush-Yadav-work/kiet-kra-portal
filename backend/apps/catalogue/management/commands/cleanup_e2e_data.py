"""DEBUG-only: find and (with --execute) remove Phase 5A records left in a working database by browser-test runs (D-067).

Dry run by default. A record is removed only with demonstrable provenance — all of:
  * created by one of the synthetic seed_demo accounts (apps.accounts…seed_demo.DEMO),
  * its creation matched by that account's audit event (draft create, or the year copy that produced it),
  * every later audited change made by a demo account,
  * the browser test's marker in the record itself (target text beginning "Synthetic"),
  * not referenced by any report (finalized assignments with submissions are reported, never deleted).
Unmarked drafts produced by an audited demo-account copy are reported per copy event and removed only when that event is
named explicitly with --copy-event <id> (a human attests it was a test run). Everything else is reported as ambiguous.
Workbook seeds, accounts, audit history, reports, evidence and revisions are never touched.

  python manage.py cleanup_e2e_data                      # report only
  python manage.py cleanup_e2e_data --execute            # remove demonstrable records
  python manage.py cleanup_e2e_data --execute --copy-event 123
"""
import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError

from apps.accounts.management.commands.seed_demo import DEMO
from apps.audit.models import AuditEvent, record
from apps.catalogue.models import DraftAssignment

MARKER = "Synthetic"
WINDOW = datetime.timedelta(minutes=2)  # draft rows and their audit event are written in the same request


def label(d):
    return f"{d.year.label} {d.department.code} KRA {d.kra.number} (draft {d.id})"


class Command(BaseCommand):
    help = "Report (default) or remove Phase 5A records demonstrably created by browser-test runs. DEBUG only."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Delete the records listed as removable.")
        parser.add_argument("--copy-event", type=int, action="append", default=[],
                            help="Audit event id of an assignments.copy run you confirm was a test run; its unmarked, "
                                 "unedited, unfinalized drafts become removable.")

    def handle(self, *args, **o):
        if not settings.DEBUG:
            raise CommandError("cleanup_e2e_data is for local development only (DEBUG=1).")
        demo = {u for u, *_ in DEMO}
        audit = AuditEvent.objects.select_related("actor")
        drafts = DraftAssignment.objects.select_related("year", "department", "kra", "created_by", "copied_from", "finalized_assignment")
        removable, batch, ambiguous = [], [], []
        copy_events = {}
        for d in drafts.filter(created_by__username__in=demo):
            events = list(audit.filter(entity_type="DraftAssignment", entity_id=str(d.id)))
            if any(e.action != "assignment_draft.create" and (e.actor is None or e.actor.username not in demo) for e in events):
                ambiguous.append((d, "changed by a non-demo account")); continue
            if d.copied_from_id:
                ev = audit.filter(action="assignments.copy", entity_type="AcademicYear", entity_id=str(d.year_id), actor=d.created_by,
                                  created_at__gte=d.created_at, created_at__lte=d.created_at + WINDOW).order_by("created_at").first()
            else:
                ev = next((e for e in events if e.action == "assignment_draft.create" and e.actor_id == d.created_by_id), None)
            if ev is None:
                ambiguous.append((d, "no matching audit event")); continue
            a = d.finalized_assignment
            if a is not None and a.submissions.exists():
                ambiguous.append((d, "finalized assignment has reports")); continue
            if d.target_text.startswith(MARKER) and (not a or a.target_text.startswith(MARKER)):
                removable.append((d, f"audit event {ev.id}")); continue
            edited = d.copied_from_id and d.target_text != d.copied_from.target_text
            if d.copied_from_id and not edited and a is None:
                copy_events.setdefault(ev.id, (ev, []))[1].append(d)
                if ev.id in o["copy_event"]:
                    removable.append((d, f"copy event {ev.id} (confirmed)"))
                else:
                    batch.append(d)
                continue
            ambiguous.append((d, "no test marker" + (" (edited after copy)" if edited else "")))
        for d in drafts.exclude(created_by__username__in=demo).filter(target_text__startswith=MARKER):
            ambiguous.append((d, "marker text but not created by a demo account"))  # never matched on text alone

        out = self.stdout.write
        out(f"{'EXECUTE' if o['execute'] else 'DRY RUN'} — removable: {len(removable)}, unconfirmed copy batches: "
            f"{len(batch)} draft(s), ambiguous: {len(ambiguous)}")
        for d, why in removable:
            out(f"  remove  {label(d)}{' + finalized assignment ' + str(d.finalized_assignment_id) if d.finalized_assignment_id else ''} — {why}")
        for ev_id, (ev, ds) in sorted(copy_events.items()):
            if ev_id not in o["copy_event"]:
                out(f"  batch   audit event {ev_id}: {ev.actor.username} copied into {ds[0].year.label} at {ev.created_at:%Y-%m-%d %H:%M} — "
                    f"{len(ds)} unedited draft(s); pass --copy-event {ev_id} to remove them")
        for d, why in ambiguous:
            out(f"  keep    {label(d)} — ambiguous: {why}")
        if not o["execute"] or not removable:
            return
        with transaction.atomic():
            finals = [d.finalized_assignment for d, _ in removable if d.finalized_assignment_id]
            try:
                DraftAssignment.objects.filter(pk__in=[d.pk for d, _ in removable]).delete()
                for a in finals:
                    a.delete()
            except ProtectedError as e:
                raise CommandError(f"Aborted, nothing deleted: a record is referenced ({e}).")
            record(None, "cleanup.e2e", DraftAssignment(pk=0), {"drafts": len(removable), "assignments": len(finals),
                                                               "copy_events": o["copy_event"]})
        out(f"Removed {len(removable)} draft(s) and {len(finals)} finalized assignment(s).")
