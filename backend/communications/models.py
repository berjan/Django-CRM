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


class ThreadReadState(BaseOrgModel):
    """Per-CRM-user read position for a lead email thread."""

    thread = models.ForeignKey(
        EmailThread, on_delete=models.CASCADE, related_name="read_states"
    )
    profile = models.ForeignKey(
        "common.Profile",
        on_delete=models.CASCADE,
        related_name="email_thread_read_states",
    )
    last_read_at = models.DateTimeField()

    class Meta:
        db_table = "communication_thread_read_state"
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "profile"],
                name="uniq_email_thread_read_state",
            )
        ]
        indexes = [
            models.Index(fields=["org", "profile", "-last_read_at"]),
        ]

    def __str__(self):
        return f"{self.profile_id}: {self.thread_id}"


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


class EmailTemplate(BaseOrgModel):
    """Reusable lead email content with immutable version history."""

    SCOPE_ORG = "org"
    SCOPE_PERSONAL = "personal"
    SCOPE_CHOICES = [
        (SCOPE_ORG, "Organization"),
        (SCOPE_PERSONAL, "Personal"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    purpose = models.CharField(max_length=100, blank=True, default="")
    language = models.CharField(max_length=10, default="nl")
    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES, default=SCOPE_ORG)
    owner = models.ForeignKey(
        "common.Profile",
        on_delete=models.CASCADE,
        related_name="email_templates",
        blank=True,
        null=True,
    )
    subject = models.CharField(max_length=512)
    body_text = models.TextField()
    is_active = models.BooleanField(default=True)
    current_version = models.PositiveIntegerField(default=1)
    usage_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "communication_email_template"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["org", "name", "scope", "owner"],
                name="uniq_email_template_name_scope_owner",
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(fields=["org", "is_active"]),
            models.Index(fields=["org", "scope", "owner"]),
        ]

    def __str__(self):
        return self.name


class EmailTemplateVersion(BaseOrgModel):
    """Immutable snapshot of template content used for audit and drafts."""

    template = models.ForeignKey(
        EmailTemplate, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.PositiveIntegerField()
    subject = models.CharField(max_length=512)
    body_text = models.TextField()

    class Meta:
        db_table = "communication_email_template_version"
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version"],
                name="uniq_email_template_version",
            )
        ]
        indexes = [models.Index(fields=["org", "template", "-version"])]

    def __str__(self):
        return f"{self.template.name} v{self.version}"


class LeadEmailTemplateAssignment(BaseOrgModel):
    """Templates selected for a lead, with at most one default."""

    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="email_template_assignments",
    )
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.CASCADE,
        related_name="lead_assignments",
    )
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "communication_lead_template_assignment"
        ordering = ("-is_default", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["lead", "template"],
                name="uniq_email_template_assignment",
            ),
            models.UniqueConstraint(
                fields=["lead"],
                condition=models.Q(is_default=True),
                name="uniq_default_email_template_per_lead",
            ),
        ]
        indexes = [models.Index(fields=["org", "lead", "-is_default"])]

    def __str__(self):
        return f"{self.lead_id}: {self.template.name}"


class EmailDraft(BaseOrgModel):
    """Reviewable content that is the only supported input to a new send."""

    STATUS_DRAFT = "draft"
    STATUS_SENT = "sent"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SENT, "Sent"),
    ]
    SOURCE_MANUAL = "manual"
    SOURCE_TEMPLATE = "template"
    SOURCE_AI = "ai"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_TEMPLATE, "Template"),
        (SOURCE_AI, "AI"),
    ]

    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.CASCADE, related_name="email_drafts"
    )
    thread = models.ForeignKey(
        EmailThread,
        on_delete=models.CASCADE,
        related_name="drafts",
        blank=True,
        null=True,
    )
    mailbox = models.ForeignKey(
        MailboxConnection, on_delete=models.PROTECT, related_name="drafts"
    )
    template_version = models.ForeignKey(
        EmailTemplateVersion,
        on_delete=models.PROTECT,
        related_name="drafts",
        blank=True,
        null=True,
    )
    recipient = models.EmailField()
    subject = models.CharField(max_length=512)
    body_text = models.TextField()
    body_html = models.TextField(blank=True, default="")
    follow_up_days = models.PositiveSmallIntegerField(default=5)
    source = models.CharField(
        max_length=16, choices=SOURCE_CHOICES, default=SOURCE_MANUAL
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT
    )
    sent_message = models.OneToOneField(
        LeadEmailMessage,
        on_delete=models.PROTECT,
        related_name="source_draft",
        blank=True,
        null=True,
    )
    idempotency_key = models.CharField(max_length=128, blank=True, default="")
    sent_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "communication_email_draft"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["org", "idempotency_key"],
                condition=~models.Q(idempotency_key=""),
                name="uniq_email_draft_idempotency_key",
            ),
            models.CheckConstraint(
                condition=models.Q(follow_up_days__gte=1)
                & models.Q(follow_up_days__lte=30),
                name="email_draft_follow_up_days_range",
            ),
        ]
        indexes = [
            models.Index(fields=["org", "lead", "-created_at"]),
            models.Index(fields=["org", "status"]),
        ]

    def __str__(self):
        return f"{self.recipient}: {self.subject}"
