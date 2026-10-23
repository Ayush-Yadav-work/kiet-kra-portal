"""VC Phase 1 analytics — formula, scopes, classification and known-fixture totals (plan v2.3 §6, §13; D-074).
Pure aggregation tests use materialised input (no database); the fixture test reads through `load` inside the test
transaction (aggregation only). Real snapshot/API boundaries are in test_vc_snapshot.py (TransactionTestCase)."""
import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.catalogue.models import KRA, AcademicYear, AnnualAssignment, DraftAssignment, ReportingPeriod, TemplateVersion
from apps.evidence.models import Evidence
from apps.submissions import analytics
from apps.submissions.models import ReviewDecision, Submission, SubmissionRevision
from apps.submissions.services import classify
from tests.base import PortalTestCase, frozen, ist

T0 = datetime.datetime(2030, 7, 1, tzinfo=datetime.timezone.utc)
PERIODS = [{"id": i, "index": i, "label": f"P{i}", "opens_at": T0 + datetime.timedelta(days=61 * (i - 1)),
            "closes_at": T0 + datetime.timedelta(days=61 * i)} for i in range(1, 7)]


def dataset(n, approved, as_of_period=2, start=None, depts=("CSE",), drafts=0, sub_status="APPROVED"):
    """n assignments per department; `approved` = {period index: approved count} (first k assignments of each period)."""
    assignments, subs = [], []
    for d in depts:
        for k in range(n):
            aid = f"{d}-{k}"
            assignments.append({"id": aid, "department__code": d, "kra__number": k + 1, "kra__activity_text": f"KRA {k + 1}: x",
                                "target_text": "1", "effective_start_period__index": start})
            for p, count in approved.items():
                if k < count:
                    subs.append({"id": f"s-{aid}-{p}", "assignment_id": aid, "period_id": p, "status": sub_status, "edit_version": 3,
                                 "is_nil": False, "achievement_text": "", "has_ev": True, "last_decision": "APPROVE", "reopened": False,
                                 "current_revision__achievement_text": "done", "current_revision__is_nil": False,
                                 "current_revision__sequence": 1})
    as_of = PERIODS[as_of_period - 1]["opens_at"] + datetime.timedelta(days=3)
    return ({"periods": PERIODS, "assignments": assignments, "subs": subs, "drafts_pending": drafts,
             "departments": [{"code": d, "name": d} for d in depts]}, as_of)


def filt(scope, period=None, status=""):
    return {"year": SimpleNamespace(label="2030-31"), "scope": scope, "period": period and SimpleNamespace(id=period, label=f"P{period}",
            opens_at=PERIODS[period - 1]["opens_at"]), "departments": [], "kras": [], "status": status, "page": 1, "page_size": 50}


class FormulaTests(SimpleTestCase):
    def test_single_period_30_of_40(self):
        data, as_of = dataset(40, {1: 30})
        s = analytics.compute(data, filt("period", 1), as_of)["summary"]
        self.assertEqual((s["approved"], s["expected"], s["remaining"], s["rate_label"]), (30, 40, 10, "75.0%"))

    def test_ytd_and_full_year_denominators(self):
        data, as_of = dataset(40, {1: 30, 2: 30})  # two periods opened, 60 approved reports
        ytd = analytics.compute(data, filt("ytd"), as_of)
        year = analytics.compute(data, filt("year"), as_of)
        self.assertEqual((ytd["summary"]["approved"], ytd["summary"]["expected"], ytd["summary"]["rate_label"]), (60, 80, "75.0%"))
        self.assertEqual((year["summary"]["approved"], year["summary"]["expected"], year["summary"]["rate_label"]), (60, 240, "25.0%"))
        self.assertEqual(year["breakdown"]["NOT_DUE"], 160)  # future slots: Not due, still expected for the full year
        self.assertEqual(ytd["breakdown"]["NOT_DUE"], 0)
        trend = {t["index"]: t for t in ytd["trend"]}
        self.assertEqual((trend[2]["rate_label"], trend[3]["rate_label"], trend[3]["expected"]), ("75.0%", "Not due", 40))  # no fake 0 %

    def test_zero_denominators_and_future_period(self):
        empty, as_of = dataset(0, {})
        self.assertEqual(analytics.compute(empty, filt("ytd"), as_of)["summary"]["rate_label"], "No assignments")
        late, as_of = dataset(5, {}, start=5)  # assigned from P5, now in P2
        self.assertEqual(analytics.compute(late, filt("ytd"), as_of)["summary"]["rate_label"], "No applicable reporting periods")
        future = analytics.compute(late, filt("period", 6), as_of)["summary"]
        self.assertEqual((future["expected"], future["rate_label"]), (5, "Not due"))  # planned count, no rate

    def test_late_start_gives_four_annual_slots_and_no_past_obligation(self):
        data, as_of = dataset(1, {}, as_of_period=3, start=3)
        r = analytics.compute(data, filt("year"), as_of)
        self.assertEqual((r["summary"]["expected"], r["breakdown"]["NOT_SUBMITTED"], r["breakdown"]["NOT_DUE"]), (4, 1, 3))
        self.assertEqual(sorted({d["period_index"] for d in r["details"]}), [3, 4, 5, 6])  # P1, P2 excluded, never "Not submitted"
        self.assertEqual(analytics.compute(data, filt("ytd"), as_of)["summary"]["expected"], 1)

    def test_weighted_aggregation_and_status_filter_does_not_inflate(self):
        data, as_of = dataset(1, {1: 1}, depts=("CSE",))
        other, _ = dataset(3, {}, depts=("ECE",))
        data["assignments"] += other["assignments"]
        data["departments"] += other["departments"]
        r = analytics.compute(data, filt("period", 1), as_of)
        self.assertEqual((r["summary"]["approved"], r["summary"]["expected"], r["summary"]["rate_label"]), (1, 4, "25.0%"))  # not avg(100, 0)
        only = analytics.compute(data, filt("period", 1, status="APPROVED"), as_of)
        self.assertEqual((only["summary"]["rate_label"], len(only["details"])), ("25.0%", 1))  # filter narrows rows only
        self.assertEqual({d["code"]: d["rate_label"] for d in r["departments"]}, {"CSE": "100.0%", "ECE": "0.0%"})

    def test_csv_formula_neutralised(self):
        from apps.submissions.analytics_views import cell
        self.assertEqual([cell(x) for x in ("=1+1", "+cmd", "-2", "@x", "50% student/Year", None)],
                         ["'=1+1", "'+cmd", "'-2", "'@x", "50% student/Year", ""])

    def test_classification(self):
        self.assertEqual(classify(None, None, None, None), "NOT_SUBMITTED")
        self.assertEqual(classify("DRAFT", 0, False, None), "NOT_SUBMITTED")  # C11 untouched shell
        self.assertEqual(classify("DRAFT", 0, True, None), "DRAFT")  # evidence only (e.g. a Drive link) is a genuine draft
        self.assertEqual(classify("SUBMITTED", 2, True, None), "AWAITING_REVIEW")
        self.assertEqual(classify("REJECTED", 4, True, "RETURN"), "RETURNED")
        self.assertEqual(classify("REJECTED", 4, True, "REJECT"), "REJECTED")  # return → resubmit → reject shows Rejected
        self.assertEqual(classify("APPROVED", 1, False, "APPROVE"), "APPROVED")  # an approved Nil report counts as approved


NOW = ist(2026, 10, 1)  # 2026-27: P1 closed, P2 open


class FixtureTests(PortalTestCase):
    def sub(self, asg, period, status, decisions=(), edit_version=3, nil=False):
        s = Submission.objects.create(assignment=asg, period=period, status=status, edit_version=edit_version, created_by=self.dean_a, is_nil=nil)
        if status != "DRAFT":
            rev = SubmissionRevision.objects.create(submission=s, sequence=1, payload={}, is_nil=nil, achievement_text="ach",
                                                    snapshot={}, evidence_manifest=[], manifest_hash="x", submitted_by=self.dean_a, submitted_at=NOW)
            for i, dec in enumerate(decisions):
                ReviewDecision.objects.create(revision=rev, reviewer=self.vc, reviewer_name="VC", decision=dec, reason="" if dec == "APPROVE" else "r",
                                              created_at=NOW + datetime.timedelta(minutes=i))
            s.current_revision = rev
            s.save()
        return s

    def test_known_fixture_unequal_departments_and_comparison(self):
        k33 = KRA.objects.get(number=33)
        a = {(x.department.code, x.kra.number): x for x in AnnualAssignment.objects.filter(year__label="2026-27", kra=k33).select_related("department", "kra")}
        self.sub(a[("CSE", 33)], self.p1, "APPROVED", ["APPROVE"], nil=True)
        self.sub(a[("CSE", 33)], self.p2, "SUBMITTED")
        self.sub(a[("ECE", 33)], self.p1, "REJECTED", ["APPROVE", "RETURN"])
        self.sub(a[("ECE", 33)], self.p2, "DRAFT", edit_version=0)  # untouched shell
        ev = self.sub(a[("ME", 33)], self.p2, "DRAFT", edit_version=0)  # evidence-only draft
        Evidence.objects.create(submission=ev, source_type="DRIVE_LINK", category="x", label="x", drive_url="https://drive.google.com/x", uploaded_by=self.dean_a)
        k46 = KRA.objects.create(number=46, activity_text="KRA 46: Synthetic", default_template=TemplateVersion.objects.get(key="kra41"))
        AnnualAssignment.objects.create(department=self.cse, kra=k46, year=self.p1.year, target_text="1",
                                        template_version=k46.default_template, effective_start_period=self.p2)  # CSE only, from P2
        DraftAssignment.objects.create(department=self.ece, kra=k46, year=self.p1.year, target_text="d", template_version=k46.default_template,
                                       created_by=self.vc)  # unpublished: excluded, shown as pending
        y = AcademicYear.objects.get(label="2026-27")
        f = {"year": y, "scope": "ytd", "period": None, "departments": ["CSE", "ECE", "ME", "IT"], "kras": [33, 46], "status": "",
             "page": 1, "page_size": 50}
        with frozen(NOW):
            r = analytics.compute(analytics.load(f, NOW), f, NOW)
        depts = {d["code"]: d for d in r["departments"]}
        self.assertEqual((depts["CSE"]["assignments"], depts["CSE"]["expected"], depts["CSE"]["approved"]), (2, 3, 1))  # unequal totals
        self.assertEqual((depts["ECE"]["assignments"], depts["ECE"]["expected"], depts["ECE"]["approved"]), (1, 2, 0))
        self.assertEqual(depts["ECE"]["breakdown"]["RETURNED"], 1)
        self.assertNotIn("DRAFT", depts["ME"]["breakdown"])  # draft privacy (D-078): the evidence-only draft is Not submitted
        self.assertEqual(depts["ME"]["breakdown"]["NOT_SUBMITTED"], 2)
        self.assertEqual(r["breakdown"]["NOT_SUBMITTED"], 6)  # ECE P2 shell, ME P1, ME P2 draft, IT P1, IT P2, CSE KRA 46 P2 (its P1 is not assigned)
        self.assertEqual((r["summary"]["approved"], r["summary"]["expected"], r["drafts_pending"]), (1, 9, 1))
        cells = dict(zip(r["matrix"]["kras"], next(x for x in r["matrix"]["rows"] if x["department"] == "ECE")["cells"]))
        self.assertIsNone(cells[46])  # not assigned to ECE: N/A, not zero
        self.assertEqual(sum(d["expected"] for d in r["departments"]), r["summary"]["expected"])  # comparison reconciles
        year = dict(f, scope="year")
        with frozen(NOW):
            y_r = analytics.compute(analytics.load(year, NOW), year, NOW)
        self.assertEqual(y_r["summary"]["expected"], 4 * 6 + 5)  # four KRA 33 rows × 6 + CSE KRA 46 from P2
