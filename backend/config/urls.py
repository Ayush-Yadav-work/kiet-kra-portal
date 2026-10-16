from django.http import JsonResponse
from django.urls import include, path

from apps.accounts import views as auth
from apps.catalogue import views as cat
from apps.evidence import views as ev
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
]


def health(request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("api/v1/", include(api)),
    path("health/", health),
]
