import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Status(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SUBMITTED = "SUBMITTED", "Submitted"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey("catalogue.AnnualAssignment", on_delete=models.PROTECT, related_name="submissions")
    period = models.ForeignKey("catalogue.ReportingPeriod", on_delete=models.PROTECT, related_name="submissions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    is_nil = models.BooleanField(default=False)
    nil_reason = models.TextField(blank=True)
    achievement_text = models.CharField(max_length=500, blank=True)
    remarks = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    edit_version = models.PositiveIntegerField(default=0)
    current_revision = models.ForeignKey("SubmissionRevision", null=True, blank=True, on_delete=models.PROTECT,
                                         related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "period"], name="one_submission_per_period")]


class SubmissionRevision(models.Model):
    """Immutable snapshot created at submit time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="revisions")
    sequence = models.PositiveIntegerField()
    payload = models.JSONField()
    is_nil = models.BooleanField()
    nil_reason = models.TextField(blank=True)
    achievement_text = models.CharField(max_length=500, blank=True)
    remarks = models.TextField(blank=True)
    snapshot = models.JSONField()  # department, KRA text/refs, target, period, year, template key/version
    evidence_manifest = models.JSONField()
    manifest_hash = models.CharField(max_length=64)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField()

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["submission", "sequence"], name="unique_revision_sequence")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Submission revisions are immutable")
        super().save(*args, **kwargs)


class ReviewDecision(models.Model):
    class Decision(models.TextChoices):
        APPROVE = "APPROVE", "Approved"
        REJECT = "REJECT", "Rejected"
        RETURN = "RETURN", "Returned for correction"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(SubmissionRevision, on_delete=models.PROTECT, related_name="decisions")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reviewer_name = models.CharField(max_length=200)  # snapshot
    decision = models.CharField(max_length=8, choices=Decision.choices)
    reason = models.TextField(blank=True)
    granted_reopen = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["created_at"]
        constraints = [models.CheckConstraint(condition=Q(decision="APPROVE") | ~Q(reason=""),
                                              name="reject_return_need_reason")]


class ReopenRequest(models.Model):
    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DENIED = "DENIED", "Denied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="reopen_requests")
    reason = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField()
    state = models.CharField(max_length=8, choices=State.choices, default=State.PENDING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True)
    decision_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [models.UniqueConstraint(fields=["submission"], condition=Q(state="PENDING"),
                                               name="one_pending_reopen_request")]


class ReopenGrant(models.Model):
    class Source(models.TextChoices):
        REQUEST = "REQUEST", "Reopen request"
        REVIEW = "REVIEW", "Review decision"
        PUBLICATION = "PUBLICATION", "Assignment publication"  # late publication with a 72-hour window (D-073)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="grants")
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    source = models.CharField(max_length=12, choices=Source.choices)
    request = models.OneToOneField(ReopenRequest, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="grant")
    review_decision = models.OneToOneField(ReviewDecision, null=True, blank=True, on_delete=models.PROTECT,
                                           related_name="grant")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(  # exactly one source; a publication grant references neither a request nor a decision
                condition=(Q(source="REQUEST", request__isnull=False, review_decision__isnull=True)
                           | Q(source="REVIEW", request__isnull=True, review_decision__isnull=False)
                           | Q(source="PUBLICATION", request__isnull=True, review_decision__isnull=True)),
                name="grant_source_three_way",
            ),
            models.UniqueConstraint(fields=["submission"], condition=Q(source="PUBLICATION"), name="one_publication_grant_per_submission"),
            models.CheckConstraint(condition=Q(starts_at__lt=models.F("expires_at")), name="grant_window_valid"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Reopen grants are immutable history")
        super().save(*args, **kwargs)


class BulkApproval(models.Model):
    """Server-owned manifest of exact (submission, submitted revision) pairs frozen at selection (D-075). Confirmed once;
    then processed in requests of at most BULK_BATCH_SIZE items until every item has an outcome."""

    class Scope(models.TextChoices):
        SELECTION = "SELECTION", "Selected reports"
        FILTERED = "FILTERED", "All eligible reports matching filters"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    idempotency_key = models.CharField(max_length=64)
    scope = models.CharField(max_length=9, choices=Scope.choices)
    filters = models.JSONField(default=dict)  # descriptive scope (year/period/department/KRA/search) shown to the VC
    total = models.PositiveIntegerField()
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()  # confirmation deadline
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    retry_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor", "idempotency_key"], name="one_manifest_per_key")]
        indexes = [models.Index(fields=["actor", "completed_at", "created_at"], name="bulk_actor_idx")]


class BulkApprovalItem(models.Model):
    class Outcome(models.TextChoices):
        PENDING = "", "Not processed"
        APPROVED = "APPROVED", "Approved"
        SKIPPED = "SKIPPED", "Skipped"
        CONFLICT = "CONFLICT", "Conflict"
        FAILED = "FAILED", "Failed"

    bulk = models.ForeignKey(BulkApproval, on_delete=models.PROTECT, related_name="items")
    position = models.PositiveIntegerField()
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name="+")
    revision = models.ForeignKey(SubmissionRevision, on_delete=models.PROTECT, related_name="+")
    outcome = models.CharField(max_length=8, choices=Outcome.choices, blank=True, default="")
    reason = models.CharField(max_length=300, blank=True)
    decision = models.OneToOneField(ReviewDecision, null=True, blank=True, on_delete=models.PROTECT, related_name="bulk_item")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["bulk", "submission"], name="bulk_item_unique_submission"),
            models.UniqueConstraint(fields=["bulk", "position"], name="bulk_item_unique_position"),
            models.CheckConstraint(condition=~Q(outcome="APPROVED") | Q(decision__isnull=False), name="bulk_approved_has_decision"),
        ]
        indexes = [models.Index(fields=["bulk", "outcome", "position"], name="bulk_item_queue_idx")]
