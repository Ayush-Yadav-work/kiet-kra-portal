"""Phase 5A behaviours carried into VC Phase 1 (D-065 → D-073): copy, exact draft targets, finalisation, immutability,
year locking. Updated for selective finalisation and developer-installed KRAs. SYNTHETIC data only."""
from django.core.exceptions import ValidationError

from apps.audit.models import AuditEvent
from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, DraftAssignment, TemplateVersion
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1)  # 2026-27 is the current year (P1 closed, P2 open); 2027-28 and 2028-29 not started


class Phase5ATests(PortalTestCase):
    def setUp(self):
        self.v = self.client_for(self.vc)
        self.d = self.client_for(self.dean_a)

    def call(self, client, method, path, body=None):
        with frozen(NOW):
            return getattr(client, method)(f"/api/v1{path}", body, format="json") if body is not None else getattr(client, method)(f"/api/v1{path}")

    def copy(self, target="2027-28", source="2026-27"):
        return self.call(self.v, "post", f"/admin/years/{target}/copy/", {"source_year": source})

    def fin(self, year, drafts, start=None, at=NOW):
        with frozen(at):
            return self.finalise(self.v, year, [DraftAssignment.objects.get(pk=d.pk) for d in drafts], start)

    def new_kra(self, number=46):
        """A developer-installed KRA (catalogue + working template); the VC cannot create one through the API."""
        return KRA.objects.create(number=number, activity_text=f"KRA {number}: Synthetic installed activity",
                                  default_template=TemplateVersion.objects.get(key="kra41"))

    def test_dean_and_anonymous_denied_everywhere(self):
        draft = DraftAssignment.objects.create(department=self.cse, kra=KRA.objects.get(number=1), year=AcademicYear.objects.get(label="2027-28"),
                                               target_text="1", template_version=TemplateVersion.objects.get(key="kra1"), created_by=self.vc)
        item = [{"id": str(draft.id), "edit_version": 0}]
        anon = self.client_class()
        for client, codes in ((self.d, {403}), (anon, {401, 403})):
            for method, path, body in (("get", "/admin/templates/", None), ("get", "/admin/kras/", None), ("post", "/admin/kras/", {}),
                                       ("get", "/admin/years/", None), ("get", "/admin/allocations/?year=2027-28", None),
                                       ("post", "/admin/years/2027-28/copy/", {"source_year": "2026-27"}),
                                       ("post", "/admin/years/2027-28/finalise/preview/", {"items": item}),
                                       ("post", "/admin/years/2027-28/finalise/", {"token": "x"}), ("post", "/admin/drafts/", {}),
                                       ("patch", f"/admin/drafts/{draft.id}/", {"target_text": "9", "edit_version": 0}),
                                       ("post", "/admin/drafts/remove/", {"items": item}), ("post", "/admin/drafts/restore/", {"items": item}),
                                       ("post", "/admin/drafts/bulk-target/", {"items": item, "target_text": "9", "apply": True})):
                r = self.call(client, method, path, body)
                self.assertIn(r.status_code, codes, (client, method, path))
        draft.refresh_from_db()
        self.assertEqual((draft.target_text, draft.removed_at), ("1", None))
        self.assertFalse(AnnualAssignment.objects.filter(year__label="2027-28").exists())

    def test_copy_preserves_source_and_handles_repeats(self):
        before = list(AnnualAssignment.objects.filter(year__label="2026-27").order_by("pk").values_list("pk", "target_text", "template_version_id"))
        preview = self.call(self.v, "post", "/admin/years/2027-28/copy/?preview=1", {"source_year": "2026-27"})
        self.assertEqual((preview.status_code, len(preview.json()["create"])), (200, 585))
        self.assertFalse(DraftAssignment.objects.exists())  # preview writes nothing
        r = self.copy()
        self.assertEqual((r.status_code, r.json()["created"]), (200, 585), r.content)
        drafts = DraftAssignment.objects.filter(year__label="2027-28")
        self.assertEqual(drafts.count(), 585)
        src = AnnualAssignment.objects.get(department=self.cse, kra__number=24, year__label="2026-27")
        d = drafts.get(department=self.cse, kra__number=24)
        self.assertEqual((d.target_text, d.template_version_id, d.copied_from_id, d.source_target, d.source_year.label),
                         (src.target_text, src.template_version_id, src.pk, src.target_text, "2026-27"))
        self.assertTrue(drafts.filter(target_text__contains="%").exists())  # percentages kept as text
        self.assertTrue(drafts.filter(target_text="NIL").exists())
        again = self.copy()  # repeated request: nothing overwritten
        self.assertEqual((again.json()["created"], len(again.json()["drafts_preserved"])), (0, 585))
        self.assertEqual(list(AnnualAssignment.objects.filter(year__label="2026-27").order_by("pk").values_list("pk", "target_text", "template_version_id")), before)
        self.assertEqual(self.copy(target="2026-27", source="2026-27").status_code, 400)  # source must be earlier
        self.assertEqual(self.copy(target="2027-28", source="2028-29").status_code, 400)

    def test_draft_edit_then_finalise_then_immutable(self):
        self.copy()
        d = DraftAssignment.objects.get(year__label="2027-28", department=self.cse, kra__number=33)
        target = "2 events (incl. 1 alumni meet) — 50% online; NA if no chapter"
        r = self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": target, "edit_version": 0})
        self.assertEqual((r.status_code, r.json()["target_text"], r.json()["edit_version"]), (200, target, 1))  # exact string
        stale = self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": "other tab", "edit_version": 0})
        self.assertEqual((stale.status_code, stale.json()["code"]), (409, "conflict"))  # second tab with an old version
        self.assertEqual(self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": "   ", "edit_version": 1}).status_code, 200)  # drafts may be incomplete
        blank = self.fin("2027-28", [d])
        self.assertEqual((blank.status_code, blank.json()["conflicts"][0]["reason"]), (409, "blank target"))  # but never finalised blank
        self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": target, "edit_version": 2})
        years = {y["label"]: y for y in self.call(self.v, "get", "/admin/years/").json()}
        self.assertEqual((years["2027-28"]["drafts"], years["2027-28"]["state"], years["2026-27"]["state"]), (585, "preparation", "active"))
        ok = self.fin("2027-28", DraftAssignment.objects.filter(year__label="2027-28"))
        self.assertEqual((ok.status_code, ok.json()["finalised"]), (200, 585), ok.content)
        finals = AnnualAssignment.objects.filter(year__label="2027-28")
        self.assertEqual((finals.count(), finals.values("department", "kra").distinct().count()), (585, 585))  # no duplicates
        a = finals.get(department=self.cse, kra__number=33)
        self.assertEqual((a.target_text, a.effective_start_period.index, a.finalised_by_id), (target, 1, self.vc.id))
        r = self.call(self.v, "patch", f"/admin/drafts/{d.id}/", {"target_text": "changed", "edit_version": 3})
        self.assertEqual((r.status_code, r.json()["code"]), (409, "not_draft"))
        r = self.call(self.v, "post", "/admin/drafts/remove/", {"items": [{"id": str(d.id), "edit_version": 3}]})
        self.assertEqual(r.status_code, 409)  # finalised rows are never removed
        a.target_text = "changed"
        with self.assertRaises(ValidationError):
            a.save()  # model guard as well
        r = self.call(self.v, "post", "/admin/drafts/", {"year": "2027-28", "departments": ["CSE"], "kra": 33})
        self.assertEqual(r.json()["skipped"], [{"department": "CSE", "reason": "finalised"}])
        actions = set(AuditEvent.objects.values_list("action", flat=True))
        self.assertTrue({"assignments.copy", "assignment_draft.update", "assignments.finalise"} <= actions)

    def test_finalise_conflict_rolls_back(self):
        self.new_kra()
        self.call(self.v, "post", "/admin/drafts/", {"year": "2028-29", "departments": ["CSE", "ECE"], "kra": 46, "target_text": "1"})
        y = AcademicYear.objects.get(label="2028-29")
        drafts = list(DraftAssignment.objects.filter(year=y))
        AnnualAssignment.objects.create(department=self.ece, kra=KRA.objects.get(number=46), year=y, target_text="pre-existing",
                                        template_version=TemplateVersion.objects.get(key="kra41"))  # e.g. created elsewhere
        r = self.fin("2028-29", drafts)
        self.assertEqual((r.status_code, r.json()["conflicts"][0]["reason"]), (409, "already finalised"))
        self.assertEqual(AnnualAssignment.objects.filter(year=y).count(), 1)  # nothing finalised
        self.assertFalse(DraftAssignment.objects.filter(year=y, finalized_assignment__isnull=False).exists())

    def test_vc_cannot_create_kras_developer_installed_kra_is_eligible(self):
        r = self.call(self.v, "post", "/admin/kras/", {"title": "Synthetic new activity", "template_key": "kra41", "template_version": 1,
                                                      "confirm_layout": True})
        self.assertEqual(r.status_code, 405)  # master KRAs and templates are developer-installed (plan §1)
        self.assertFalse(KRA.objects.filter(number=46).exists())
        broken = TemplateVersion.objects.create(key="synthetic_broken", version=1, title="Broken", schema={}, renderer_template="reports/missing.html")
        KRA.objects.create(number=47, activity_text="KRA 47: Synthetic incomplete", default_template=broken)
        r = self.call(self.v, "post", "/admin/drafts/", {"year": "2027-28", "departments": ["CSE"], "kra": 47})
        self.assertEqual((r.status_code, r.json()["code"]), (409, "template_unavailable"))  # incomplete template cannot be allocated
        self.new_kra()
        r = self.call(self.v, "post", "/admin/drafts/", {"year": "2027-28", "departments": ["CSE"], "kra": 46, "target_text": "2 Per Year"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(DraftAssignment.objects.get(kra__number=46).template_version.key, "kra41")  # default template prefilled
        kras = {k["number"]: k for k in self.call(self.v, "get", "/admin/kras/").json()}
        self.assertEqual((kras[46]["installed"], kras[47]["installed"]), (True, False))
        tpl = {t["key"]: t for t in self.call(self.v, "get", "/admin/templates/").json()}
        self.assertIsNone(tpl["kra41"]["problem"])
        self.assertIsNotNone(tpl["synthetic_broken"]["problem"])

    def test_dean_sees_only_own_finalised_assignments(self):
        self.copy()
        r = self.call(self.d, "get", "/assignments/?year=2027-28")
        self.assertEqual(r.json()["results"], [])  # drafts are invisible to Deans
        self.fin("2027-28", DraftAssignment.objects.filter(year__label="2027-28"))
        rows = self.call(self.d, "get", "/assignments/?year=2027-28").json()["results"]
        self.assertEqual((len(rows), {x["department"]["code"] for x in rows}), (45, {"CSE"}))
        vc_rows = self.call(self.v, "get", "/assignments/?year=2026-27").json()["results"]  # historical read for the VC
        self.assertEqual(len(vc_rows), 585)

    def test_existing_submission_workflow_unaffected(self):
        self.copy()
        self.fin("2027-28", DraftAssignment.objects.filter(year__label="2027-28"))
        with frozen(ist(2026, 10, 1)):
            sid = self.open_draft(self.d, self.asg_a, self.p2)
            self.assertEqual(self.detail(self.d, sid)["assignment"]["target_text"], self.asg_a.target_text)

    def test_current_year_new_pair_finalises_existing_stay_fixed(self):
        self.new_kra()
        existing = AnnualAssignment.objects.get(department=self.cse, kra__number=33, year__label="2026-27")
        original = existing.target_text
        r = self.call(self.v, "post", "/admin/drafts/", {"year": "2026-27", "departments": ["CSE"], "kra": 33, "target_text": "changed"})
        self.assertEqual(r.json()["skipped"], [{"department": "CSE", "reason": "finalised"}])  # an existing target cannot be replaced
        r = self.call(self.v, "post", "/admin/drafts/", {"year": "2026-27", "departments": ["CSE"], "kra": 46, "target_text": "2 Per Year"})
        self.assertEqual(r.status_code, 201, r.content)
        ok = self.fin("2026-27", DraftAssignment.objects.filter(kra__number=46))
        self.assertEqual((ok.status_code, ok.json()["finalised"]), (200, 1))
        new = AnnualAssignment.objects.get(department=self.cse, kra__number=46, year__label="2026-27")
        self.assertEqual((new.target_text, new.effective_start_period.index), ("2 Per Year", 2))  # published during P2
        existing.refresh_from_db()
        self.assertEqual((AnnualAssignment.objects.filter(year__label="2026-27").count(), existing.target_text), (586, original))
        rows = self.call(self.d, "get", "/assignments/?year=2026-27").json()["results"]  # visible to the CSE Dean at once
        self.assertIn(46, [x["kra"]["number"] for x in rows])
        ece = self.call(self.client_for(self.dean_b), "get", "/assignments/?year=2026-27").json()["results"]
        self.assertNotIn(46, [x["kra"]["number"] for x in ece])  # other departments unaffected

    def test_new_current_year_assignment_has_no_past_obligations(self):
        self.new_kra()
        self.call(self.v, "post", "/admin/drafts/", {"year": "2026-27", "departments": ["CSE"], "kra": 46, "target_text": "1"})
        self.fin("2026-27", DraftAssignment.objects.filter(kra__number=46))
        a = AnnualAssignment.objects.get(department=self.cse, kra__number=46, year__label="2026-27")
        closed = self.call(self.d, "post", f"/assignments/{a.id}/periods/{self.p1.id}/", {})
        self.assertEqual((closed.status_code, closed.json()["code"]), (409, "not_applicable"))  # no backdated report
        info = self.call(self.d, "get", f"/assignments/{a.id}/periods/{self.p1.id}/").json()
        self.assertEqual((info["submission_id"], info["can_request_reopen"], info["applicability"]), (None, False, "NOT_ASSIGNED"))
        r = self.call(self.d, "post", f"/assignments/{a.id}/periods/{self.p1.id}/reopen-requests/", {"reason": "x"})
        self.assertEqual((r.status_code, r.json()["code"]), (409, "not_applicable"))  # a new assignment cannot reopen a prior period
        self.assertEqual(self.call(self.d, "post", f"/assignments/{a.id}/periods/{self.p2.id}/", {}).status_code, 201)
        self.assertFalse(a.submissions.filter(period=self.p1).exists())

    def test_elapsed_year_read_only(self):
        self.copy()
        draft = DraftAssignment.objects.filter(year__label="2027-28").first()
        with frozen(ist(2027, 9, 1)):  # 2026-27 has ended; 2027-28 is current
            r = self.v.post("/api/v1/admin/drafts/", {"year": "2026-27", "departments": ["CSE"], "kra": 1, "target_text": "x"}, format="json")
            self.assertEqual((r.status_code, r.json()["code"]), (409, "year_locked"))
            years = {y["label"]: y for y in self.v.get("/api/v1/admin/years/").json()}
            self.assertEqual((years["2026-27"]["state"], years["2027-28"]["state"]), ("closed", "active"))
            r = self.v.patch(f"/api/v1/admin/drafts/{draft.id}/", {"target_text": "Edited in the current year", "edit_version": 0}, format="json")
            self.assertEqual(r.status_code, 200)  # current-year drafts stay editable after 1 July
        with frozen(ist(2028, 9, 1)):  # 2027-28 has ended too
            r = self.v.patch(f"/api/v1/admin/drafts/{draft.id}/", {"target_text": "late", "edit_version": 1}, format="json")
            self.assertEqual((r.status_code, r.json()["code"]), (409, "year_locked"))
            r = self.finalise(self.v, "2027-28", [DraftAssignment.objects.get(pk=draft.pk)])
            self.assertEqual((r.status_code, r.json()["code"]), (409, "year_closed"))

    def test_next_year_copy_from_current_year(self):
        self.new_kra()
        self.call(self.v, "post", "/admin/drafts/", {"year": "2027-28", "departments": ["CSE"], "kra": 46, "target_text": "1"})
        self.fin("2027-28", DraftAssignment.objects.filter(kra__number=46))
        with frozen(ist(2027, 9, 1)):  # 2027-28 is now the current year
            r = self.v.post("/api/v1/admin/years/2028-29/copy/", {"source_year": "2027-28"}, format="json")
        self.assertEqual((r.status_code, r.json()["created"]), (200, 1))  # next-year copy still works
