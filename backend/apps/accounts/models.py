import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    class Role(models.TextChoices):
        VC = "VC", "Vice Chancellor"
        DEAN = "DEAN", "Dean"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    role = models.CharField(max_length=8, choices=Role.choices)
    department = models.ForeignKey("catalogue.Department", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="users")
    must_change_password = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role"], condition=Q(role="VC", is_active=True), name="one_active_vc"),
            models.UniqueConstraint(fields=["department"], condition=Q(role="DEAN", is_active=True),
                                    name="one_active_dean_per_department"),
            models.CheckConstraint(
                condition=Q(role="DEAN", department__isnull=False) | Q(role="VC", department__isnull=True),
                name="dean_has_department_vc_has_none",
            ),
        ]

    @property
    def display_name(self):
        return self.get_full_name() or self.username


class LoginThrottle(models.Model):
    """Failed-login counter shared by every web worker and kept across restarts (audit H1). Rows are written only by
    apps.accounts.throttle with atomic upserts; a row whose window has ended counts as zero."""
    key = models.CharField(max_length=200, primary_key=True)
    count = models.PositiveIntegerField()
    window_ends = models.DateTimeField(db_index=True)
