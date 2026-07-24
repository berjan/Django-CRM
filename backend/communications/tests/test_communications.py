import base64
from email import policy
from email.parser import BytesParser
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from communications.crypto import decrypt_credentials, encrypt_credentials
from communications.gmail import reply_to_thread, send_lead_email
from communications.models import (
    EmailDraft,
    EmailSuppression,
    EmailTemplate,
    EmailTemplateVersion,
    EmailThread,
    LeadEmailMessage,
    LeadEmailTemplateAssignment,
    MailboxConnection,
)
from communications.render import render_email
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


@pytest.mark.django_db
def test_template_versions_are_immutable_and_org_scoped(
    admin_client, org_b_client, org_a
):
    create = admin_client.post(
        "/api/communications/templates/",
        {
            "name": "Eerste contact",
            "description": "Installateur benaderen",
            "purpose": "installer_outreach",
            "language": "nl",
            "scope": "org",
            "subject": "Kennismaken met {{ organization.name }}",
            "body_text": "Beste {{ lead.first_name }},",
        },
        format="json",
    )

    assert create.status_code == 201
    template_id = create.json()["id"]
    update = admin_client.patch(
        f"/api/communications/templates/{template_id}/",
        {"body_text": "Hallo {{ lead.first_name }},"},
        format="json",
    )

    assert update.status_code == 200
    assert update.json()["current_version"] == 2
    versions = EmailTemplateVersion.objects.filter(template_id=template_id).order_by(
        "version"
    )
    assert [version.body_text for version in versions] == [
        "Beste {{ lead.first_name }},",
        "Hallo {{ lead.first_name }},",
    ]
    assert org_b_client.get("/api/communications/templates/").json()["results"] == []
    assert EmailTemplate.objects.filter(org=org_a, pk=template_id).exists()


@pytest.mark.django_db
def test_template_preview_reports_missing_variables(admin_client, org_a, lead):
    template = EmailTemplate.objects.create(
        org=org_a,
        name="Met bedrijf",
        subject="Voor {{ lead.company_name }}",
        body_text="Beste {{ lead.first_name }},",
    )
    EmailTemplateVersion.objects.create(
        org=org_a,
        template=template,
        version=1,
        subject=template.subject,
        body_text=template.body_text,
    )

    response = admin_client.post(
        f"/api/communications/templates/{template.id}/preview/",
        {"lead_id": str(lead.id)},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["missing_variables"] == ["lead.company_name"]


@pytest.mark.django_db
def test_only_one_default_template_assignment(admin_client, org_a, lead):
    templates = []
    for number in (1, 2):
        template = EmailTemplate.objects.create(
            org=org_a,
            name=f"Template {number}",
            subject=f"Onderwerp {number}",
            body_text="Bericht",
        )
        EmailTemplateVersion.objects.create(
            org=org_a,
            template=template,
            version=1,
            subject=template.subject,
            body_text=template.body_text,
        )
        templates.append(template)

    for template in templates:
        response = admin_client.post(
            f"/api/communications/leads/{lead.id}/template-assignments/",
            {"template_id": str(template.id), "is_default": True},
            format="json",
        )
        assert response.status_code == 201

    assignments = LeadEmailTemplateAssignment.objects.filter(lead=lead)
    assert assignments.count() == 2
    assert assignments.filter(is_default=True).get().template == templates[1]


@pytest.mark.django_db
@override_settings(GMAIL_TOKEN_ENCRYPTION_KEY="test-encryption-key")
def test_draft_send_is_idempotent_and_tracks_template_version(
    admin_client, org_a, mailbox, lead
):
    template = EmailTemplate.objects.create(
        org=org_a,
        name="Installatiepartner",
        subject="Kennismaken {{ lead.first_name }}",
        body_text="Beste {{ lead.first_name }},\n\nKunnen we kennismaken?",
    )
    EmailTemplateVersion.objects.create(
        org=org_a,
        template=template,
        version=1,
        subject=template.subject,
        body_text=template.body_text,
    )
    create = admin_client.post(
        f"/api/communications/leads/{lead.id}/drafts/",
        {
            "mailbox_id": str(mailbox.id),
            "template_id": str(template.id),
            "follow_up_days": 7,
        },
        format="json",
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    assert create.json()["subject"] == "Kennismaken Jan"
    service = gmail_service({"id": "gmail-draft-1", "threadId": "thread-draft-1"})

    with patch("communications.gmail._service", return_value=service):
        first = admin_client.post(
            f"/api/communications/drafts/{draft_id}/send/",
            {"idempotency_key": "send-draft-once"},
            format="json",
        )
        second = admin_client.post(
            f"/api/communications/drafts/{draft_id}/send/",
            {"idempotency_key": "send-draft-once"},
            format="json",
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == EmailDraft.STATUS_SENT
    assert service.users.return_value.messages.return_value.send.call_count == 1
    assert LeadEmailMessage.objects.filter(thread__lead=lead).count() == 1
    template.refresh_from_db()
    assert template.usage_count == 1


@pytest.mark.django_db
def test_safe_renderer_escapes_html(org_a, lead, admin_profile):
    lead.first_name = "<Jan>"
    result = render_email(
        subject="Hallo {{ lead.first_name }}",
        body_text="Beste {{ lead.first_name }}",
        lead=lead,
        organization=org_a,
        sender=admin_profile,
    )

    assert result.subject == "Hallo <Jan>"
    assert result.body_html == "<p>Beste &lt;Jan&gt;</p>"
