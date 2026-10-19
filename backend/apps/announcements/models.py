"""In-portal announcements (VC plan v2.3 §10, D-077).

Read state = a receipt for the announcement's *current content version* made after the reader's department joined the
current audience. So: a content edit (new version) makes it unread; audience/expiry/pin edits keep `content_version`
and existing members' `added_at`, so read state survives; a newly added or re-added department has a fresh `added_at`
and starts unread. Each announcement counts once, whatever its revision count.
"""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Announcement(models.Model):
    class State(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.CharField(max_length=9, choices=State.choices, default=State.DRAFT)
    title = models.CharField(max_length=200)
    body = models.TextField()
    pinned = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    audience_all = models.BooleanField(default=False)  # draft audience spec; resolved to recipients at publication
    audience_codes = models.JSONField(default=list)
    pending_scope = models.JSONField(null=True, blank=True)  # set by "Announce to pending departments"
    content_version = models.PositiveIntegerField(default=0)  # 0 = never published
    revision = models.PositiveIntegerField(default=0)
    edit_version = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    published_at = models.DateTimeField(null=True, blank=True)
    content_updated_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["state", "expires_at"], name="announcement_state_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(state="DRAFT") | Q(content_version__gte=1, published_at__isnull=False),
                                   name="announcement_published_has_version"),
            models.CheckConstraint(condition=~Q(state="WITHDRAWN") | Q(withdrawn_at__isnull=False), name="announcement_withdrawn_at"),
        ]


class AnnouncementRevision(models.Model):
    """Immutable history of every publication, edit and withdrawal (VC-only audience kept here)."""

    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=10)  # publish / content / metadata / withdraw
    content_version = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    body = models.TextField()
    pinned = models.BooleanField()
    expires_at = models.DateTimeField(null=True, blank=True)
    audience = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["announcement", "number"], name="unique_announcement_revision")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Announcement revisions are immutable")
        super().save(*args, **kwargs)


class AnnouncementRecipient(models.Model):
    """Current audience membership; `added_at` starts this membership (re-adding gives a new one)."""

    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="recipients")
    department = models.ForeignKey("catalogue.Department", on_delete=models.PROTECT, related_name="+")
    added_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["announcement", "department"], name="unique_announcement_recipient")]
        indexes = [models.Index(fields=["department", "announcement"], name="recipient_dept_idx")]


class AnnouncementRead(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    content_version = models.PositiveIntegerField()
    read_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["announcement", "user", "content_version"], name="one_read_per_version")]
        indexes = [models.Index(fields=["user", "announcement"], name="read_user_idx")]
