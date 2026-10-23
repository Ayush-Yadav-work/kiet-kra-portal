"""Announcement rules (D-077). Every write locks the announcement row; time comes from the server."""
import re
from datetime import datetime, time

from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.audit.errors import ApiError
from apps.audit.models import record
from apps.catalogue.models import Department

from .models import Announcement, AnnouncementRead, AnnouncementRecipient, AnnouncementRevision

State = Announcement.State
MAX_TITLE, MAX_BODY = 200, 10000
TAG = re.compile(r"<\s*/?\s*[a-zA-Z!]")
URL_SCHEME = re.compile(r"\b([a-zA-Z][a-zA-Z0-9+.-]*):(//)?\S+")
PENDING_BUCKETS = ("NOT_SUBMITTED", "REJECTED", "RETURNED")  # Not submitted includes saved drafts (D-078)


def bad(message, field):
    return ApiError(400, "invalid", message, {field: [message]})


# ---------- validation ----------

def clean_text(title, body):
    title, body = str(title or "").strip(), str(body or "").replace("\r\n", "\n").strip()
    if not title:
        raise bad("Enter a title.", "title")
    if not body:
        raise bad("Enter the message.", "body")
    if len(title) > MAX_TITLE:
        raise bad(f"At most {MAX_TITLE} characters.", "title")
    if len(body) > MAX_BODY:
        raise bad(f"At most {MAX_BODY} characters.", "body")
    for field, text in (("title", title), ("body", body)):
        if TAG.search(text):
            raise bad("Plain text only: HTML tags are not allowed.", field)
        for m in URL_SCHEME.finditer(text):
            if m.group(1).lower() not in ("http", "https") and m.group(2):
                raise bad("Links must start with http:// or https://.", field)
            if m.group(1).lower() in ("javascript", "data", "vbscript", "file"):
                raise bad("Links must start with http:// or https://.", field)
    return title, body


def clean_expiry(value, at):
    """None/'' = no expiry. A date means the end of that day (IST); a naive datetime is IST."""
    if value in (None, ""):
        return None
    dt = parse_datetime(str(value))
    if dt is None:
        d = parse_date(str(value))
        if d is None:
            raise bad("Enter a valid date and time.", "expires_at")
        dt = datetime.combine(d, time(23, 59, 59))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    if dt <= at:
        raise bad("The expiry must be in the future.", "expires_at")
    return dt


def clean_audience(spec):
    """{"all": true} or {"departments": [codes]} -> (all, sorted codes). Unknown/inactive codes are refused."""
    if not isinstance(spec, dict):
        raise bad("Choose the audience.", "audience")
    if spec.get("all") is True:
        return True, []
    codes = spec.get("departments")
    if not isinstance(codes, list) or not codes or not all(isinstance(c, str) for c in codes):
        raise bad("Choose all departments or at least one department.", "audience")
    codes = sorted(set(codes))
    found = set(Department.objects.filter(code__in=codes, active=True).values_list("code", flat=True))
    missing = [c for c in codes if c not in found]
    if missing:
        raise bad(f"Unknown or inactive department(s): {', '.join(missing)}.", "audience")
    return False, codes


def resolve(a):
    """The departments a draft/announcement audience spec means right now (all = the active departments now)."""
    qs = Department.objects.filter(active=True)
    if not a.audience_all:
        qs = qs.filter(code__in=a.audience_codes)
    return list(qs.order_by("code"))


def _version(a, expected):
    if not isinstance(expected, int) or expected != a.edit_version:
        raise ApiError(409, "version_conflict", "This announcement changed in another tab. Reload to see the latest version.",
                       extra={"current": announcement_json(a, for_vc=True)})


def _lock(pk):
    try:
        return Announcement.objects.select_for_update().get(pk=pk)
    except (Announcement.DoesNotExist, ValueError):
        raise ApiError(404, "not_found", "Not found.")


def _revision(a, kind, user, at):
    a.revision += 1
    AnnouncementRevision.objects.create(
        announcement=a, number=a.revision, kind=kind, content_version=a.content_version, title=a.title, body=a.body,
        pinned=a.pinned, expires_at=a.expires_at, created_by=user, created_at=at,
        audience=sorted(a.recipients.values_list("department__code", flat=True)))


def _sync_recipients(a, departments, at):
    """Keep members (and their added_at), remove dropped ones, add new ones as unread."""
    want = {d.id: d for d in departments}
    have = set(a.recipients.values_list("department_id", flat=True))
    a.recipients.exclude(department_id__in=list(want)).delete()
    AnnouncementRecipient.objects.bulk_create([AnnouncementRecipient(announcement=a, department=d, added_at=at)
                                               for i, d in want.items() if i not in have])
    return sorted(d.code for i, d in want.items() if i not in have), len(have - set(want))


# ---------- VC actions ----------

def create(user, data, request=None, pending_scope=None):
    at = timezone.now()
    title, body = clean_text(data.get("title"), data.get("body"))
    every, codes = clean_audience(data.get("audience"))
    a = Announcement.objects.create(title=title, body=body, pinned=data.get("pinned") is True,
                                    expires_at=clean_expiry(data.get("expires_at"), at), audience_all=every,
                                    audience_codes=codes, pending_scope=pending_scope, created_by=user,
                                    created_at=at, updated_at=at)
    record(user, "announcement.create", a, {"pending_shortcut": bool(pending_scope)}, request)
    return a


def update(user, pk, data, request=None):
    with transaction.atomic():
        a = _lock(pk)
        _version(a, data.get("edit_version"))
        if a.state == State.WITHDRAWN:
            raise ApiError(409, "withdrawn", "A withdrawn announcement cannot be changed.")
        at = timezone.now()
        title, body = clean_text(data.get("title", a.title), data.get("body", a.body))
        content_changed = (title, body) != (a.title, a.body)
        a.title, a.body = title, body
        if "pinned" in data:
            a.pinned = data["pinned"] is True
        if "expires_at" in data:
            a.expires_at = clean_expiry(data["expires_at"], at)
        audience_changed = False
        if "audience" in data:
            every, codes = clean_audience(data["audience"])
            audience_changed = (every, codes) != (a.audience_all, sorted(a.audience_codes))
            a.audience_all, a.audience_codes = every, codes
        summary = {"content_changed": content_changed, "audience_changed": audience_changed}
        if a.state == State.PUBLISHED:
            if audience_changed:
                departments = resolve(a)
                if not departments:
                    raise bad("The audience has no active department.", "audience")
                summary["added"], summary["removed"] = _sync_recipients(a, departments, at)
            if content_changed:
                a.content_version += 1  # every current recipient sees it as unread again
                a.content_updated_at = at
            _revision(a, "content" if content_changed else "metadata", user, at)
        a.edit_version += 1
        a.updated_at = at
        a.save()
        record(user, "announcement.update", a, summary, request)
        return a


def delete_draft(user, pk, data, request=None):
    with transaction.atomic():
        a = _lock(pk)
        _version(a, data.get("edit_version"))
        if a.state != State.DRAFT:
            raise ApiError(409, "not_draft", "Published announcements keep their history; withdraw instead.")
        record(user, "announcement.delete_draft", a, {"title": a.title}, request)
        a.delete()


def publish(user, pk, data, request=None, eligible=None):
    """`eligible` = freshly recomputed pending departments for a shortcut draft (computed by the caller outside this
    transaction, because the analytics snapshot must own its own transaction)."""
    with transaction.atomic():
        a = _lock(pk)
        _version(a, data.get("edit_version"))
        if a.state != State.DRAFT:
            raise ApiError(409, "not_draft", "Already published.")
        at = timezone.now()
        if a.expires_at and a.expires_at <= at:
            raise bad("The expiry has passed; choose a later one.", "expires_at")
        departments = resolve(a)
        if not departments:
            raise bad("The audience has no active department.", "audience")
        if eligible is not None:
            chosen = sorted(d.code for d in departments)
            if sorted(eligible) != chosen and data.get("acknowledge_eligibility") is not True:
                raise ApiError(409, "eligibility_changed",
                               "The departments with pending reports changed since this draft was prepared. Review the "
                               "recipients; nothing was published.",
                               extra={"eligible": sorted(eligible), "audience": chosen,
                                      "newly_pending": sorted(set(eligible) - set(chosen)),
                                      "no_longer_pending": sorted(set(chosen) - set(eligible))})
        _sync_recipients(a, departments, at)
        a.state, a.content_version, a.published_at, a.content_updated_at = State.PUBLISHED, 1, at, at
        _revision(a, "publish", user, at)
        a.edit_version += 1
        a.updated_at = at
        a.save()
        record(user, "announcement.publish", a, {"recipients": [d.code for d in departments]}, request)
        return a


def withdraw(user, pk, data, request=None):
    with transaction.atomic():
        a = _lock(pk)
        _version(a, data.get("edit_version"))
        if a.state != State.PUBLISHED:
            raise ApiError(409, "not_published", "Only a published announcement can be withdrawn.")
        at = timezone.now()
        a.state, a.withdrawn_at = State.WITHDRAWN, at
        _revision(a, "withdraw", user, at)
        a.edit_version += 1
        a.updated_at = at
        a.save()
        record(user, "announcement.withdraw", a, None, request)
        return a


# ---------- Dean side ----------

def visible_to(user, at=None):
    """Active announcements whose current audience includes the user's department (derived from the session user)."""
    at = at or timezone.now()
    return Announcement.objects.filter(
        state=State.PUBLISHED, recipients__department_id=user.department_id).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=at))


def with_unread(qs, user):
    """is_read = a receipt for the current content version made since this department's membership began."""
    since = AnnouncementRecipient.objects.filter(announcement=OuterRef(OuterRef("pk")), department_id=user.department_id)
    return qs.annotate(is_read=Exists(AnnouncementRead.objects.filter(
        announcement=OuterRef("pk"), user=user, content_version=OuterRef("content_version"),
        read_at__gte=Subquery(since.values("added_at")[:1]))))


def get_for_dean(user, pk):
    try:
        return with_unread(visible_to(user), user).get(pk=pk)
    except (Announcement.DoesNotExist, ValueError):
        raise ApiError(404, "not_found", "Not found.")  # not a recipient, expired, withdrawn or draft: indistinguishable


def unread_count(user):
    return with_unread(visible_to(user), user).filter(is_read=False).count()


def mark_read(user, pk, content_version):
    with transaction.atomic():
        a = get_for_dean(user, pk)  # access is re-checked on every read request
        Announcement.objects.select_for_update().get(pk=a.pk)
        a.refresh_from_db()
        if content_version != a.content_version:
            raise ApiError(409, "stale_read", "This announcement was updated while you were reading it. The new version is shown.",
                           extra={"content_version": a.content_version})
        AnnouncementRead.objects.update_or_create(announcement=a, user=user, content_version=a.content_version,
                                                  defaults={"read_at": timezone.now()})
    return get_for_dean(user, pk)


# ---------- pending departments (Analytics shortcut) ----------

def pending_departments(year, period_ids, departments, kras, at=None):
    """Departments with at least one applicable, opened slot in the chosen periods that is Not submitted, Draft,
    Rejected or Returned for correction (Awaiting review, Approved, Not due and unassigned slots never count)."""
    from apps.submissions import analytics

    at = at or timezone.now()
    periods = {p.id: p for p in year.periods.filter(id__in=period_ids)}
    if not period_ids or len(periods) != len(set(period_ids)):
        raise bad(f"Choose reporting periods of {year.label}.", "periods")
    unopened = [p.label for p in periods.values() if p.opens_at > at]
    if unopened:
        raise bad(f"These periods have not opened yet: {', '.join(unopened)}.", "periods")
    f = {"year": year, "scope": "year", "period": None, "departments": departments, "kras": kras, "status": "", "page": 1, "page_size": 50}
    d = analytics.dataset(f, at)
    idx = {p.index for p in periods.values()}
    counts = {}
    for r in d["details"]:
        if r["period_index"] in idx and r["status"] in PENDING_BUCKETS:
            counts[r["department"]] = counts.get(r["department"], 0) + 1
    labels = [p.label for p in sorted(periods.values(), key=lambda p: p.index)]
    return sorted(counts), counts, labels


def suggested_message(year, labels, kras):
    scope = f"KRA {', '.join(str(k) for k in kras)}" if kras else "your assigned KRAs"
    return (f"Reports pending for {year.label}",
            f"Our records show at least one report for {scope} in {'; '.join(labels)} that is not yet submitted, or was "
            "rejected or returned for correction.\n\nPlease review your KRA dashboard. This notice does not "
            "reopen a closed reporting window or change any deadline; use the usual reopening request where needed.")


# ---------- serialisation ----------

def announcement_json(a, for_vc=False, at=None):
    at = at or timezone.now()
    expired = bool(a.expires_at and a.expires_at <= at)
    out = {"id": str(a.id), "title": a.title, "body": a.body, "pinned": a.pinned, "expires_at": a.expires_at,
           "published_at": a.published_at, "content_updated_at": a.content_updated_at, "content_version": a.content_version,
           "updated": a.content_version > 1}
    if for_vc:
        out.update({"state": a.state, "expired": expired, "edit_version": a.edit_version, "revision": a.revision,
                    "audience": {"all": a.audience_all, "departments": a.audience_codes},
                    "recipients": sorted(a.recipients.values_list("department__code", flat=True)) if a.state != State.DRAFT else [],
                    "pending_scope": a.pending_scope, "created_at": a.created_at, "updated_at": a.updated_at,
                    "withdrawn_at": a.withdrawn_at,
                    "read_count": a.reads.filter(content_version=a.content_version).count() if a.state != State.DRAFT else 0})
    else:
        out["read"] = bool(getattr(a, "is_read", False))
    return out


def ordered(qs):
    """Pinned first, then by latest publication/content update."""
    return qs.order_by("-pinned", "-content_updated_at", "-published_at")
