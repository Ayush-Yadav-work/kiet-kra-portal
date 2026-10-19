"""VC Phase 1 — annual allocations, selective finalisation, effective periods, publication grants, Dean applicability
(VC features plan v2.3 §3–5; D-073). SYNTHETIC data only."""
import datetime
import io

from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, Department, DraftAssignment, ReportingPeriod, TemplateVersion
from apps.submissions.models import ReopenGrant, ReopenRequest, ReviewDecision, Submission
from tests.base import PortalTestCase, frozen, ist

NOW = ist(2026, 10, 1)  # 2026-27 P2 open (closes 1 Nov 2026 00:00 IST); 2027-28 in preparation
H = datetime.timedelta(hours=1)


class AllocationTests(PortalTestCase):
    def setUp(self):
        self.v = self.client_for(self.vc)
        self.kra = KRA.objects.create(number=46, activity_text="KRA 46: Synthetic installed", default_template=TemplateVersion.objects.get(key="kra41"))

    def call(self, method, path, body=None, at=NOW, client=None):
        with frozen(at):
            c = client or self.v
            return getattr(c, method)(f"/api/v1{path}", body, format="json") if body is not None else getattr(c, method)(f"/api/v1{path}")

    def add(self, year, codes, kra=46, target="1 Per Year", at=NOW):
        r = self.call("post", "/admin/drafts/", {"year": year, "departments": codes, "kra": kra, "target_text": target}, at=at)
        assert r.status_code == 201, r.content
        return r.json()

    def drafts(self, **kw):
        return list(DraftAssignment.objects.filter(**kw).order_by("department__code"))

    def items(self, ds):
        return [{"id": str(d.id), "edit_version": DraftAssignment.objects.get(pk=d.pk).edit_version} for d in ds]

    def fin(self, year, ds, start=None, at=NOW):
        with frozen(at):
            return self.finalise(self.v, year, [DraftAssignment.objects.get(pk=d.pk) for d in ds], start)

    # ---- allocation states ----
    def test_selected_departments_only_and_unallocated_vs_removed(self):
        out = self.add("2027-28", ["CSE", "ECE"])
        self.assertEqual(len(out["created"]), 2)
        self.assertEqual(DraftAssignment.objects.filter(kra=self.kra).count(), 2)  # nothing for the other departments
        listing = self.call("get", "/admin/allocations/?year=2027-28").json()
        states = {(r["department"], r["kra"]): r["state"] for r in listing["allocations"]}
        self.assertEqual((states[("CSE", 46)], states.get(("ME", 46))), ("DRAFT", None))  # ME is Unallocated: no row
        self.assertEqual((listing["year"]["drafts"], listing["year"]["state"]), (2, "preparation"))
        cse = self.drafts(kra=self.kra, department=self.cse)[0]
        r = self.call("post", "/admin/drafts/remove/", {"items": self.items([cse])})
        self.assertEqual(r.status_code, 200, r.content)
        listing = self.call("get", "/admin/allocations/?year=2027-28").json()
        self.assertEqual({(r["department"], r["kra"]): r["state"] for r in listing["allocations"]}[("CSE", 46)], "REMOVED")
        self.assertEqual((listing["year"]["drafts"], listing["year"]["removed"]), (1, 1))
        again = self.add("2027-28", ["CSE", "ME"])  # adding never resurrects a removed row
        self.assertEqual(again["skipped"], [{"department": "CSE", "reason": "removed — use Restore"}])
        r = self.call("post", "/admin/drafts/restore/", {"items": self.items([cse])})
        self.assertEqual(r.status_code, 200)
        cse.refresh_from_db()
        self.assertEqual((cse.removed_at, cse.target_text), (None, "1 Per Year"))  # retained target
        self.assertEqual(self.call("post", "/admin/drafts/restore/", {"items": self.items([cse])}).status_code, 409)  # not removed

    def test_previous_year_prefill_is_department_specific_and_copy_never_resurrects(self):
        a_cse = AnnualAssignment.objects.get(year__label="2026-27", department=self.cse, kra__number=39)
        a_ece = AnnualAssignment.objects.get(year__label="2026-27", department=self.ece, kra__number=39)
        self.assertNotEqual(a_cse.target_text, a_ece.target_text)
        self.add("2027-28", ["CSE", "ECE"], kra=39, target="ignored when a previous target exists")
        cse, ece = self.drafts(kra__number=39, year__label="2027-28")
        self.assertEqual((cse.target_text, cse.source_target, ece.target_text), (a_cse.target_text, a_cse.target_text, a_ece.target_text))
        self.call("post", "/admin/drafts/remove/", {"items": self.items([ece])})
        Department.objects.filter(code="ME").update(active=False)
        preview = self.call("post", "/admin/years/2027-28/copy/?preview=1", {"source_year": "2026-27"}).json()
        self.assertEqual((len(preview["drafts_preserved"]), len(preview["removed_preserved"])), (1, 1))
        self.assertEqual(len(preview["unavailable"]), 45)  # the inactive department's 45 KRAs need resolution
        self.assertEqual(len(preview["create"]), 585 - 2 - 45)
        r = self.call("post", "/admin/years/2027-28/copy/", {"source_year": "2026-27"}).json()
        ece.refresh_from_db()
        self.assertIsNotNone(ece.removed_at)  # removed draft stays removed
        self.assertEqual(r["created"], 538)
        self.assertEqual(self.call("post", "/admin/years/2027-28/copy/", {"source_year": "2026-27"}).json()["created"], 0)  # idempotent

    def test_bulk_target_scope_and_conflicts(self):
        self.add("2027-28", ["CSE", "ECE", "ME"], target="old")
        cse, ece, me = self.drafts(kra=self.kra)
        r = self.call("post", "/admin/drafts/bulk-target/", {"items": self.items([cse, ece]), "target_text": "2 Per Year", "apply": False})
        self.assertEqual([(x["department"], x["old"], x["new"]) for x in r.json()["affected"]], [("CSE", "old", "2 Per Year"), ("ECE", "old", "2 Per Year")])
        self.assertEqual(DraftAssignment.objects.get(pk=cse.pk).target_text, "old")  # preview writes nothing
        stale = self.items([cse, ece])
        self.call("patch", f"/admin/drafts/{ece.id}/", {"target_text": "edited in another tab", "edit_version": 0})
        r = self.call("post", "/admin/drafts/bulk-target/", {"items": stale, "target_text": "2 Per Year", "apply": True})
        self.assertEqual((r.status_code, r.json()["conflicts"][0]["reason"]), (409, "changed"))
        self.assertEqual(DraftAssignment.objects.get(pk=cse.pk).target_text, "old")  # all-or-nothing
        r = self.call("post", "/admin/drafts/bulk-target/", {"items": self.items([cse, ece]), "target_text": "2 Per Year", "apply": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([d.target_text for d in self.drafts(kra=self.kra)], ["2 Per Year", "2 Per Year", "old"])  # ME untouched
        self.fin("2027-28", [cse])
        r = self.call("post", "/admin/drafts/bulk-target/", {"items": self.items([cse, me]), "target_text": "x", "apply": True})
        self.assertEqual(r.status_code, 409)  # finalised rows never enter a target edit
        self.assertEqual(DraftAssignment.objects.get(pk=me.pk).target_text, "old")

    # ---- finalisation ----
    def test_partial_finalisation_idempotent_retry_and_stale_selection(self):
        self.add("2027-28", ["CSE", "ECE"])
        cse, ece = self.drafts(kra=self.kra)
        with frozen(NOW):
            pv = self.v.post("/api/v1/admin/years/2027-28/finalise/preview/", {"items": self.items([cse])}, format="json").json()
            self.assertEqual((pv["count"], pv["effective_start_period"]["index"], pv["grant"], len(pv["applicable_periods"])), (1, 1, False, 6))
            first = self.v.post("/api/v1/admin/years/2027-28/finalise/", {"token": pv["token"]}, format="json")
            retry = self.v.post("/api/v1/admin/years/2027-28/finalise/", {"token": pv["token"]}, format="json")
        self.assertEqual((first.status_code, retry.status_code, retry.json()["already_finalised"]), (200, 200, True))
        self.assertEqual(retry.json()["assignments"][0]["id"], first.json()["assignments"][0]["id"])
        self.assertEqual(AnnualAssignment.objects.filter(kra=self.kra).count(), 1)  # no duplicate
        r = self.call("patch", f"/admin/drafts/{ece.id}/", {"target_text": "still editable", "edit_version": 0})
        self.assertEqual(r.status_code, 200)  # unselected draft stays editable
        with frozen(NOW):  # finalise vs edit race: an edit after the review makes the confirmation stale
            pv = self.v.post("/api/v1/admin/years/2027-28/finalise/preview/", {"items": self.items([ece])}, format="json").json()
            self.v.patch(f"/api/v1/admin/drafts/{ece.id}/", {"target_text": "changed after review", "edit_version": 1}, format="json")
            r = self.v.post("/api/v1/admin/years/2027-28/finalise/", {"token": pv["token"]}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "conflict"))
        self.assertEqual(AnnualAssignment.objects.filter(kra=self.kra).count(), 1)
        other = self.client_for(self.vc)  # a token is bound to its review; garbage is refused
        self.assertEqual(self.call("post", "/admin/years/2027-28/finalise/", {"token": "tampered"}, client=other).status_code, 400)

    def test_effective_start_rules_and_exact_72_hour_boundary(self):
        self.add("2026-27", ["CSE", "ECE", "ME", "IT", "EEE"])
        cse, ece, eee, it, me = self.drafts(kra=self.kra)
        close = self.p2.closes_at
        r = self.fin("2026-27", [cse], at=close - 72 * H)  # exactly 72 hours left: still the current period, no grant
        self.assertEqual(r.json()["assignments"][0]["effective_start_period"], self.p2.label)
        self.assertFalse(ReopenGrant.objects.filter(source="PUBLICATION").exists())
        r = self.fin("2026-27", [ece], at=close - 71 * H)  # under 72 hours: default is the next period
        p3 = ReportingPeriod.objects.get(year__label="2026-27", index=3)
        a_ece = AnnualAssignment.objects.get(kra=self.kra, department=self.ece)
        self.assertEqual((a_ece.effective_start_period_id, r.json()["assignments"][0]["grant_expires_at"]), (p3.id, None))
        self.assertFalse(Submission.objects.filter(assignment=a_ece).exists())
        at = close - 30 * H
        with frozen(at):  # explicit current period + 72-hour publication grant
            pv = self.v.post("/api/v1/admin/years/2026-27/finalise/preview/", {"items": self.items([it]), "start": "current"}, format="json").json()
            self.assertEqual((pv["kind"], pv["grant"], sorted(pv["choices"])), ("near_deadline", True, ["current", "next"]))
            r = self.v.post("/api/v1/admin/years/2026-27/finalise/", {"token": pv["token"]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        a_it = AnnualAssignment.objects.get(kra=self.kra, department__code="IT")
        g = ReopenGrant.objects.get(source="PUBLICATION")
        self.assertEqual((a_it.effective_start_period_id, g.submission.assignment_id, g.submission.period_id, g.expires_at - g.starts_at),
                         (self.p2.id, a_it.id, self.p2.id, 72 * H))
        self.assertEqual((g.request_id, g.review_decision_id, g.starts_at), (None, None, at))
        shell = g.submission
        self.assertEqual((shell.status, shell.edit_version), ("DRAFT", 0))
        dean_it = self.make_user("t.dean.it", "DEAN", Department.objects.get(code="IT"))
        c = self.client_for(dean_it)
        with frozen(close + 20 * H):  # P2 has closed; the grant keeps the report open
            d = self.detail(c, str(shell.id))
            self.assertEqual((d["display_status"], d["editable"], d["active_grant"]["source"]), ("NOT_SUBMITTED", True, "PUBLICATION"))
            self.assertEqual(self.save(c, str(shell.id), 0, remarks="late publication").status_code, 200)
        with frozen(at + 72 * H):  # grant ends exactly 72 hours after publication
            self.assertFalse(self.detail(c, str(shell.id))["editable"])
        with frozen(close + H):  # retry of the same confirmation after P2 has closed: original outcome
            retry = self.v.post("/api/v1/admin/years/2026-27/finalise/", {"token": pv["token"]}, format="json")
        self.assertEqual((retry.status_code, retry.json()["already_finalised"]), (200, True))
        self.assertEqual(ReopenGrant.objects.filter(source="PUBLICATION").count(), 1)
        self.assertEqual(ReopenGrant.objects.get(source="PUBLICATION").expires_at, at + 72 * H)  # never extended

    def test_stale_preview_across_threshold_and_final_period_and_closed_year(self):
        self.add("2026-27", ["CSE", "ECE"])
        cse, ece = self.drafts(kra=self.kra)
        close = self.p2.closes_at
        with frozen(close - 73 * H):
            pv = self.v.post("/api/v1/admin/years/2026-27/finalise/preview/", {"items": self.items([cse])}, format="json").json()
        self.assertEqual(pv["effective_start_period"]["index"], 2)
        with frozen(close - 71 * H):  # the 72-hour threshold passed before confirmation
            r = self.v.post("/api/v1/admin/years/2026-27/finalise/", {"token": pv["token"]}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "stale_preview"))
        self.assertFalse(AnnualAssignment.objects.filter(kra=self.kra).exists())  # nothing silently re-targeted
        p6 = ReportingPeriod.objects.get(year__label="2026-27", index=6)
        late = p6.closes_at - 24 * H
        r = self.fin("2026-27", [cse], at=late)  # final period, under 72 hours, no choice
        self.assertEqual((r.status_code, r.json()["code"]), (409, "grant_required"))
        self.assertEqual(self.fin("2026-27", [cse], start="next", at=late).json()["code"], "grant_required")  # no next period exists
        r = self.fin("2026-27", [cse], start="current", at=late)
        self.assertEqual(r.status_code, 200, r.content)
        g = ReopenGrant.objects.get(source="PUBLICATION")
        self.assertGreater(g.expires_at, p6.closes_at)  # the reporting window may run past year end
        r = self.fin("2026-27", [ece], at=p6.closes_at + H)
        self.assertEqual((r.status_code, r.json()["code"]), (409, "year_closed"))

    # ---- grants ----
    def test_grant_source_constraints(self):
        with frozen(NOW):
            sid = self.open_draft(self.client_for(self.dean_a), self.asg_a, self.p2)
        sub = Submission.objects.get(pk=sid)
        req = ReopenRequest.objects.create(submission=sub, reason="x", requested_by=self.dean_a, requested_at=NOW)
        base = dict(submission=sub, starts_at=NOW, expires_at=NOW + 72 * H, approved_by=self.vc)
        for kw in ({"source": "REQUEST"}, {"source": "REVIEW"}, {"source": "PUBLICATION", "request": req}, {"source": "OTHER"},
                   {"source": "REQUEST", "request": req, "review_decision": None, "submission": sub, "expires_at": NOW}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ReopenGrant.objects.create(**{**base, **kw})
        ReopenGrant.objects.create(**base, source="PUBLICATION")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReopenGrant.objects.create(**base, source="PUBLICATION")  # one publication grant per submission
        ReopenGrant.objects.create(**base, source="REQUEST", request=req)  # later legitimate grants are still allowed
        self.assertEqual(ReopenGrant.objects.filter(submission=sub).count(), 2)

    # ---- Dean applicability ----
    def test_dean_screens_report_applicability(self):
        self.add("2026-27", ["CSE"])
        self.fin("2026-27", self.drafts(kra=self.kra), at=self.p2.closes_at - 10 * H)  # next-period default → starts in P3
        a = AnnualAssignment.objects.get(kra=self.kra)
        dean = self.client_for(self.dean_a)
        p3 = ReportingPeriod.objects.get(year__label="2026-27", index=3)
        with frozen(NOW):
            rows = {r["kra"]["number"]: r for r in dean.get(f"/api/v1/assignments/?year=2026-27&period={self.p2.id}").json()["results"]}
            self.assertEqual((rows[46]["applicability"], rows[46]["effective_start_period"]["index"], rows[33]["applicability"]),
                             ("NOT_ASSIGNED", 3, "APPLICABLE"))
            rows3 = {r["kra"]["number"]: r for r in dean.get(f"/api/v1/assignments/?year=2026-27&period={p3.id}").json()["results"]}
            self.assertEqual(rows3[46]["applicability"], "NOT_DUE")
            self.assertEqual(dean.post(f"/api/v1/assignments/{a.id}/periods/{self.p2.id}/").json()["code"], "not_applicable")
        with frozen(ist(2026, 11, 5)):
            sid = self.open_draft(dean, a, p3)
            entries = {e["period"]["index"]: e["applicability"] for e in self.detail(dean, sid)["period_entries"]}
            self.assertEqual((entries[1], entries[2], entries[3], entries[4]), ("NOT_ASSIGNED", "NOT_ASSIGNED", "APPLICABLE", "NOT_DUE"))

    def test_seed_rerun_preserves_allocations(self):
        self.add("2027-28", ["CSE", "ECE", "ME"], target="draft text")
        cse, ece, me = self.drafts(kra=self.kra)
        self.call("post", "/admin/drafts/remove/", {"items": self.items([me])})
        self.fin("2027-28", [cse])
        before = list(DraftAssignment.objects.order_by("pk").values_list("pk", "target_text", "removed_at", "finalized_assignment_id", "edit_version"))
        finals = list(AnnualAssignment.objects.order_by("pk").values_list("pk", "target_text", "effective_start_period_id", "template_version_id"))
        call_command("seed_catalogue", stdout=io.StringIO(), stderr=io.StringIO())
        self.assertEqual(list(DraftAssignment.objects.order_by("pk").values_list("pk", "target_text", "removed_at", "finalized_assignment_id", "edit_version")), before)
        self.assertEqual(list(AnnualAssignment.objects.order_by("pk").values_list("pk", "target_text", "effective_start_period_id", "template_version_id")), finals)
