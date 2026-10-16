"""Django -> internal renderer client and generated-document cache (plan 8.13–8.14, C4)."""
import json
import urllib.error
import urllib.request
import uuid

from django.conf import settings

from apps.audit.errors import ApiError
from apps.evidence.storage import read_path, write_bytes

from .models import GeneratedDocument
from .rendering import build_context, content_hash, pdf_parts


def call_renderer(parts):
    req = urllib.request.Request(f"{settings.RENDERER_URL}/pdf", data=json.dumps(parts).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.RENDERER_TIMEOUT_SECONDS) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 503:
            raise ApiError(503, "pdf_busy", "The PDF service is busy. Your draft is safe — try again in a moment.")
        raise ApiError(502, "pdf_failed", "PDF generation failed. Your draft is safe — try again.")
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        raise ApiError(503, "pdf_unavailable", "The PDF service is unavailable. Your draft is safe — try again later.")


def export_pdf(submission, revision=None):
    """Return (GeneratedDocument, path). Reuses an identical earlier render; never deletes history."""
    ctx = build_context(submission, revision)
    parts = pdf_parts(ctx)
    digest = content_hash(parts)
    doc = GeneratedDocument.objects.filter(content_hash=digest).first()
    if doc is None:
        data = call_renderer(parts)
        key = f"generated/{uuid.uuid4().hex}.pdf"
        write_bytes(key, data)
        doc, _ = GeneratedDocument.objects.get_or_create(content_hash=digest, defaults=dict(
            submission=submission, revision=revision or submission.current_revision,
            status_snapshot=submission.status, verification_label=ctx["verification_label"],
            renderer_version=settings.RENDERER_VERSION, storage_key=key, bytes=len(data)))
    return doc, read_path(doc.storage_key), ctx
