"""Announcements API (D-077). One set of routes; the role and department come from the session user, never the client."""
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsDean, IsDeanOrVC, IsVC
from apps.audit.errors import ApiError
from apps.catalogue.models import AcademicYear, Department

from . import services as svc
from .models import Announcement, AnnouncementRevision

State = Announcement.State


def vc_get(pk):
    try:
        return Announcement.objects.get(pk=pk)
    except (Announcement.DoesNotExist, ValueError):
        raise ApiError(404, "not_found", "Not found.")


def page(request, qs, fn):
    try:
        n = max(int(request.query_params.get("page", 1) or 1), 1)
    except ValueError:
        raise ApiError(400, "invalid", "Page must be a number.")
    size = 20
    total = qs.count()
    return {"total": total, "page": n, "page_size": size, "results": [fn(a) for a in qs[(n - 1) * size:n * size]]}


class AnnouncementsView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request):
        at = timezone.now()
        if request.user.role == "VC":
            qs = Announcement.objects.all()
            state = request.query_params.get("state")
            if state == "ACTIVE":
                qs = qs.filter(state=State.PUBLISHED).exclude(expires_at__lte=at)
            elif state == "EXPIRED":
                qs = qs.filter(state=State.PUBLISHED, expires_at__lte=at)
            elif state in State.values:
                qs = qs.filter(state=state)
            elif state:
                raise ApiError(400, "invalid", "Unknown state.")
            return Response(page(request, qs.order_by("-updated_at"), lambda a: svc.announcement_json(a, True, at)))
        qs = svc.ordered(svc.with_unread(svc.visible_to(request.user, at), request.user))
        if request.query_params.get("unread") == "1":
            qs = qs.filter(is_read=False)
        data = page(request, qs, lambda a: svc.announcement_json(a, False, at))
        return Response({**data, "unread_count": svc.unread_count(request.user)})

    def post(self, request):
        if request.user.role != "VC":
            raise ApiError(403, "forbidden", "Only the Vice Chancellor can write announcements.")
        return Response(svc.announcement_json(svc.create(request.user, request.data, request), True), status=201)


class AnnouncementView(APIView):
    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        if request.user.role == "VC":
            return Response(svc.announcement_json(vc_get(pk), True))
        return Response(svc.announcement_json(svc.get_for_dean(request.user, pk)))  # loading never marks it read

    def patch(self, request, pk):
        if request.user.role != "VC":
            raise ApiError(403, "forbidden", "Only the Vice Chancellor can edit announcements.")
        return Response(svc.announcement_json(svc.update(request.user, pk, request.data, request), True))

    def delete(self, request, pk):
        if request.user.role != "VC":
            raise ApiError(403, "forbidden", "Only the Vice Chancellor can delete drafts.")
        svc.delete_draft(request.user, pk, request.data, request)
        return Response(status=204)


class PublishView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        a = vc_get(pk)
        eligible = None
        if a.pending_scope and a.state == State.DRAFT:  # revalidate the shortcut's recipients before publication
            s = a.pending_scope
            year = AcademicYear.objects.get(label=s["year"])
            eligible, _, _ = svc.pending_departments(year, s["period_ids"], s.get("departments", []), s.get("kras", []))
        return Response(svc.announcement_json(svc.publish(request.user, pk, request.data, request, eligible), True))


class WithdrawView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        return Response(svc.announcement_json(svc.withdraw(request.user, pk, request.data, request), True))


class ReadView(APIView):
    permission_classes = [IsDean]

    def post(self, request, pk):
        version = request.data.get("content_version")
        if not isinstance(version, int):
            raise ApiError(400, "invalid", "content_version is required.", {"content_version": ["Required."]})
        a = svc.mark_read(request.user, pk, version)
        return Response({**svc.announcement_json(a), "unread_count": svc.unread_count(request.user)})


class UnreadCountView(APIView):
    permission_classes = [IsDean]

    def get(self, request):
        return Response({"unread_count": svc.unread_count(request.user)})


class RevisionsView(APIView):
    """History. VC: every revision with its audience. Dean: content revisions only, and only while the announcement is
    currently addressed to the Dean's department (a removed department loses old revisions too)."""

    permission_classes = [IsDeanOrVC]

    def get(self, request, pk):
        vc = request.user.role == "VC"
        a = vc_get(pk) if vc else svc.get_for_dean(request.user, pk)
        revs = AnnouncementRevision.objects.filter(announcement=a).select_related("created_by")
        if not vc:
            revs = revs.filter(kind__in=["publish", "content"])
        return Response({"results": [
            {"number": r.number, "kind": r.kind, "content_version": r.content_version, "title": r.title, "body": r.body,
             "created_at": r.created_at, **({"pinned": r.pinned, "expires_at": r.expires_at, "audience": r.audience,
                                            "by": r.created_by.display_name} if vc else {})} for r in revs]})


class RecipientsPreviewView(APIView):
    permission_classes = [IsVC]

    def post(self, request):
        every, codes = svc.clean_audience(request.data.get("audience"))
        qs = Department.objects.filter(active=True)
        if not every:
            qs = qs.filter(code__in=codes)
        return Response({"departments": [{"code": d.code, "name": d.name} for d in qs.order_by("code")]})


class PendingDraftView(APIView):
    """"Announce to pending departments": computes recipients and a factual message, then saves an editable DRAFT.
    Nothing is published, and no reporting window is reopened."""

    permission_classes = [IsVC]

    def post(self, request):
        d = request.data
        year = AcademicYear.objects.filter(label=str(d.get("year", ""))).first()
        if year is None:
            raise svc.bad("Choose a valid academic year.", "year")
        ids = d.get("period_ids")
        if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids):
            raise svc.bad("Choose the reporting periods this notice concerns.", "periods")
        depts = [c for c in (d.get("departments") or []) if isinstance(c, str)]
        try:
            kras = sorted({int(k) for k in (d.get("kras") or [])})
        except (TypeError, ValueError):
            raise svc.bad("KRA must be a number.", "kras")
        eligible, counts, labels = svc.pending_departments(year, sorted(set(ids)), depts, kras)
        if not eligible:
            raise ApiError(409, "nothing_pending", "No department has a pending report in these periods.")
        title, body = svc.suggested_message(year, labels, kras)
        if d.get("preview") is True:
            return Response({"eligible": eligible, "counts": counts, "periods": labels, "title": title, "body": body})
        scope = {"year": year.label, "period_ids": sorted(set(ids)), "periods": labels, "departments": depts, "kras": kras}
        a = svc.create(request.user, {"title": title, "body": body, "audience": {"departments": eligible}}, request,
                       pending_scope=scope)
        return Response({**svc.announcement_json(a, True), "counts": counts}, status=201)
