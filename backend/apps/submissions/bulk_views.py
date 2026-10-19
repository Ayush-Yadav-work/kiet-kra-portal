"""VC bulk approval API (D-075). Session + CSRF like every other write; VC only; manifests are owned by their creator."""
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth import IsVC
from apps.audit.errors import ApiError

from . import bulk as svc
from .models import BulkApproval


def page_of(request):
    try:
        return max(int(request.query_params.get("page", 1) or 1), 1)
    except ValueError:
        raise ApiError(400, "invalid", "Page must be a number.")


class BulkApprovalsView(APIView):
    permission_classes = [IsVC]

    def get(self, request):
        """The VC's own unfinished confirmed runs (for Resume) and recent runs."""
        rows = BulkApproval.objects.filter(actor=request.user).order_by("-created_at")[:20]
        return Response({"results": [svc.summary(b) for b in rows]})

    def post(self, request):
        bulk, excluded = svc.prepare(request.user, request.data, request)
        return Response({**svc.summary(bulk), "excluded": excluded, "items": svc.items_page(bulk)}, status=201)


class BulkApprovalView(APIView):
    permission_classes = [IsVC]

    def get(self, request, pk):
        bulk = svc.owned(request.user, pk)
        outcome = request.query_params.get("outcome") or None
        if outcome and outcome not in ("PENDING", "APPROVED", "SKIPPED", "CONFLICT", "FAILED"):
            raise ApiError(400, "invalid", "Unknown outcome.")
        return Response({**svc.summary(bulk), "items": svc.items_page(bulk, outcome, page_of(request))})


class BulkConfirmView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        return Response(svc.summary(svc.confirm(request.user, pk, request)))


class BulkProcessView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        return Response(svc.process_next(request.user, pk, request))


class BulkRetryView(APIView):
    permission_classes = [IsVC]

    def post(self, request, pk):
        bulk, excluded = svc.retry(request.user, pk, request.data.get("idempotency_key"), request)
        return Response({**svc.summary(bulk), "excluded": excluded, "items": svc.items_page(bulk)}, status=201)
