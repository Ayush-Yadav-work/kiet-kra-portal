import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Evidence(models.Model):
    class Source(models.TextChoices):
        FILE = "FILE", "Uploaded file"
        DRIVE_LINK = "DRIVE_LINK", "Google Drive link"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey("submissions.Submission", on_delete=models.PROTECT, related_name="evidence")
    source_type = models.CharField(max_length=10, choices=Source.choices)
    category = models.CharField(max_length=100)
    label = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    storage_key = models.CharField(max_length=80, null=True, blank=True)
    drive_url = models.URLField(max_length=1000, null=True, blank=True)
    original_filename = models.CharField(max_length=255, null=True, blank=True)
    mime = models.CharField(max_length=60, null=True, blank=True)
    bytes = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    removed = models.BooleanField(default=False)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["uploaded_at"]
        constraints = [models.CheckConstraint(
            name="evidence_fields_match_source",
            condition=(
                Q(source_type="FILE", storage_key__isnull=False, original_filename__isnull=False, mime__isnull=False,
                  bytes__isnull=False, checksum__isnull=False, drive_url__isnull=True)
                | Q(source_type="DRIVE_LINK", drive_url__isnull=False, storage_key__isnull=True, bytes__isnull=True,
                    checksum__isnull=True)
            ),
        )]
