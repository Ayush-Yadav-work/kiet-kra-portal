"""Object scoping. Role checks happen first (permission classes); these narrow to the user's department.
Out-of-scope objects raise 404 so their existence is not confirmed (D-021)."""
from django.core.exceptions import ValidationError
from django.http import Http404

from apps.catalogue.models import AnnualAssignment

from .models import ReopenRequest, Submission

SUB_RELATED = ("assignment__department", "assignment__kra", "assignment__year", "assignment__template_version",
               "assignment__effective_start_period", "period", "current_revision")


def assignments_for(user):
    qs = AnnualAssignment.objects.select_related("department", "kra", "year", "template_version", "effective_start_period")
    if user.role == "VC":
        return qs
    return qs.filter(department_id=user.department_id)


def submissions_for(user):
    qs = Submission.objects.select_related(*SUB_RELATED)
    if user.role == "VC":
        return qs
    return qs.filter(assignment__department_id=user.department_id)


def reopen_requests_for(user):
    qs = ReopenRequest.objects.select_related("submission__assignment__department", "submission__assignment__kra",
                                              "submission__period", "submission__assignment__year", "requested_by", "decided_by")
    if user.role == "VC":
        return qs
    return qs.filter(submission__assignment__department_id=user.department_id)


def get_or_404(qs, **kw):
    try:
        return qs.get(**kw)
    except (qs.model.DoesNotExist, ValueError, ValidationError):  # malformed UUIDs included
        raise Http404
