from rest_framework import serializers

from communications.models import EmailThread, LeadEmailMessage, MailboxConnection


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
            "occurred_at",
            "provider_labels",
        )
        read_only_fields = fields


class EmailThreadSerializer(serializers.ModelSerializer):
    messages = EmailMessageSerializer(many=True, read_only=True)
    mailbox_email = serializers.EmailField(
        source="mailbox.email_address", read_only=True
    )

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
            "messages",
        )
        read_only_fields = fields
