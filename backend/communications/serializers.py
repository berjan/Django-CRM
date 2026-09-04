import re

from rest_framework import serializers

from common.email_body import email_body_preview, plain_text_email_body
from communications.models import (
    EmailDraft,
    EmailSignature,
    EmailTemplate,
    EmailTemplateVersion,
    EmailThread,
    LeadEmailMessage,
    LeadEmailTemplateAssignment,
    MailboxConnection,
)
from communications.render import find_unknown_variables, render_outbound_email


class EmailSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSignature
        fields = (
            "id",
            "sender_name",
            "sender_role",
            "company_name",
            "phone_number",
            "email_address",
            "website_url",
            "address",
            "logo_url",
            "primary_color",
            "accent_color",
            "certifications",
            "review_score",
            "review_count",
            "reviews_url",
            "projects_url",
            "is_enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    @staticmethod
    def _validate_color(value):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise serializers.ValidationError("Use a hexadecimal color like #426451")
        return value.upper()

    def validate_primary_color(self, value):
        return self._validate_color(value)

    def validate_accent_color(self, value):
        return self._validate_color(value)

    def validate_review_score(self, value):
        if value is not None and not 0 <= value <= 10:
            raise serializers.ValidationError("Review score must be between 0 and 10")
        return value

    def validate_certifications(self, value):
        if not isinstance(value, list) or len(value) > 6:
            raise serializers.ValidationError(
                "Use a list of at most six certifications"
            )
        cleaned = []
        for item in value:
            if not isinstance(item, dict) or not str(item.get("name", "")).strip():
                raise serializers.ValidationError("Each certification requires a name")
            certification = {"name": str(item["name"]).strip()[:100]}
            for key in ("url", "image_url"):
                url = str(item.get(key, "")).strip()
                if url and not url.startswith("https://"):
                    raise serializers.ValidationError(
                        f"Certification {key} must use HTTPS"
                    )
                certification[key] = url
            cleaned.append(certification)
        return cleaned


class MailboxConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailboxConnection
        fields = (
            "id",
            "provider",
            "email_address",
            "display_name",
            "is_active",
            "last_synced_at",
            "last_error",
            "created_at",
        )
        read_only_fields = fields


class EmailMessageSerializer(serializers.ModelSerializer):
    body_text = serializers.SerializerMethodField()
    body_preview = serializers.SerializerMethodField()

    class Meta:
        model = LeadEmailMessage
        fields = (
            "id",
            "direction",
            "from_address",
            "to_addresses",
            "cc_addresses",
            "subject",
            "body_text",
            "body_preview",
            "body_html",
            "occurred_at",
            "provider_labels",
        )
        read_only_fields = fields

    def get_body_text(self, obj):
        return plain_text_email_body(obj.body_text, obj.body_html)

    def get_body_preview(self, obj):
        return email_body_preview(obj.body_text, obj.body_html)


class EmailThreadSerializer(serializers.ModelSerializer):
    messages = EmailMessageSerializer(many=True, read_only=True)
    mailbox_email = serializers.EmailField(
        source="mailbox.email_address", read_only=True
    )
    message_count = serializers.SerializerMethodField()
    draft_count = serializers.SerializerMethodField()
    latest_snippet = serializers.SerializerMethodField()
    last_direction = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_unread = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    last_read_at = serializers.SerializerMethodField()

    class Meta:
        model = EmailThread
        fields = (
            "id",
            "lead",
            "mailbox",
            "mailbox_email",
            "subject",
            "last_message_at",
            "reply_received_at",
            "message_count",
            "draft_count",
            "latest_snippet",
            "last_direction",
            "unread_count",
            "is_unread",
            "status",
            "last_read_at",
            "messages",
        )
        read_only_fields = fields

    @staticmethod
    def _messages(obj):
        return list(obj.messages.all())

    @staticmethod
    def _read_at(obj):
        states = getattr(obj, "request_read_states", [])
        return states[0].last_read_at if states else None

    def get_message_count(self, obj):
        return getattr(obj, "message_count_value", len(self._messages(obj)))

    def get_draft_count(self, obj):
        return getattr(obj, "draft_count_value", 0)

    def get_latest_snippet(self, obj):
        messages = self._messages(obj)
        if not messages:
            return ""
        body = email_body_preview(
            messages[-1].body_text,
            messages[-1].body_html,
            limit=180,
        )
        return " ".join(body.split())[:180]

    def get_last_direction(self, obj):
        messages = self._messages(obj)
        return messages[-1].direction if messages else ""

    def get_unread_count(self, obj):
        read_at = self._read_at(obj)
        return sum(
            1
            for message in self._messages(obj)
            if message.direction == LeadEmailMessage.DIRECTION_INBOUND
            and (read_at is None or message.occurred_at > read_at)
        )

    def get_is_unread(self, obj):
        return self.get_unread_count(obj) > 0

    def get_status(self, obj):
        if self.get_draft_count(obj):
            return "draft"
        direction = self.get_last_direction(obj)
        if direction == LeadEmailMessage.DIRECTION_INBOUND:
            return "new_reply" if self.get_is_unread(obj) else "reply_received"
        if direction == LeadEmailMessage.DIRECTION_OUTBOUND:
            return "waiting_for_reply"
        return "empty"

    def get_last_read_at(self, obj):
        return self._read_at(obj)


class EmailTemplateVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateVersion
        fields = ("id", "version", "subject", "body_text", "created_at")
        read_only_fields = fields


class EmailTemplateSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.user.name", read_only=True)
    unknown_variables = serializers.SerializerMethodField()

    class Meta:
        model = EmailTemplate
        fields = (
            "id",
            "name",
            "description",
            "purpose",
            "language",
            "scope",
            "owner",
            "owner_name",
            "subject",
            "body_text",
            "is_active",
            "current_version",
            "usage_count",
            "unknown_variables",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "owner",
            "owner_name",
            "current_version",
            "usage_count",
            "unknown_variables",
            "created_at",
            "updated_at",
        )

    def get_unknown_variables(self, obj):
        return find_unknown_variables(obj.subject, obj.body_text)

    def validate(self, attrs):
        subject = attrs.get("subject", getattr(self.instance, "subject", ""))
        body_text = attrs.get("body_text", getattr(self.instance, "body_text", ""))
        unknown = find_unknown_variables(subject, body_text)
        if unknown:
            raise serializers.ValidationError(
                {"variables": f"Unknown template variables: {', '.join(unknown)}"}
            )
        return attrs


class LeadEmailTemplateAssignmentSerializer(serializers.ModelSerializer):
    template = EmailTemplateSerializer(read_only=True)
    template_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = LeadEmailTemplateAssignment
        fields = ("id", "lead", "template", "template_id", "is_default", "created_at")
        read_only_fields = ("id", "lead", "template", "created_at")


class EmailDraftSerializer(serializers.ModelSerializer):
    body_html = serializers.SerializerMethodField()
    template_id = serializers.UUIDField(
        source="template_version.template_id", read_only=True
    )
    template_version_number = serializers.IntegerField(
        source="template_version.version", read_only=True
    )
    mailbox_email = serializers.EmailField(
        source="mailbox.email_address", read_only=True
    )

    class Meta:
        model = EmailDraft
        fields = (
            "id",
            "lead",
            "thread",
            "mailbox",
            "mailbox_email",
            "template_id",
            "template_version_number",
            "recipient",
            "subject",
            "body_text",
            "body_html",
            "follow_up_days",
            "source",
            "status",
            "sent_message",
            "sent_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "lead",
            "thread",
            "mailbox",
            "mailbox_email",
            "template_id",
            "template_version_number",
            "recipient",
            "body_html",
            "source",
            "status",
            "sent_message",
            "sent_at",
            "created_at",
            "updated_at",
        )

    def get_body_html(self, obj):
        if obj.status != EmailDraft.STATUS_DRAFT:
            return obj.body_html
        signature = EmailSignature.objects.filter(
            org_id=obj.org_id, is_enabled=True
        ).first()
        return render_outbound_email(
            obj.body_text,
            organization=obj.org_id,
            signature=signature,
        ).body_html
