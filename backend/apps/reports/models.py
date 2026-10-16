import uuid

from django.db import models


class GeneratedDocument(models.Model):
    """Cached/historical report PDF keyed by content hash (plan 8.13)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey("submissions.Submission", on_delete=models.PROTECT, related_name="documents")
    revision = models.ForeignKey("submissions.SubmissionRevision", null=True, on_delete=models.PROTECT,
                                 related_name="documents")
    content_hash = models.CharField(max_length=64, unique=True)
    status_snapshot = models.CharField(max_length=20)
    verification_label = models.CharField(max_length=250)
    renderer_version = models.CharField(max_length=40)
    storage_key = models.CharField(max_length=80)
    bytes = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
