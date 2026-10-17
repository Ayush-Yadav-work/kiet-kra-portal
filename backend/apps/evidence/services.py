"""Evidence rules (plan 3.2, C3, C5, C6). Evidence changes never touch Submission.edit_version."""
import hashlib
import re
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.errors import ApiError
from apps.audit.models import record
from apps.submissions import services as sub_services
from apps.submissions.models import Submission

from .models import Evidence
from .storage import read_path, write_upload

SIGNATURES = ((b"%PDF-", "application/pdf", "pdf"), (b"\xff\xd8\xff", "image/jpeg", "jpg"),
              (b"\x89PNG\r\n\x1a\n", "image/png", "png"))
DRIVE_HOSTS = {"drive.google.com", "docs.google.com"}


def _lock_editable(submission_id):
    sub = Submission.objects.select_for_update(of=("self",)).select_related(
        "period", "assignment__template_version").get(pk=submission_id)
    if not sub_services.is_editable(sub):
        raise ApiError(409, "not_editable", "Evidence can only be changed while the report is editable.")
    return sub


def _meta(sub, category, label, description):
    categories = sub.assignment.template_version.schema.get("evidence", {}).get("categories", [])
    errors = {}
    if category not in categories:
        errors["category"] = ["Choose a listed category."]
    label = (label or "").strip()
    if not label or len(label) > 200:
        errors["label"] = ["Enter a label (max 200 characters)."]
    if len(description or "") > 1000:
        errors["description"] = ["Max 1000 characters."]
    if errors:
        raise ApiError(400, "invalid", "Check the evidence details.", errors)
    return category, label, (description or "").strip()


def safe_filename(name):
    name = re.sub(r"[^\w.\- ()]+", "_", (name or "file").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip(" .")
    return name[:200] or "file"


def add_file(user, submission_id, uploaded, category, label, description="", request=None):
    if uploaded is None:
        raise ApiError(400, "invalid", "Choose a file.", {"file": ["Required."]})
    if uploaded.size > settings.EVIDENCE_MAX_FILE_BYTES:
        raise ApiError(413, "too_large", f"Files must be at most {settings.EVIDENCE_MAX_FILE_BYTES // 2**20} MB.")
    head = uploaded.read(16)
    uploaded.seek(0)
    kind = next((s for s in SIGNATURES if head.startswith(s[0])), None)
    if kind is None:
        raise ApiError(400, "invalid_type", "Only PDF, JPEG and PNG files are accepted.", {"file": ["Unsupported type."]})
    with transaction.atomic():
        sub = _lock_editable(submission_id)
        category, label, description = _meta(sub, category, label, description)
        active, history = sub_services.evidence_totals(sub)
        if active + uploaded.size > settings.EVIDENCE_MAX_ACTIVE_BYTES:
            raise ApiError(413, "quota_active", "This report's active evidence would exceed "
                           f"{settings.EVIDENCE_MAX_ACTIVE_BYTES // 2**20} MB. Remove files or use Drive links.")
        if history + uploaded.size > settings.EVIDENCE_MAX_HISTORY_BYTES:
            raise ApiError(413, "quota_history", "This report has reached its total upload history limit "
                           f"({settings.EVIDENCE_MAX_HISTORY_BYTES // 2**20} MB). Use Drive links.")
        key = f"evidence/{uuid.uuid4().hex}.{kind[2]}"
        path = write_upload(key, uploaded)
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            ev = Evidence.objects.create(
                submission=sub, source_type=Evidence.Source.FILE, category=category, label=label,
                description=description, storage_key=key, original_filename=safe_filename(uploaded.name),
                mime=kind[1], bytes=uploaded.size, checksum=digest, uploaded_by=user)
            record(user, "evidence_added", sub, {"evidence": str(ev.id), "type": "FILE", "bytes": ev.bytes}, request)
        except BaseException:  # the row rolls back with the transaction; remove the file it would have referenced
            path.unlink(missing_ok=True)
            raise
        return ev


def add_link(user, submission_id, url, category, label, description="", request=None):
    url = (url or "").strip()
    parsed = urlparse(url)
    if len(url) > 1000 or parsed.scheme != "https" or parsed.hostname not in DRIVE_HOSTS or parsed.username:
        raise ApiError(400, "invalid", "Enter an https://drive.google.com or https://docs.google.com link.",
                       {"drive_url": ["Not a Google Drive link."]})
    with transaction.atomic():
        sub = _lock_editable(submission_id)
        category, label, description = _meta(sub, category, label, description)
        ev = Evidence.objects.create(submission=sub, source_type=Evidence.Source.DRIVE_LINK, category=category,
                                     label=label, description=description, drive_url=url, uploaded_by=user)
        record(user, "evidence_added", sub, {"evidence": str(ev.id), "type": "DRIVE_LINK"}, request)
        return ev


def remove(user, evidence, request=None):
    """Soft removal: files stay on disk because submitted revisions may reference them (plan 7)."""
    with transaction.atomic():
        sub = _lock_editable(evidence.submission_id)
        ev = Evidence.objects.select_for_update().get(pk=evidence.pk)
        if ev.removed:
            return ev
        ev.removed, ev.removed_at = True, timezone.now()
        ev.save(update_fields=["removed", "removed_at"])
        record(user, "evidence_removed", sub, {"evidence": str(ev.id)}, request)
        return ev


def file_path(ev):
    return read_path(ev.storage_key)
