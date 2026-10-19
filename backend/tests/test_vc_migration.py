"""VC Phase 1 — upgrade from the Phase 5A schema keeps every existing record (plan v2.3 §11). Real migrations on the
isolated test database: migrate back, create Phase 5A-style data with historical models, migrate forward."""
import datetime
import io

from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.catalogue.models import AnnualAssignment, DraftAssignment
from apps.submissions.models import ReopenGrant
from tests.base import PortalTestCase, ist

NOW = ist(2026, 10, 1)
OLD = [("catalogue", "0002_phase5a_drafts"), ("submissions", "0001_initial")]


class UpgradeTests(TransactionTestCase):
    def test_upgrade_preserves_assignments_drafts_and_grants(self):
        call_command("seed_catalogue", stdout=io.StringIO())
        from apps.catalogue.models import Department
        vc, dean = PortalTestCase.make_user("t.vc", "VC"), PortalTestCase.make_user("t.dean", "DEAN", Department.objects.get(code="CSE"))
        ex = MigrationExecutor(connection)
        ex.migrate(OLD)
        old = ex.loader.project_state(OLD).apps
        A, D, Y = (old.get_model("catalogue", m) for m in ("AnnualAssignment", "DraftAssignment", "AcademicYear"))
        S, R, G, P = (old.get_model(app, m) for app, m in (("submissions", "Submission"), ("submissions", "ReopenRequest"),
                                                            ("submissions", "ReopenGrant"), ("catalogue", "ReportingPeriod")))
        src = A.objects.get(year__label="2026-27", department__code="CSE", kra__number=24)
        draft = D.objects.create(department_id=src.department_id, kra_id=src.kra_id, year=Y.objects.get(label="2027-28"), target_text="edited",
                                 template_version_id=src.template_version_id, copied_from=src, created_by_id=vc.id)
        sub = S.objects.create(assignment=src, period=P.objects.get(year__label="2026-27", index=1), created_by_id=dean.id)
        req = R.objects.create(submission=sub, reason="x", requested_by_id=dean.id, requested_at=NOW)
        grant = G.objects.create(submission=sub, starts_at=NOW, expires_at=NOW + datetime.timedelta(hours=72), approved_by_id=vc.id,
                                 source="REQUEST", request=req)
        before = list(A.objects.order_by("pk").values_list("pk", "target_text", "template_version_id"))
        ex = MigrationExecutor(connection)
        ex.loader.build_graph()
        ex.migrate(ex.loader.graph.leaf_nodes())

        after = AnnualAssignment.objects.order_by("pk")
        self.assertEqual(list(after.values_list("pk", "target_text", "template_version_id")), before)  # targets/templates untouched
        self.assertFalse(after.filter(effective_start_period__isnull=False).exists())  # legacy: every period stays an obligation
        self.assertFalse(after.filter(finalised_by__isnull=False).exists())  # no fabricated actor
        d = DraftAssignment.objects.get(pk=draft.pk)
        self.assertEqual((d.target_text, d.source_target, d.source_year.label, d.edit_version, d.removed_at),
                         ("edited", src.target_text, "2026-27", 0, None))  # draft kept as draft, source snapshot back-filled
        g = ReopenGrant.objects.get(pk=grant.pk)
        self.assertEqual((g.source, g.request_id), ("REQUEST", req.pk))
        with self.assertRaises(IntegrityError), transaction.atomic():  # new three-way check is in force
            ReopenGrant.objects.create(submission_id=sub.pk, starts_at=NOW, expires_at=NOW + datetime.timedelta(hours=1),
                                       approved_by=vc, source="PUBLICATION", request_id=req.pk)
