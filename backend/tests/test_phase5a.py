"""Phase 5A — VC KRA management, draft assignments, next-year copy and finalization (D-065). SYNTHETIC data only."""
from django.core.exceptions import ValidationError

from apps.audit.models import AuditEvent
from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, DraftAssignment, TemplateVersion
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1)  # 2026-27 under way (locked); 2027-28 and 2028-29 not started


class Phase5ATests(PortalTestCase):
    def setUp(self):
        self.v = self.client_for(self.vc)
        self.d = self.client_for(self.dean_a)

    def call(self, client, method, path, body=None):
        with frozen(NOW):
            return getattr(client, method)(f"/api/v1{path}", body, format="json") if body is not None else getattr(client, method)(f"/api/v1{path}")

    def copy(self, target="2027-28", source="2026-27"):
        return self.call(self.v, "post", f"/admin/years/{target}/copy/", {"source_year": source})

    def test_dean_and_anonymous_denied_everywhere(self):
        draft = DraftAssignment.objects.create(department=self.cse, kra=KRA.objects.get(number=1), year=AcademicYear.objects.get(label="2027-28"),
                                               target_text="1", template_version=TemplateVersion.objects.get(key="kra1"), created_by=self.vc)
        anon = self.client_class()
        for client, codes in ((self.d, {403}), (anon, {401, 403})):
            for method, path, body in (("get", "/admin/templates/", None), ("get", "/admin/kras/", None), ("post", "/admin/kras/", {}),
                                       ("get", "/admin/years/", None), ("post", "/admin/years/2027-28/copy/", {"source_year": "2026-27"}),
                                       ("post", "/admin/years/2027-28/finalize/", {"expected_pending": 1}),
                                       ("get", "/admin/drafts/?year=2027-28", None), ("post", "/admin/drafts/", {}),
                                       ("patch", f"/admin/drafts/{draft.id}/", {"target_text": "9"}), ("delete", f"/admin/drafts/{draft.id}/", None)):
                r = self.call(client, method, path, body)
                self.assertIn(r.status_code, codes, (client, method, path))
        draft.refresh_from_db()
        self.assertEqual(draft.target_text, "1")
        self.assertFalse(AnnualAssignment.objects.filter(year__label="2027-28").exists())

    def test_copy_preserves_source_and_handles_repeats(self):
        before = list(AnnualAssignment.objects.filter(year__label="2026-27").order_by("pk").values_list("pk", "target_text", "template_version_id"))
        r = self.copy()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["created"], r.json()["conflicts"]), (585, []))
        drafts = DraftAssignment.objects.filter(year__label="2027-28")
        self.assertEqual(drafts.count(), 585)
        src = AnnualAssignment.objects.get(department=self.cse, kra__number=24, year__label="2026-27")
        d = drafts.get(department=self.cse, kra__number=24)
        self.assertEqual((d.target_text, d.template_version_id, d.copied_from_id), (src.target_text, src.template_version_id, src.pk))
        self.assertTrue(drafts.filter(target_text__contains="%").exists())  # percentages kept as text
        self.assertTrue(drafts.filter(target_text="NIL").exists())
        again = self.copy()  # repeated request: nothing overwritten
        self.assertEqual((again.json()["created"], len(again.json()["conflicts"])), (0, 585))
        self.assertEqual(again.json()["conflicts"][0]["reason"], "draft exists")
        self.assertEqual(list(AnnualAssignment.objects.filter(year__label="2026-27").order_by("pk").values_list("pk", "target_text", "template_version_id")), before)
        self.assertEqual(self.copy(target="2026-27", source="2026-27").status_code, 409)  # current year locked
        self.assertEqual(self.copy(target="2027-28", source="2028-29").status_code, 400)  # must copy from an earlier year

    def test_draft_edit_then_finalize_then_immutable(self):
        self.copy()
        d = DraftAssignment.objects.get(year__label="2027-28", department=self.cse, kra__number=33)
        target = "2 events (incl. 1 alumni meet) — 50% online; NA if no chapter"
        r = self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": target})
        self.assertEqual((r.status_code, r.json()["target_text"]), (200, target))  # exact string, not parsed
        self.assertEqual(self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": "   "}).status_code, 400)
        years = {y["label"]: y for y in self.call(self.v, "get", "/admin/years/").json()}
        self.assertEqual((years["2027-28"]["drafts_pending"], years["2026-27"]["locked"], years["2027-28"]["locked"]), (585, True, False))
        stale = self.call(self.v, "post", "/admin/years/2027-28/finalize/", {"expected_pending": 584})
        self.assertEqual((stale.status_code, stale.json()["code"]), (409, "stale"))
        self.assertFalse(AnnualAssignment.objects.filter(year__label="2027-28").exists())
        ok = self.call(self.v, "post", "/admin/years/2027-28/finalize/", {"expected_pending": 585})
        self.assertEqual((ok.status_code, ok.json()["finalized"]), (200, 585))
        twice = self.call(self.v, "post", "/admin/years/2027-28/finalize/", {"expected_pending": 585})  # double click
        self.assertEqual((twice.status_code, twice.json()["code"]), (409, "nothing_pending"))
        finals = AnnualAssignment.objects.filter(year__label="2027-28")
        self.assertEqual(finals.count(), 585)
        self.assertEqual(finals.values("department", "kra").distinct().count(), 585)  # no duplicates
        a = finals.get(department=self.cse, kra__number=33)
        self.assertEqual(a.target_text, target)
        r = self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": "changed"})
        self.assertEqual((r.status_code, r.json()["code"]), (409, "finalized"))
        self.assertEqual(self.call(self.v, "delete", f"/admin/drafts/{d.id}/").status_code, 409)
        a.target_text = "changed"
        with self.assertRaises(ValidationError):
            a.save()  # model guard as well
        self.assertEqual(self.call(self.v, "post", "/admin/drafts/", {"year": "2027-28", "department": "CSE", "kra": 33,
                                                                       "target_text": "x"}).status_code, 409)
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        self.assertTrue({"assignments.copy", "assignment_draft.update", "assignments.finalize"} <= actions)

    def test_finalize_conflict_rolls_back(self):
        self.call(self.v, "post", "/admin/drafts/", {"year": "2028-29", "department": "CSE", "kra": 1, "target_text": "1"})
        self.call(self.v, "post", "/admin/drafts/", {"year": "2028-29", "department": "ECE", "kra": 1, "target_text": "1"})
        y = AcademicYear.objects.get(label="2028-29")
        AnnualAssignment.objects.create(department=self.ece, kra=KRA.objects.get(number=1), year=y, target_text="pre-existing",
                                        template_version=TemplateVersion.objects.get(key="kra1"))  # e.g. created elsewhere
        r = self.call(self.v, "post", "/admin/years/2028-29/finalize/", {"expected_pending": 2})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(AnnualAssignment.objects.filter(year=y).count(), 1)  # nothing finalized
        self.assertFalse(DraftAssignment.objects.filter(year=y, finalized_assignment__isnull=False).exists())

    def test_create_kra_template_compatibility(self):
        base = {"title": "Synthetic new activity", "nba_ref": "", "naac_ref": "7.9.9"}
        r = self.call(self.v, "post", "/admin/kras/", {**base, "template_key": "kra99", "template_version": 1, "confirm_layout": True})
        self.assertEqual((r.status_code, list(r.json()["field_errors"])), (400, ["template"]))  # not installed
        r = self.call(self.v, "post", "/admin/kras/", {**base, "template_key": "kra41", "template_version": 1})
        self.assertEqual((r.status_code, list(r.json()["field_errors"])), (400, ["confirm_layout"]))  # layout fit must be confirmed
        broken = TemplateVersion.objects.create(key="synthetic_broken", version=1, title="Broken", schema={}, renderer_template="reports/missing.html")
        r = self.call(self.v, "post", "/admin/kras/", {**base, "template_key": broken.key, "template_version": 1, "confirm_layout": True})
        self.assertEqual(r.status_code, 400)
        r = self.call(self.v, "post", "/admin/kras/", {**base, "template_key": "kra41", "template_version": 1, "confirm_layout": True})
        self.assertEqual(r.status_code, 201, r.content)
        k = KRA.objects.get(number=46)
        self.assertEqual((k.activity_text, k.default_template.key), ("KRA 46: Synthetic new activity", "kra41"))
        self.assertEqual(self.call(self.v, "post", "/admin/kras/", {**base, "number": 46, "template_key": "kra41", "template_version": 1,
                                                                    "confirm_layout": True}).status_code, 400)  # no duplicate number
        r = self.call(self.v, "post", "/admin/drafts/", {"year": "2027-28", "department": "CSE", "kra": 46, "target_text": "2 Per Year"})
        self.assertEqual((r.status_code, r.json()["template"]["key"]), (201, "kra41"))  # default template prefilled
        self.assertIn("kra.create", AuditEvent.objects.values_list("action", flat=True))
        tpl = {t["key"]: t for t in self.call(self.v, "get", "/admin/templates/").json()}
        self.assertIsNone(tpl["kra41"]["problem"])
        self.assertIsNotNone(tpl["synthetic_broken"]["problem"])

    def test_dean_sees_only_own_finalized_assignments(self):
        self.copy()
        r = self.call(self.d, "get", "/assignments/?year=2027-28")
        self.assertEqual(r.json()["results"], [])  # drafts are invisible to Deans
        self.call(self.v, "post", "/admin/years/2027-28/finalize/", {"expected_pending": 585})
        rows = self.call(self.d, "get", "/assignments/?year=2027-28").json()["results"]
        self.assertEqual((len(rows), {x["department"]["code"] for x in rows}), (45, {"CSE"}))
        vc_rows = self.call(self.v, "get", "/assignments/?year=2026-27").json()["results"]  # historical read for the VC
        self.assertEqual(len(vc_rows), 585)

    def test_existing_submission_workflow_unaffected(self):
        self.copy()
        self.call(self.v, "post", "/admin/years/2027-28/finalize/", {"expected_pending": 585})
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(self.d, self.asg_a, self.p2)
            self.assertEqual(self.detail(self.d, sid)["assignment"]["target_text"], self.asg_a.target_text)
