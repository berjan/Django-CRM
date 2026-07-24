from django.db import models

from common.base import BaseOrgModel


class MailboxConnection(BaseOrgModel):
    """An OAuth-backed mailbox that can send and synchronize lead email."""

    PROVIDER_GMAIL = "gmail"
    PROVIDER_CHOICES = [(PROVIDER_GMAIL, "Google Gmail")]

    provider = models.CharField(
        max_length=16, choices=PROVIDER_CHOICES, default=PROVIDER_GMAIL
    )
    email_address = models.EmailField()
    display_name = models.CharField(max_length=255, blank=True, default="")
    credentials_encrypted = models.TextField()
    provider_history_id = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        db_table = "communication_mailbox"
        ordering = ("email_address",)
        constraints = [
            models.UniqueConstraint(
                fields=["org", "provider", "email_address"],
                name="uniq_communication_mailbox_per_org",
            )
        ]
        indexes = [models.Index(fields=["org", "is_active"])]

    def __str__(self):
        return f"{self.email_address} ({self.provider})"


class EmailThread(BaseOrgModel):
    """A Gmail thread associated with one CRM lead."""

    mailbox = models.ForeignKey(
        MailboxConnection, on_delete=models.CASCADE, related_name="threads"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="email_threads"
    )
    provider_thread_id = models.CharField(max_length=255)
    subject = models.CharField(max_length=512, blank=True, default="")
    last_message_at = models.DateTimeField(blank=True, null=True)
    reply_received_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "communication_email_thread"
        ordering = ("-last_message_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["mailbox", "provider_thread_id"],
                name="uniq_provider_thread_per_mailbox",
            )
        ]
        indexes = [
            models.Index(fields=["org", "lead", "-last_message_at"]),
        ]

    def __str__(self):
        return f"{self.subject or self.provider_thread_id} — {self.lead_id}"


class LeadEmailMessage(BaseOrgModel):
    """A synchronized inbound or outbound Gmail message."""

    DIRECTION_INBOUND = "inbound"
    DIRECTION_OUTBOUND = "outbound"
    DIRECTION_CHOICES = [
        (DIRECTION_INBOUND, "Inbound"),
        (DIRECTION_OUTBOUND, "Outbound"),
    ]

    thread = models.ForeignKey(
        EmailThread, on_delete=models.CASCADE, related_name="messages"
    )
    mailbox = models.ForeignKey(
        MailboxConnection, on_delete=models.CASCADE, related_name="messages"
    )
    provider_message_id = models.CharField(max_length=255)
    rfc_message_id = models.CharField(max_length=512, blank=True, default="")
    in_reply_to = models.CharField(max_length=512, blank=True, default="")
    references = models.TextField(blank=True, default="")
    direction = models.CharField(max_length=16, choices=DIRECTION_CHOICES)
    from_address = models.EmailField()
    to_addresses = models.JSONField(default=list, blank=True)
    cc_addresses = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=512, blank=True, default="")
    body_text = models.TextField(blank=True, default="")
    body_html = models.TextField(blank=True, default="")
    provider_labels = models.JSONField(default=list, blank=True)
    occurred_at = models.DateTimeField()

    class Meta:
        db_table = "communication_email_message"
        ordering = ("occurred_at", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["mailbox", "provider_message_id"],
                name="uniq_provider_message_per_mailbox",
            )
        ]
        indexes = [
            models.Index(fields=["org", "thread", "occurred_at"]),
            models.Index(fields=["org", "rfc_message_id"]),
        ]

    def __str__(self):
        return f"{self.direction}: {self.subject or self.provider_message_id}"


class EmailSuppression(BaseOrgModel):
    """Addresses that must not receive additional lead outreach."""

    REASON_UNSUBSCRIBED = "unsubscribed"
    REASON_HARD_BOUNCE = "hard_bounce"
    REASON_MANUAL = "manual"
    REASON_CHOICES = [
        (REASON_UNSUBSCRIBED, "Unsubscribed"),
        (REASON_HARD_BOUNCE, "Hard bounce"),
        (REASON_MANUAL, "Manually suppressed"),
    ]

    email_address = models.EmailField()
    reason = models.CharField(max_length=32, choices=REASON_CHOICES)
    detail = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "communication_email_suppression"
        constraints = [
            models.UniqueConstraint(
                fields=["org", "email_address"],
                name="uniq_email_suppression_per_org",
            )
        ]
        indexes = [models.Index(fields=["org", "is_active"])]

    def __str__(self):
        return f"{self.email_address}: {self.reason}"
