"""Annual KRA allocations (VC features plan v2.3, Phase 1; D-073). One service for every write path.

States of a (year, KRA, department) pair:
  Unallocated — no row.  Draft — DraftAssignment, not removed, not finalised (VC only).  Removed — DraftAssignment with
  removed_at (restorable).  Finalised — AnnualAssignment (immutable, visible to the Dean; its draft row, if any, links to it).

Finalisation freezes `effective_start_period` (plan §3). Time always comes from one server timestamp per operation.
"""
import uuid
from datetime import timedelta

from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.errors import ApiError
from apps.audit.models import record

from .models import AcademicYear, AnnualAssignment, Department, DraftAssignment, ReportingPeriod

GRANT = timedelta(hours=72)
MAX_TARGET = 500
MAX_SELECTION = 1000  # documented cap for one finalisation/bulk request
PREVIEW_MAX_AGE = 15 * 60  # seconds a finalisation confirmation stays valid
SALT = "kra.allocations.finalise"
NOT_ASSIGNED, NOT_DUE, APPLICABLE = "NOT_ASSIGNED", "NOT_DUE", "APPLICABLE"


def err(code, message, status=400, field_errors=None, **extra):
    return ApiError(status, code, message, field_errors, extra=extra or None)


# ---------- read-side rules ----------

def year_state(year, at=None):
    """preparation (before the first period opens) / active / closed (after the last period closes or end_date passed)."""
    at = at or timezone.now()
    periods = list(year.periods.all())
    if not periods:
        return "preparation"
    first, last = min(periods, key=lambda p: p.index), max(periods, key=lambda p: p.index)
    if at < first.opens_at:
        return "preparation"
    if at >= last.closes_at or year.end_date < timezone.localdate(at):
        return "closed"
    return "active"


def applicability(assignment, period, at=None):
    """Shared rule for Dean screens and report endpoints: periods before the frozen start are not assigned; applicable
    periods that have not opened are not due yet. Legacy assignments (no start period) apply to every period."""
    eff = assignment.effective_start_period
    if eff is not None and period.index < eff.index:
        return NOT_ASSIGNED
    if (at or timezone.now()) < period.opens_at:
        return NOT_DUE
    return APPLICABLE


def start_options(year, at):
    """Publication timing for a year at `at` (plan §3): {kind, choices: {name: (period, grant)}, default}."""
    periods = sorted(year.periods.all(), key=lambda p: p.index)
    if not periods or at >= periods[-1].closes_at or year.end_date < timezone.localdate(at):
        return {"kind": "closed", "choices": {}, "default": None}
    if at < periods[0].opens_at:
        return {"kind": "before_year", "choices": {"auto": (periods[0], False)}, "default": "auto"}
    current = next((p for p in periods if p.opens_at <= at < p.closes_at), None)
    if current is None:  # between periods: the next period to open
        nxt = next(p for p in periods if p.opens_at > at)
        return {"kind": "open", "choices": {"auto": (nxt, False)}, "default": "auto"}
    if current.closes_at - at >= GRANT:
        return {"kind": "open", "choices": {"auto": (current, False)}, "default": "auto"}
    nxt = next((p for p in periods if p.index == current.index + 1), None)
    if nxt:
        return {"kind": "near_deadline", "choices": {"next": (nxt, False), "current": (current, True)}, "default": "next"}
    return {"kind": "final_period", "choices": {"current": (current, True)}, "default": None}  # must be chosen explicitly


def resolve_start(year, at, choice):
    opts = start_options(year, at)
    if opts["kind"] == "closed":
        raise err("year_closed", f"{year.label} has closed; new assignments can no longer be published.", status=409)
    choice = choice or opts["default"]
    if choice not in opts["choices"]:
        if opts["kind"] == "final_period":
            raise err("grant_required", "Fewer than 72 hours remain in the final period. Publishing requires starting in the "
                      "current period with a 72-hour reporting window; otherwise leave these allocations unpublished.", status=409)
        raise err("invalid", "Choose when these assignments start.", field_errors={"start": [f"Choose one of: {', '.join(opts['choices'])}."]})
    period, grant = opts["choices"][choice]
    return opts, choice, period, grant


def state_of(draft):
    if draft.finalized_assignment_id:
        return "FINALISED"
    return "REMOVED" if draft.removed_at else "DRAFT"


# ---------- validation helpers ----------

def clean_target(value, required=False):
    """Exact text; drafts may be incomplete, finalisation needs a non-blank target."""
    if not isinstance(value, str):
        raise err("invalid", "Enter the target text.", field_errors={"target_text": ["Must be text."]})
    if len(value) > MAX_TARGET:
        raise err("invalid", f"Target text is limited to {MAX_TARGET} characters.", field_errors={"target_text": ["Too long."]})
    if required and not value.strip():
        raise err("invalid", "Enter the target text.", field_errors={"target_text": ["Required."]})
    return value


def items_of(items):
    """[{id, edit_version}] → {id: version}, validated and capped."""
    if not isinstance(items, list) or not items:
        raise err("invalid", "Select at least one draft allocation.", field_errors={"items": ["Required."]})
    if len(items) > MAX_SELECTION:
        raise err("too_many", f"Select at most {MAX_SELECTION} allocations per request.")
    out = {}
    for it in items:
        try:
            key = str(uuid.UUID(str(it.get("id"))))
        except (AttributeError, ValueError):
            key = None
        if not key or not isinstance(it.get("edit_version"), int):
            raise err("invalid", "Each selected allocation needs its id and edit_version.", field_errors={"items": ["Invalid item."]})
        out[key] = it["edit_version"]
    return out


def lock_drafts(versions, year=None):
    """Lock the selected drafts in a deterministic order and check each version. Raises 409 listing every conflict."""
    rows = list(DraftAssignment.objects.select_for_update(of=("self",))
                .select_related("department", "kra", "year", "template_version", "finalized_assignment")
                .filter(pk__in=list(versions)).order_by("pk"))
    found = {str(d.pk): d for d in rows}
    conflicts = [{"id": i, "reason": "not_found"} for i in versions if i not in found]
    for i, d in found.items():
        if year is not None and d.year_id != year.id:
            conflicts.append({"id": i, "reason": "other_year"})
        elif d.edit_version != versions[i]:
            conflicts.append({"id": i, "reason": "changed", "edit_version": d.edit_version})
    if conflicts:
        raise err("conflict", "Some selected allocations changed or no longer exist. Reload and review them again; nothing was changed.",
                  status=409, conflicts=conflicts)
    return rows


def open_for_setup(year, at=None):
    if year_state(year, at) == "closed":
        raise err("year_locked", f"{year.label} has closed; its annual setup is read-only.", status=409)


def bump(d, **fields):
    for k, v in fields.items():
        setattr(d, k, v)
    d.edit_version += 1
    d.save()


# ---------- copy ----------

def copy_plan(source, target):
    """Read-only classification of every source assignment (plan §4.2)."""
    from .admin_views import template_problem  # shared template-readiness check

    drafts = {(d.department_id, d.kra_id): d for d in DraftAssignment.objects.filter(year=target)}
    finals = set(AnnualAssignment.objects.filter(year=target).values_list("department_id", "kra_id"))
    plan = {"create": [], "drafts_preserved": [], "finalised_skipped": [], "removed_preserved": [], "unavailable": []}
    for a in (AnnualAssignment.objects.filter(year=source).select_related("department", "kra", "template_version")
              .order_by("kra__number", "department__code")):
        pair = (a.department_id, a.kra_id)
        row = {"department": a.department.code, "kra": a.kra.number, "source_target": a.target_text}
        problem = (None if a.department.active and a.kra.active and a.template_version else "inactive department/KRA or no template")
        if a.template_version and not problem:
            problem = template_problem(a.template_version)
        if pair in finals:
            plan["finalised_skipped"].append(row)
        elif pair in drafts:
            plan["removed_preserved" if drafts[pair].removed_at else "drafts_preserved"].append(row)
        elif problem:
            plan["unavailable"].append({**row, "reason": problem})
        else:
            plan["create"].append({**row, "assignment": a})
    return plan


def plan_json(plan):
    return {k: [{x: v for x, v in r.items() if x != "assignment"} for r in rows] for k, rows in plan.items()}


def copy(source, target, user, request=None):
    if source.label >= target.label:
        raise err("invalid", "Copy from an earlier year.", field_errors={"source_year": ["Must be before the target year."]})
    with transaction.atomic():
        target = AcademicYear.objects.select_for_update().get(pk=target.pk)  # concurrent copies wait, then find drafts
        open_for_setup(target)
        plan = copy_plan(source, target)
        for r in plan["create"]:
            a = r["assignment"]
            DraftAssignment.objects.create(department=a.department, kra=a.kra, year=target, target_text=a.target_text,
                                           template_version=a.template_version, copied_from=a, source_year=source,
                                           source_target=a.target_text, created_by=user)
        record(user, "assignments.copy", target, {"source_year": source.label, "created": len(plan["create"]),
                                                  "preserved": len(plan["drafts_preserved"]) + len(plan["removed_preserved"]),
                                                  "skipped": len(plan["finalised_skipped"])}, request)
    return plan


# ---------- drafts ----------

def add_departments(year, kra, codes, user, target_text=None, request=None):
    """Create drafts only for the explicitly selected departments (plan §4.1). Prefill each from the previous year's
    finalised target for that department when one exists; otherwise from `target_text` (may be blank)."""
    from .admin_views import default_template, template_problem

    if not isinstance(codes, list) or not codes:
        raise err("invalid", "Select at least one department.", field_errors={"departments": ["Required."]})
    if target_text is not None:
        clean_target(target_text)
    tv = default_template(kra)
    if tv is None or template_problem(tv):
        raise err("template_unavailable", f"KRA {kra.number} has no installed report template; a developer must install it first.", status=409)
    with transaction.atomic():
        year = AcademicYear.objects.select_for_update().get(pk=year.pk)
        open_for_setup(year)
        depts = {d.code: d for d in Department.objects.filter(code__in=codes, active=True)}
        unknown = [c for c in codes if c not in depts]
        if unknown:
            raise err("invalid", f"Unknown or inactive department(s): {', '.join(unknown)}.", field_errors={"departments": unknown})
        previous = AcademicYear.objects.filter(label__lt=year.label).order_by("-label").first()
        sources = {a.department_id: a for a in AnnualAssignment.objects.filter(year=previous, kra=kra)} if previous else {}
        created, skipped = [], []
        for code in codes:
            d = depts[code]
            if AnnualAssignment.objects.filter(year=year, kra=kra, department=d).exists():
                skipped.append({"department": code, "reason": "finalised"}); continue
            existing = DraftAssignment.objects.filter(year=year, kra=kra, department=d).first()
            if existing:
                skipped.append({"department": code, "reason": "removed — use Restore" if existing.removed_at else "draft exists"}); continue
            src = sources.get(d.id)
            created.append(DraftAssignment.objects.create(
                department=d, kra=kra, year=year, template_version=tv, created_by=user,
                target_text=src.target_text if src else (target_text or ""), copied_from=src,
                source_year=previous if src else None, source_target=src.target_text if src else None))
        for x in created:  # one event per draft: cleanup_e2e_data and audits trace each row's provenance
            record(user, "assignment_draft.create", x, {"year": year.label, "department": x.department.code, "kra": kra.number,
                                                        "source_year": previous.label if x.source_year_id else None}, request)
    return created, skipped


def edit_target(pk, version, target_text, user, request=None):
    clean_target(target_text)
    with transaction.atomic():
        d = lock_drafts({str(pk): version})[0]
        if state_of(d) != "DRAFT":
            raise err("not_draft", f"This allocation is {state_of(d).lower()}; only drafts can be edited.", status=409)
        open_for_setup(d.year)
        old = d.target_text
        bump(d, target_text=target_text)
        record(user, "assignment_draft.update", d, {"old": old, "new": target_text, "edit_version": d.edit_version}, request)
    return d


def bulk_target(items, target_text, user, apply=False, request=None):
    """Preview (no writes) or apply one target to the confirmed drafts; all-or-nothing."""
    clean_target(target_text)
    versions = items_of(items)
    with transaction.atomic():
        rows = lock_drafts(versions)
        bad = [{"id": str(d.pk), "reason": state_of(d).lower()} for d in rows if state_of(d) != "DRAFT"]
        if bad:
            raise err("not_draft", "Only draft allocations can receive a new target; nothing was changed.", status=409, conflicts=bad)
        for y in {d.year for d in rows}:
            open_for_setup(y)
        affected = sorted(({"id": str(d.pk), "department": d.department.code, "kra": d.kra.number, "old": d.target_text, "new": target_text}
                           for d in rows), key=lambda x: (x["kra"], x["department"]))  # rows are locked by pk; shown by KRA/department
        if apply:
            for d in rows:
                old = d.target_text
                bump(d, target_text=target_text)
                record(user, "assignment_draft.update", d, {"old": old, "new": target_text, "edit_version": d.edit_version,
                                                            "bulk": len(rows)}, request)
    return affected


def set_removed(items, removed, user, request=None):
    versions = items_of(items)
    with transaction.atomic():
        rows = lock_drafts(versions)
        want = "DRAFT" if removed else "REMOVED"
        bad = [{"id": str(d.pk), "reason": state_of(d).lower()} for d in rows if state_of(d) != want]
        if bad:
            raise err("not_allowed", ("Only drafts can be removed" if removed else "Only removed allocations can be restored")
                      + "; finalised assignments never change. Nothing was changed.", status=409, conflicts=bad)
        for y in {d.year for d in rows}:
            open_for_setup(y)
        now = timezone.now()
        for d in rows:
            bump(d, removed_at=now if removed else None, removed_by=user if removed else None)
            record(user, "assignment_draft.remove" if removed else "assignment_draft.restore", d,
                   {"edit_version": d.edit_version}, request)
    return rows


# ---------- finalisation ----------

def check_finalisable(d):
    from .admin_views import template_problem

    if state_of(d) != "DRAFT":
        return state_of(d).lower()
    if not d.target_text.strip():
        return "blank target"
    if not d.department.active or not d.kra.active:
        return "inactive department or KRA"
    if d.template_version is None or template_problem(d.template_version):
        return "report template not installed"
    if AnnualAssignment.objects.filter(year=d.year, kra=d.kra, department=d.department).exists():
        return "already finalised"
    return None


def period_json_short(p):
    return {"id": p.id, "index": p.index, "label": p.label, "opens_at": p.opens_at, "closes_at": p.closes_at}


def finalise_preview(year, items, choice, user, at=None):
    at = at or timezone.now()
    versions = items_of(items)
    opts, choice, period, grant = resolve_start(year, at, choice)
    rows = list(DraftAssignment.objects.select_related("department", "kra", "year", "template_version")
                .filter(pk__in=list(versions), year=year).order_by("kra__number", "department__code"))
    if len(rows) != len(versions):
        raise err("conflict", "Some selected allocations no longer exist in this year; reload.", status=409)
    conflicts = [{"id": str(d.pk), "department": d.department.code, "kra": d.kra.number, "reason": "changed"}
                 for d in rows if d.edit_version != versions[str(d.pk)]]
    conflicts += [{"id": str(d.pk), "department": d.department.code, "kra": d.kra.number, "reason": r}
                  for d in rows if (r := check_finalisable(d))]
    if conflicts:
        raise err("conflict", "Some selected allocations cannot be finalised; resolve them first. Nothing was finalised.",
                  status=409, conflicts=conflicts)
    applicable = [p for p in sorted(year.periods.all(), key=lambda p: p.index) if p.index >= period.index]
    token = signing.dumps({"year": year.label, "items": versions, "period": period.id, "grant": grant, "choice": choice,
                           "user": str(user.pk)}, salt=SALT)
    return {"token": token, "year": year.label, "count": len(rows), "kind": opts["kind"],
            "choices": {k: {"period": period_json_short(p), "grant": g} for k, (p, g) in opts["choices"].items()},
            "choice": choice, "effective_start_period": period_json_short(period), "grant": grant,
            "grant_expires_at": at + GRANT if grant else None, "applicable_periods": [period_json_short(p) for p in applicable],
            "rows": [{"id": str(d.pk), "department": d.department.code, "kra": d.kra.number, "previous_target": d.source_target,
                      "target_text": d.target_text} for d in rows], "preview_at": at}


def create_publication_grant(assignment, period, user, at):
    """The only way to create an ASSIGNMENT_PUBLICATION grant: inside finalisation, for this exact assignment and its
    effective start period. The untouched shell stays Not submitted (C11) until the Dean uses it."""
    from apps.submissions.models import ReopenGrant, Submission

    assert period.year_id == assignment.year_id and period.id == assignment.effective_start_period_id
    shell, _ = Submission.objects.get_or_create(assignment=assignment, period=period, defaults={"created_by": user})
    assert shell.assignment_id == assignment.id and shell.period_id == period.id
    return ReopenGrant.objects.create(submission=shell, starts_at=at, expires_at=at + GRANT, approved_by=user,
                                      source=ReopenGrant.Source.PUBLICATION)


def outcome(year, drafts):
    from apps.submissions.models import ReopenGrant

    finals = [d.finalized_assignment for d in drafts]
    grants = {g.submission.assignment_id: g for g in ReopenGrant.objects.select_related("submission")
              .filter(source=ReopenGrant.Source.PUBLICATION, submission__assignment__in=finals)}
    return {"year": year.label, "finalised": len(finals),
            "assignments": [{"id": str(a.id), "draft_id": str(d.pk), "department": d.department.code, "kra": d.kra.number,
                             "effective_start_period": a.effective_start_period.label if a.effective_start_period_id else None,
                             "grant_expires_at": grants[a.id].expires_at if a.id in grants else None}
                            for d, a in zip(drafts, finals)]}


def finalise(year, token, user, at=None, request=None):
    try:
        data = signing.loads(token or "", salt=SALT, max_age=PREVIEW_MAX_AGE)
    except signing.SignatureExpired:
        raise err("preview_expired", "This review has expired. Review the selection again before finalising.", status=409)
    except signing.BadSignature:
        raise err("invalid", "Invalid confirmation; review the selection again.", status=400)
    if data["year"] != year.label or data["user"] != str(user.pk):
        raise err("invalid", "This confirmation belongs to another review.", status=400)
    at = at or timezone.now()
    try:
        with transaction.atomic():
            year = AcademicYear.objects.select_for_update().get(pk=year.pk)  # serialises finalisations of the year
            ids = sorted(data["items"])
            drafts = list(DraftAssignment.objects.select_for_update(of=("self",))
                          .select_related("department", "kra", "year", "template_version", "finalized_assignment__effective_start_period")
                          .filter(pk__in=ids, year=year).order_by("pk"))
            done = [d for d in drafts if d.finalized_assignment_id]
            if len(drafts) == len(ids) and done and len(done) == len(drafts) and all(
                    d.finalized_assignment.effective_start_period_id == data["period"] for d in done):
                return {**outcome(year, drafts), "already_finalised": True}  # retry after success: same outcome
            if len(drafts) != len(ids) or done:
                raise err("conflict", "Some selected allocations were finalised or removed elsewhere. Reload and review again; nothing was finalised.",
                          status=409)
            try:
                _, _, period, grant = resolve_start(year, at, data["choice"])
            except ApiError as e:
                if e.code == "year_closed":
                    raise
                period = grant = None  # the confirmed choice no longer exists (e.g. the 72-hour threshold passed)
            if period is None or period.id != data["period"] or grant != data["grant"]:
                raise err("stale_preview", "The reporting period or the 72-hour threshold changed since your review. Review the start "
                          "period again; nothing was finalised.", status=409)
            conflicts = [{"id": str(d.pk), "reason": "changed"} for d in drafts if d.edit_version != data["items"][str(d.pk)]]
            conflicts += [{"id": str(d.pk), "reason": r} for d in drafts if (r := check_finalisable(d))]
            if conflicts:
                raise err("conflict", "Some selected allocations changed since your review; nothing was finalised.", status=409, conflicts=conflicts)
            for d in drafts:
                a = AnnualAssignment.objects.create(department=d.department, kra=d.kra, year=year, target_text=d.target_text,
                                                    template_version=d.template_version, effective_start_period=period,
                                                    finalised_by=user, finalised_at=at)
                d.finalized_assignment = a
                d.save(update_fields=["finalized_assignment", "updated_at"])
                if grant:
                    create_publication_grant(a, period, user, at)
            record(user, "assignments.finalise", year, {"count": len(drafts), "ids": ids, "effective_start_period": period.index,
                                                        "grant": grant}, request)
            return {**outcome(year, drafts), "already_finalised": False}
    except IntegrityError:
        raise err("conflict", "An assignment for one of these department/KRA pairs already exists; nothing was finalised.", status=409)
