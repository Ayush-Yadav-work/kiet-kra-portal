from django.db import transaction
from django.http import JsonResponse
from django.urls import include, path

from apps.accounts import views as auth
from apps.catalogue import admin_views as adm
from apps.catalogue import views as cat
from apps.evidence import views as ev
from apps.submissions import analytics_views as sub_analytics
from apps.submissions import bulk_views as bulk
from apps.announcements import views as ann
from apps.submissions import views as sub

UUID = "<uuid:pk>"

api = [
    path("auth/csrf/", auth.CsrfView.as_view()),
    path("auth/dean/login/", auth.DeanLoginView.as_view()),
    path("auth/vc/login/", auth.VCLoginView.as_view()),
    path("auth/logout/", auth.LogoutView.as_view()),
    path("auth/me/", auth.MeView.as_view()),
    path("auth/change-password/", auth.ChangePasswordView.as_view()),
    path("years/", cat.YearsView.as_view()),
    path("periods/", cat.PeriodsView.as_view()),
    path("departments/", cat.DepartmentsView.as_view()),
    path("kras/", cat.KRAsView.as_view()),
    path("templates/<str:key>/<int:version>/", cat.TemplateView.as_view()),
    path("assignments/", sub.AssignmentsView.as_view()),
    path("assignments/<uuid:assignment_id>/periods/<int:period_id>/", sub.AssignmentPeriodView.as_view()),
    path("assignments/<uuid:assignment_id>/periods/<int:period_id>/reopen-requests/",
         sub.AssignmentReopenRequestView.as_view()),
    path(f"submissions/{UUID}/", sub.SubmissionDetailView.as_view()),
    path(f"submissions/{UUID}/draft/", sub.DraftView.as_view()),
    path(f"submissions/{UUID}/validate/", sub.ValidateView.as_view()),
    path(f"submissions/{UUID}/preview/", sub.PreviewView.as_view()),
    path(f"submissions/{UUID}/export/", sub.ExportView.as_view()),
    path(f"submissions/{UUID}/submit/", sub.SubmitView.as_view()),
    path(f"submissions/{UUID}/review/", sub.ReviewView.as_view()),
    path(f"submissions/{UUID}/history/", sub.HistoryView.as_view()),
    path(f"submissions/{UUID}/reopen-requests/", sub.SubmissionReopenRequestView.as_view()),
    path(f"submissions/{UUID}/evidence/", ev.SubmissionEvidenceView.as_view()),
    path(f"evidence/{UUID}/", ev.EvidenceItemView.as_view()),
    path(f"evidence/{UUID}/download/", ev.EvidenceDownloadView.as_view()),
    path("reopen-requests/", sub.ReopenRequestsView.as_view()),
    path(f"reopen-requests/{UUID}/decision/", sub.ReopenDecisionView.as_view()),
    path("reopen-grants/active/", sub.ActiveGrantsView.as_view()),
    path("progress/", sub.ProgressView.as_view()),
    path("progress/export/", sub.ProgressExportView.as_view()),
    # VC annual assignments (VC features plan v2.3 Phase 1, D-073; supersedes the Phase 5A whole-year finalize)
    path("admin/templates/", adm.TemplatesView.as_view()),
    path("admin/kras/", adm.AdminKRAsView.as_view()),
    path("admin/years/", adm.AdminYearsView.as_view()),
    path("admin/allocations/", adm.AllocationsView.as_view()),
    path("admin/years/<str:label>/copy/", adm.CopyYearView.as_view()),
    path("admin/years/<str:label>/finalise/preview/", adm.FinalisePreviewView.as_view()),
    path("admin/years/<str:label>/finalise/", adm.FinaliseView.as_view()),
    path("admin/drafts/", adm.DraftsView.as_view()),
    path("admin/drafts/bulk-target/", adm.BulkTargetView.as_view()),
    path("admin/drafts/remove/", adm.RemoveView.as_view()),
    path("admin/drafts/restore/", adm.RestoreView.as_view()),
    path(f"admin/drafts/{UUID}/", adm.DraftItemView.as_view()),
    # VC progress analytics and department comparison (Phase 1): the reader owns its REPEATABLE READ snapshot, so these
    # views must never run inside a request-wide transaction (plan §8.1).
    path("analytics/", transaction.non_atomic_requests(sub_analytics.AnalyticsView.as_view())),
    path("analytics/export/", transaction.non_atomic_requests(sub_analytics.AnalyticsExportView.as_view())),
    # Bulk approval (D-075): one transaction per item inside each request.
    path("bulk-approvals/", bulk.BulkApprovalsView.as_view()),
    path(f"bulk-approvals/{UUID}/", bulk.BulkApprovalView.as_view()),
    path(f"bulk-approvals/{UUID}/confirm/", bulk.BulkConfirmView.as_view()),
    path(f"bulk-approvals/{UUID}/process/", bulk.BulkProcessView.as_view()),
    path(f"bulk-approvals/{UUID}/retry/", bulk.BulkRetryView.as_view()),
    # Announcements (D-077); publish/pending-draft read the analytics snapshot, which must own its transaction.
    path("announcements/", ann.AnnouncementsView.as_view()),
    path("announcements/unread-count/", ann.UnreadCountView.as_view()),
    path("announcements/recipients-preview/", ann.RecipientsPreviewView.as_view()),
    path("announcements/pending-draft/", transaction.non_atomic_requests(ann.PendingDraftView.as_view())),
    path(f"announcements/{UUID}/", ann.AnnouncementView.as_view()),
    path(f"announcements/{UUID}/publish/", transaction.non_atomic_requests(ann.PublishView.as_view())),
    path(f"announcements/{UUID}/withdraw/", ann.WithdrawView.as_view()),
    path(f"announcements/{UUID}/read/", ann.ReadView.as_view()),
    path(f"announcements/{UUID}/revisions/", ann.RevisionsView.as_view()),
]


def health(request):
    return JsonResponse({"ok": True})


def artifact_health(request):
    """Operator signal for the approved-PDF worker: live heartbeat, backlog, failed jobs (counts only)."""
    from apps.reports.artifacts import health as h

    data = h()
    return JsonResponse(data, status=200 if data["ok"] else 503)


urlpatterns = [
    path("api/v1/", include(api)),
    path("health/", health),
    path("health/artifacts/", artifact_health),
]
