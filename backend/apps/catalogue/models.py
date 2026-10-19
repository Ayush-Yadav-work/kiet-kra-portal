import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class AcademicYear(models.Model):
    label = models.CharField(max_length=9, unique=True)  # "2026-27"
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return self.label


class ReportingPeriod(models.Model):
    """[opens_at, closes_at) in UTC; boundaries are 00:00 Asia/Kolkata (plan 2.3)."""

    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="periods")
    index = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=40)
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()

    class Meta:
        ordering = ["year__label", "index"]
        constraints = [
            models.UniqueConstraint(fields=["year", "index"], name="unique_period_index"),
            models.CheckConstraint(condition=models.Q(index__gte=1, index__lte=6), name="period_index_1_6"),
            models.CheckConstraint(condition=models.Q(opens_at__lt=models.F("closes_at")), name="period_opens_first"),
        ]

    def is_open(self, at):
        return self.opens_at <= at < self.closes_at

    def __str__(self):
        return f"{self.year.label} P{self.index}"


class KRA(models.Model):
    number = models.PositiveSmallIntegerField(unique=True)
    activity_text = models.TextField()  # exact workbook text
    nba_ref = models.CharField(max_length=20, blank=True)
    naac_ref = models.CharField(max_length=20, blank=True)
    active = models.BooleanField(default=True)
    # Report layout used to prefill new draft assignments; KRAs 1–45 take it from their assignments (D-065).
    default_template = models.ForeignKey("TemplateVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"KRA {self.number}"


class TemplateVersion(models.Model):
    key = models.CharField(max_length=40)
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    schema = models.JSONField()
    renderer_template = models.CharField(max_length=120)  # Django template path
    source_checksum = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "version"], name="unique_template_version")]

    def __str__(self):
        return f"{self.key} v{self.version}"


class AnnualAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="assignments")
    kra = models.ForeignKey(KRA, on_delete=models.PROTECT, related_name="assignments")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="assignments")
    target_text = models.TextField()  # immutable once assigned (plan 2.2)
    template_version = models.ForeignKey(TemplateVersion, null=True, blank=True, on_delete=models.PROTECT)
    assigned_at = models.DateTimeField(auto_now_add=True)
    # First reporting period with an obligation (VC Phase 1, D-073). NULL = every period of the year: all assignments that
    # existed before this field (seeded and Phase 5A) keep their full-year obligations.
    effective_start_period = models.ForeignKey(ReportingPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    finalised_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    finalised_at = models.DateTimeField(null=True, blank=True)  # NULL for migrated rows; assigned_at is their creation time

    LOCKED = ("target_text", "template_version_id", "effective_start_period_id", "department_id", "kra_id", "year_id")

    class Meta:
        ordering = ["kra__number"]
        constraints = [models.UniqueConstraint(fields=["department", "kra", "year"], name="unique_assignment")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            old = AnnualAssignment.objects.only(*self.LOCKED).get(pk=self.pk)
            if old.target_text != self.target_text:
                raise ValidationError("Assigned annual targets are fixed for the year.")
            if old.template_version_id and old.template_version_id != self.template_version_id:
                raise ValidationError("Template version cannot change once assigned.")
            if any(getattr(old, f) != getattr(self, f) for f in ("effective_start_period_id", "department_id", "kra_id", "year_id")):
                raise ValidationError("A finalised assignment cannot change its year, department, KRA or start period.")
        super().save(*args, **kwargs)


class DraftAssignment(models.Model):
    """VC staging row for a future year's department/KRA assignment (Phase 5A, D-065). Deans never see drafts; finalizing a
    year creates the operational AnnualAssignment and freezes the draft (finalized_assignment set)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="+")
    kra = models.ForeignKey(KRA, on_delete=models.PROTECT, related_name="+")
    year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="draft_assignments")
    target_text = models.TextField()  # exact text, never parsed
    template_version = models.ForeignKey(TemplateVersion, on_delete=models.PROTECT, related_name="+")
    copied_from = models.ForeignKey(AnnualAssignment, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    # Stored snapshot of the source year's target (changed-target comparison never reads another year's live data).
    source_year = models.ForeignKey(AcademicYear, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    source_target = models.TextField(null=True, blank=True)
    edit_version = models.PositiveIntegerField(default=0)  # optimistic concurrency for VC edits across tabs
    removed_at = models.DateTimeField(null=True, blank=True)  # Removed state: kept for restore, excluded from finalisation
    removed_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    finalized_assignment = models.OneToOneField(AnnualAssignment, null=True, blank=True, on_delete=models.PROTECT, related_name="draft")
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kra__number", "department__code"]
        constraints = [models.UniqueConstraint(fields=["department", "kra", "year"], name="unique_draft_assignment")]
