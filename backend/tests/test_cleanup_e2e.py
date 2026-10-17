"""cleanup_e2e_data on an isolated fixture (D-067): dry run, execution, idempotency and preservation. SYNTHETIC data only."""
import io
import re
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.catalogue.models import KRA, AnnualAssignment, DraftAssignment, ReportingPeriod
from apps.submissions.models import Submission
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1)


@override_settings(DEBUG=True)
class CleanupE2ETests(PortalTestCase):
    def setUp(self):
        # one active VC/Dean per role: the demo accounts, as in a dev database
        User.objects.filter(pk__in=[self.vc.pk, self.dean_a.pk, self.dean_b.pk]).update(is_active=False)
        with tempfile.TemporaryDirectory() as tmp:
            call_command("seed_demo", "--credentials", f"{tmp}/c.txt", stdout=io.StringIO())
        self.demo_vc = User.objects.get(username="demo.vc")
        self.v = self.client_for(self.demo_vc)
        with frozen(NOW):
            # what a browser-test run leaves: a copy batch, one marked edit, a marked finalized assignment
            self.v.post("/api/v1/admin/years/2027-28/copy/", {"source_year": "2026-27"}, format="json")
            self.edited = DraftAssignment.objects.get(year__label="2027-28", department=self.ece, kra__number=1)
            self.v.patch(f"/api/v1/admin/drafts/{self.edited.id}/", {"target_text": "Synthetic target 1 — 50% / NA"}, format="json")
            self.v.post("/api/v1/admin/drafts/", {"year": "2028-29", "department": "ECE", "kra": 1, "target_text": "Synthetic 2028-29 target"}, format="json")
            self.v.post("/api/v1/admin/years/2028-29/finalize/", {"expected_pending": 1}, format="json")
            self.v.post("/api/v1/admin/drafts/", {"year": "2028-29", "department": "CSE", "kra": 3, "target_text": "2 Per Year"}, format="json")
        User.objects.filter(pk=self.demo_vc.pk).update(is_active=False)  # later, a real VC works in the same database
        User.objects.filter(pk=self.vc.pk).update(is_active=True)
        self.real = self.client_for(self.vc)
        with frozen(NOW):
            # look-alikes that must survive
            self.real.post("/api/v1/admin/drafts/", {"year": "2028-29", "department": "CSE", "kra": 2, "target_text": "Synthetic but real VC"}, format="json")
            hand = DraftAssignment.objects.get(year__label="2027-28", department=self.ece, kra__number=2)
            self.real.patch(f"/api/v1/admin/drafts/{hand.id}/", {"target_text": "Synthetic edited by the real VC"}, format="json")
            self.real.post("/api/v1/admin/drafts/", {"year": "2028-29", "department": "ECE", "kra": 5, "target_text": "4"}, format="json")
        self.final = AnnualAssignment.objects.get(year__label="2028-29", department=self.ece, kra__number=1)
        self.copy_event = AuditEvent.objects.get(action="assignments.copy").id

    def run_cmd(self, *args):
        out = io.StringIO()
        call_command("cleanup_e2e_data", *args, stdout=out)
        return out.getvalue()

    def snapshot(self):
        return (KRA.objects.count(), User.objects.count(), AnnualAssignment.objects.filter(year__label="2026-27").count(),
                Submission.objects.count(), AuditEvent.objects.exclude(action="cleanup.e2e").count())

    def test_dry_run_changes_nothing_and_reports(self):
        drafts, finals = DraftAssignment.objects.count(), AnnualAssignment.objects.count()
        out = self.run_cmd()
        self.assertIn("DRY RUN — removable: 2, unconfirmed copy batches: 583 draft(s), ambiguous: 3", out)
        self.assertIn(f"pass --copy-event {self.copy_event}", out)
        self.assertIn("marker text but not created by a demo account", out)  # never matched on text alone
        self.assertIn("changed by a non-demo account", out)
        self.assertIn("ambiguous: no test marker", out)
        self.assertEqual((DraftAssignment.objects.count(), AnnualAssignment.objects.count()), (drafts, finals))

    def test_execute_is_selective_and_idempotent(self):
        before = self.snapshot()
        out = self.run_cmd("--execute")
        self.assertIn("Removed 2 draft(s) and 1 finalized assignment(s).", out)
        self.assertFalse(DraftAssignment.objects.filter(pk=self.edited.pk).exists())
        self.assertFalse(AnnualAssignment.objects.filter(pk=self.final.pk).exists())
        self.assertEqual(DraftAssignment.objects.filter(year__label="2027-28").count(), 584)  # 583 unconfirmed + 1 real-VC edit kept
        for text in ("Synthetic but real VC", "2 Per Year", "Synthetic edited by the real VC", "4"):
            self.assertTrue(DraftAssignment.objects.filter(target_text=text).exists(), text)
        self.assertEqual(self.snapshot(), before)  # seeds, accounts, current assignments, reports, audit history intact
        self.assertTrue(AuditEvent.objects.filter(action="cleanup.e2e").exists())
        again = self.run_cmd("--execute")  # idempotent
        self.assertIn("removable: 0", again)
        self.assertNotIn("Removed", again)

    def test_confirmed_copy_batch_and_reports_protect(self):
        a = AnnualAssignment.objects.get(year__label="2028-29", department=self.ece, kra__number=1)
        Submission.objects.create(assignment=a, period=ReportingPeriod.objects.filter(year__label="2028-29").first(),
                                  created_by=User.objects.get(username="demo.dean.ece"))  # a report exists
        out = self.run_cmd("--execute", "--copy-event", str(self.copy_event))
        self.assertIn("finalized assignment has reports", out)
        self.assertTrue(AnnualAssignment.objects.filter(pk=a.pk).exists())  # referenced: never deleted
        self.assertEqual(DraftAssignment.objects.filter(year__label="2027-28").count(), 1)  # only the real VC's edit remains
        self.assertTrue(DraftAssignment.objects.filter(target_text="Synthetic edited by the real VC").exists())
        self.assertRegex(out, r"Removed 584 draft\(s\) and 0 finalized assignment\(s\)\.")

    def test_refused_without_debug(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                self.run_cmd()
