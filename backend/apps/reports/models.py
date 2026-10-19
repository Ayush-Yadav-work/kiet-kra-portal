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


class ApprovalArtifact(models.Model):
    """Durable job + retained file for one approval decision (VC plan v2.3 §9.1, D-076). Everything needed to render is
    frozen here or in the immutable revision, so a later return, approval or account rename never changes this artifact."""

    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        READY = "READY", "Ready"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    decision = models.OneToOneField("submissions.ReviewDecision", on_delete=models.PROTECT, related_name="artifact")
    submission = models.ForeignKey("submissions.Submission", on_delete=models.PROTECT, related_name="+")
    revision = models.ForeignKey("submissions.SubmissionRevision", on_delete=models.PROTECT, related_name="artifacts")
    reviewer_name = models.CharField(max_length=200)  # snapshot from the decision
    verified_at = models.DateTimeField()
    template_key = models.CharField(max_length=60)
    template_version = models.PositiveIntegerField()
    renderer_version = models.CharField(max_length=40)
    state = models.CharField(max_length=8, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    lease_owner = models.CharField(max_length=120, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)
    storage_key = models.CharField(max_length=80, blank=True)
    content_hash = models.CharField(max_length=64, blank=True)
    bytes = models.BigIntegerField(null=True, blank=True)
    legacy_document = models.ForeignKey(GeneratedDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state", "next_attempt_at"], name="artifact_queue_idx"),
                   models.Index(fields=["state", "lease_expires_at"], name="artifact_lease_idx")]
        constraints = [
            models.CheckConstraint(condition=~models.Q(state="READY") | (~models.Q(storage_key="") & models.Q(bytes__isnull=False)),
                                   name="artifact_ready_has_file"),
            models.CheckConstraint(condition=~models.Q(state="RUNNING") | (~models.Q(lease_owner="") & models.Q(lease_expires_at__isnull=False)),
                                   name="artifact_running_has_lease"),
        ]


class WorkerHeartbeat(models.Model):
    """Last sign of life per worker process; operators and `/health/` read it (D-076)."""

    name = models.CharField(max_length=120, primary_key=True)
    host = models.CharField(max_length=120)
    pid = models.PositiveIntegerField()
    started_at = models.DateTimeField()
    beat_at = models.DateTimeField()
    stopped_at = models.DateTimeField(null=True, blank=True)
    current_job = models.UUIDField(null=True, blank=True)
    processed = models.PositiveIntegerField(default=0)
