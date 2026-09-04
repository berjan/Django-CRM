"""Kanban-friendly lead email status annotations."""

from django.db.models import (
    Case,
    CharField,
    Count,
    DateTimeField,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

EMAIL_STATUS_NONE = "none"
EMAIL_STATUS_DRAFT = "draft"
EMAIL_STATUS_SENT = "sent"
EMAIL_STATUS_REPLIED = "replied"
EMAIL_STATUS_FOLLOW_UP = "follow_up"
EMAIL_STATUS_VALUES = {
    EMAIL_STATUS_NONE,
    EMAIL_STATUS_DRAFT,
    EMAIL_STATUS_SENT,
    EMAIL_STATUS_REPLIED,
    EMAIL_STATUS_FOLLOW_UP,
}


def annotate_email_status(queryset):
    """Annotate leads with their current communication state without N+1 queries."""
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
    outbound_messages = LeadEmailMessage.objects.filter(
        org_id=OuterRef("org_id"),
        thread__lead_id=OuterRef("pk"),
        direction=LeadEmailMessage.DIRECTION_OUTBOUND,
    ).order_by("-occurred_at", "-created_at")
    inbound_messages = LeadEmailMessage.objects.filter(
        org_id=OuterRef("org_id"),
        thread__lead_id=OuterRef("pk"),
        direction=LeadEmailMessage.DIRECTION_INBOUND,
    ).order_by("-occurred_at", "-created_at")

    queryset = queryset.annotate(
        email_draft_count=Coalesce(
            Subquery(draft_counts, output_field=IntegerField()),
            Value(0),
        ),
        last_email_sent_at=Subquery(
            outbound_messages.values("occurred_at")[:1],
            output_field=DateTimeField(),
        ),
        last_email_reply_at=Subquery(
            inbound_messages.values("occurred_at")[:1],
            output_field=DateTimeField(),
        ),
    )

    latest_message_is_reply = Q(last_email_reply_at__isnull=False) & (
        Q(last_email_sent_at__isnull=True)
        | Q(last_email_reply_at__gt=F("last_email_sent_at"))
    )
    return queryset.annotate(
        email_status=Case(
            When(latest_message_is_reply, then=Value(EMAIL_STATUS_REPLIED)),
            When(
                last_email_sent_at__isnull=False,
                next_follow_up__lt=timezone.localdate(),
                then=Value(EMAIL_STATUS_FOLLOW_UP),
            ),
            When(
                last_email_sent_at__isnull=False,
                then=Value(EMAIL_STATUS_SENT),
            ),
            When(
                email_draft_count__gt=0,
                then=Value(EMAIL_STATUS_DRAFT),
            ),
            default=Value(EMAIL_STATUS_NONE),
            output_field=CharField(),
        )
    )


def filter_email_status(queryset, value):
    """Apply a supported email-status filter and ignore unknown values."""
    if value not in EMAIL_STATUS_VALUES:
        return queryset
    if "email_status" not in queryset.query.annotations:
        queryset = annotate_email_status(queryset)
    return queryset.filter(email_status=value)
