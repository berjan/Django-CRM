"""Lead queryset support for summarized email activity."""

from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    DateTimeField,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone


class LeadEmailStatus(models.TextChoices):
    """Primary email status displayed for a lead."""

    NONE = "none", "No email activity"
    DRAFT = "draft", "Draft"
    SENT = "sent", "Sent"
    REPLIED = "replied", "Reply received"
    FOLLOW_UP = "follow_up", "Follow-up needed"


class LeadEmailDirection(models.TextChoices):
    """Direction of the most recent synchronized lead email."""

    INBOUND = "inbound", "Inbound"
    OUTBOUND = "outbound", "Outbound"


class LeadQuerySet(models.QuerySet):
    """Lead queryset with reusable email-activity annotations."""

    def with_email_activity(self):
        """Add the email facts and primary display status used by lead views."""
        from communications.models import EmailDraft, LeadEmailMessage

        draft_counts = (
            EmailDraft.objects.filter(
                org_id=OuterRef("org_id"),
                lead_id=OuterRef("pk"),
                status=EmailDraft.STATUS_DRAFT,
            )
            .order_by()
            .values("lead_id")
            .annotate(total=Count("pk"))
            .values("total")[:1]
        )
        messages = LeadEmailMessage.objects.filter(
            org_id=OuterRef("org_id"),
            thread__lead_id=OuterRef("pk"),
        ).order_by("-occurred_at", "-created_at")
        outbound_messages = messages.filter(
            direction=LeadEmailMessage.DIRECTION_OUTBOUND
        )

        queryset = self.annotate(
            email_draft_count=Coalesce(
                Subquery(draft_counts, output_field=IntegerField()),
                Value(0),
            ),
            latest_email_direction=Subquery(
                messages.values("direction")[:1],
                output_field=CharField(),
            ),
            last_email_at=Subquery(
                messages.values("occurred_at")[:1],
                output_field=DateTimeField(),
            ),
            last_outbound_email_at=Subquery(
                outbound_messages.values("occurred_at")[:1],
                output_field=DateTimeField(),
            ),
        )
        queryset = queryset.annotate(
            email_follow_up_overdue=Case(
                When(
                    last_outbound_email_at__isnull=False,
                    next_follow_up__lt=timezone.localdate(),
                    then=Value(True),
                ),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

        # An actionable draft takes precedence over historical activity. The
        # underlying facts remain available to consumers that need more detail.
        return queryset.annotate(
            email_status=Case(
                When(
                    email_draft_count__gt=0,
                    then=Value(LeadEmailStatus.DRAFT),
                ),
                When(
                    latest_email_direction=LeadEmailDirection.INBOUND,
                    then=Value(LeadEmailStatus.REPLIED),
                ),
                When(
                    email_follow_up_overdue=True,
                    then=Value(LeadEmailStatus.FOLLOW_UP),
                ),
                When(
                    latest_email_direction=LeadEmailDirection.OUTBOUND,
                    then=Value(LeadEmailStatus.SENT),
                ),
                default=Value(LeadEmailStatus.NONE),
                output_field=CharField(),
            )
        )

    def for_email_status(self, email_status):
        """Filter by a validated primary email status."""
        return self.with_email_activity().filter(email_status=email_status)


class LeadManager(models.Manager.from_queryset(LeadQuerySet)):
    """Default lead manager exposing reusable queryset operations."""
