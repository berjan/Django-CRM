import base64
from email import policy
from email.parser import BytesParser
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from communications.crypto import decrypt_credentials, encrypt_credentials
from communications.gmail import reply_to_thread, send_lead_email
from communications.models import (
    EmailSuppression,
    EmailThread,
    LeadEmailMessage,
    MailboxConnection,
)
from leads.models import Lead


@pytest.fixture
def mailbox(org_a):
    return MailboxConnection.objects.create(
        org=org_a,
        email_address="planning@bruensdt.nl",
        display_name="Bruens Duurzame Technieken",
        credentials_encrypted=encrypt_credentials({"token": "test"}),
        provider_history_id="100",
    )


@pytest.fixture
def lead(org_a):
    return Lead.objects.create(
        org=org_a,
        title="Installatiepartner",
        first_name="Jan",
        last_name="Installateur",
        email="jan@example.com",
        status="assigned",
    )


def gmail_service(*results):
    service = MagicMock()
    execute = service.users.return_value.messages.return_value.send.return_value.execute
    execute.side_effect = list(results)
    return service


@override_settings(GMAIL_TOKEN_ENCRYPTION_KEY="test-encryption-key")
def test_credentials_are_encrypted_at_rest():
    value = encrypt_credentials({"refresh_token": "secret", "token": "access"})

    assert "secret" not in value
    assert decrypt_credentials(value)["refresh_token"] == "secret"


@pytest.mark.django_db
@override_settings(GMAIL_TOKEN_ENCRYPTION_KEY="test-encryption-key")
def test_send_and_reply_create_a_lead_thread(mailbox, lead):
    service = gmail_service(
        {"id": "gmail-message-1", "threadId": "gmail-thread-1"},
        {"id": "gmail-message-2", "threadId": "gmail-thread-1"},
    )

    with patch("communications.gmail._service", return_value=service):
        message = send_lead_email(
            mailbox=mailbox,
            lead=lead,
            subject="Kennismaken",
            body_text="Beste Jan,\n\nKunnen we kennismaken?",
            follow_up_days=7,
        )
        reply = reply_to_thread(thread=message.thread, body_text="Een aanvulling.")

    lead.refresh_from_db()
    assert message.direction == LeadEmailMessage.DIRECTION_OUTBOUND
    assert reply.thread_id == message.thread_id
    assert lead.last_contacted is not None
    assert (lead.next_follow_up - lead.last_contacted).days == 5
    assert EmailThread.objects.filter(lead=lead).count() == 1
    assert LeadEmailMessage.objects.filter(thread=message.thread).count() == 2

    second_call = service.users.return_value.messages.return_value.send.call_args_list[
        1
    ]
    raw = second_call.kwargs["body"]["raw"]
    mime = BytesParser(policy=policy.default).parsebytes(
        base64.urlsafe_b64decode(raw.encode("ascii"))
    )
    assert second_call.kwargs["body"]["threadId"] == "gmail-thread-1"
    assert mime["In-Reply-To"].startswith("<")
    assert mime["References"].startswith("<")


@pytest.mark.django_db
@override_settings(GMAIL_TOKEN_ENCRYPTION_KEY="test-encryption-key")
def test_suppressed_lead_cannot_be_emailed(mailbox, lead):
    EmailSuppression.objects.create(
        org=lead.org,
        email_address=lead.email,
        reason=EmailSuppression.REASON_MANUAL,
    )

    with pytest.raises(ValueError, match="suppressed"):
        send_lead_email(
            mailbox=mailbox,
            lead=lead,
            subject="No send",
            body_text="This must not be sent",
        )


@pytest.mark.django_db
@override_settings(
    GMAIL_OAUTH_CLIENT_ID="",
    GMAIL_OAUTH_CLIENT_SECRET="",
)
def test_mailbox_api_is_org_scoped_and_reports_configuration(
    admin_client, mailbox, org_b_client
):
    response = admin_client.get("/api/communications/mailboxes/")
    other_response = org_b_client.get("/api/communications/mailboxes/")

    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["mailboxes"][0]["email_address"] == mailbox.email_address
    assert other_response.status_code == 200
    assert other_response.json()["mailboxes"] == []


@pytest.mark.django_db
@override_settings(
    GMAIL_OAUTH_CLIENT_ID="",
    GMAIL_OAUTH_CLIENT_SECRET="",
)
def test_only_admin_can_start_gmail_oauth(admin_client, user_client):
    admin_response = admin_client.post("/api/communications/gmail/connect/")
    user_response = user_client.post("/api/communications/gmail/connect/")

    assert admin_response.status_code == 503
    assert user_response.status_code == 403
