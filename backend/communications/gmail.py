from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from email.message import EmailMessage as MimeEmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from cases.inbound.parser import parse_raw_email
from communications.crypto import decrypt_credentials, encrypt_credentials
from communications.models import EmailThread, LeadEmailMessage, MailboxConnection
from communications.render import render_outbound_email

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
STATE_SALT = "communications.gmail.oauth"
logger = logging.getLogger(__name__)


def _oauth_config() -> dict:
    client_id = getattr(settings, "GMAIL_OAUTH_CLIENT_ID", "")
    client_secret = getattr(settings, "GMAIL_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ImproperlyConfigured(
            "GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET are required"
        )
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def oauth_redirect_uri() -> str:
    return getattr(settings, "GMAIL_OAUTH_REDIRECT_URI", "") or (
        f"{settings.FRONTEND_URL.rstrip('/')}/settings/email"
    )


def gmail_is_configured() -> bool:
    return bool(
        getattr(settings, "GMAIL_OAUTH_CLIENT_ID", "")
        and getattr(settings, "GMAIL_OAUTH_CLIENT_SECRET", "")
    )


def build_authorization_url(*, org_id, user_id) -> str:
    state = signing.dumps(
        {"org_id": str(org_id), "user_id": str(user_id)}, salt=STATE_SALT
    )
    flow = Flow.from_client_config(
        _oauth_config(), scopes=GMAIL_SCOPES, redirect_uri=oauth_redirect_uri()
    )
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return authorization_url


def validate_state(state: str, *, org_id, user_id) -> None:
    payload = signing.loads(state, salt=STATE_SALT, max_age=600)
    if payload != {"org_id": str(org_id), "user_id": str(user_id)}:
        raise signing.BadSignature("Gmail OAuth state does not match this session")


def _credentials_payload(credentials: Credentials) -> dict:
    return {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or GMAIL_SCOPES),
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }


def _credentials_from_payload(payload: dict) -> Credentials:
    expiry = payload.get("expiry")
    parsed_expiry = datetime.fromisoformat(expiry) if expiry else None
    if parsed_expiry and parsed_expiry.tzinfo is not None:
        parsed_expiry = parsed_expiry.astimezone(dt_timezone.utc).replace(tzinfo=None)
    return Credentials(
        token=payload.get("token"),
        refresh_token=payload.get("refresh_token"),
        token_uri=payload.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=payload.get("client_id"),
        client_secret=payload.get("client_secret"),
        scopes=payload.get("scopes") or GMAIL_SCOPES,
        expiry=parsed_expiry,
    )


def _service(mailbox: MailboxConnection):
    credentials = _credentials_from_payload(
        decrypt_credentials(mailbox.credentials_encrypted)
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        mailbox.credentials_encrypted = encrypt_credentials(
            _credentials_payload(credentials)
        )
        mailbox.save(update_fields=["credentials_encrypted", "updated_at"])
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def connect_mailbox(*, code: str, state: str, org, user) -> MailboxConnection:
    validate_state(state, org_id=org.id, user_id=user.id)
    flow = Flow.from_client_config(
        _oauth_config(), scopes=GMAIL_SCOPES, redirect_uri=oauth_redirect_uri()
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    email_address = profile["emailAddress"].strip().lower()

    existing = MailboxConnection.objects.filter(
        org=org, provider=MailboxConnection.PROVIDER_GMAIL, email_address=email_address
    ).first()
    if existing and not credentials.refresh_token:
        old_payload = decrypt_credentials(existing.credentials_encrypted)
        credentials.refresh_token = old_payload.get("refresh_token")
    if not credentials.refresh_token:
        raise ImproperlyConfigured(
            "Google did not return a refresh token; revoke the app grant and reconnect"
        )

    mailbox, _ = MailboxConnection.objects.update_or_create(
        org=org,
        provider=MailboxConnection.PROVIDER_GMAIL,
        email_address=email_address,
        defaults={
            "display_name": user.name or email_address,
            "credentials_encrypted": encrypt_credentials(
                _credentials_payload(credentials)
            ),
            "provider_history_id": str(profile.get("historyId", "")),
            "is_active": True,
            "last_error": "",
        },
    )
    return mailbox


def _message_id_header(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    return value if value.startswith("<") and value.endswith(">") else f"<{value}>"


def _raw_message(
    *,
    mailbox: MailboxConnection,
    to_address: str,
    subject: str,
    body_text: str,
    body_html: str,
    thread: EmailThread | None = None,
) -> tuple[str, str]:
    message = MimeEmailMessage()
    message["To"] = to_address
    message["From"] = formataddr(
        (mailbox.display_name or mailbox.email_address, mailbox.email_address)
    )
    message["Subject"] = subject
    domain = mailbox.email_address.rsplit("@", 1)[-1]
    rfc_message_id = make_msgid(domain=domain)
    message["Message-ID"] = rfc_message_id

    if thread:
        latest = thread.messages.order_by("-occurred_at").first()
        if latest and latest.rfc_message_id:
            message["In-Reply-To"] = _message_id_header(latest.rfc_message_id)
            references = latest.references.split() if latest.references else []
            references.append(latest.rfc_message_id)
            message["References"] = " ".join(
                _message_id_header(item) for item in dict.fromkeys(references)
            )

    message.set_content(body_text)
    message.add_alternative(body_html, subtype="html")
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return raw, rfc_message_id


@transaction.atomic
def send_lead_email(
    *,
    mailbox: MailboxConnection,
    lead,
    subject: str,
    body_text: str,
    follow_up_days: int = 5,
) -> LeadEmailMessage:
    if not mailbox.is_active:
        raise ValueError("Mailbox is not active")
    if mailbox.org_id != lead.org_id:
        raise ValueError("Mailbox and lead must belong to the same organization")
    if not lead.email:
        raise ValueError("Lead has no email address")

    from communications.models import EmailSuppression

    if EmailSuppression.objects.filter(
        org=lead.org,
        email_address__iexact=lead.email,
        is_active=True,
    ).exists():
        raise ValueError("This email address is suppressed")

    rendered = render_outbound_email(body_text, organization=lead.org)
    raw, rfc_message_id = _raw_message(
        mailbox=mailbox,
        to_address=lead.email,
        subject=subject,
        body_text=rendered.body_text,
        body_html=rendered.body_html,
    )
    result = (
        _service(mailbox)
        .users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    now = timezone.now()
    thread = EmailThread.objects.create(
        org=lead.org,
        mailbox=mailbox,
        lead=lead,
        provider_thread_id=result["threadId"],
        subject=subject,
        last_message_at=now,
    )
    message = LeadEmailMessage.objects.create(
        org=lead.org,
        thread=thread,
        mailbox=mailbox,
        provider_message_id=result["id"],
        rfc_message_id=rfc_message_id.strip("<>"),
        direction=LeadEmailMessage.DIRECTION_OUTBOUND,
        from_address=mailbox.email_address,
        to_addresses=[lead.email],
        subject=subject,
        body_text=rendered.body_text,
        body_html=rendered.body_html,
        provider_labels=result.get("labelIds", ["SENT"]),
        occurred_at=now,
    )
    lead.last_contacted = now.date()
    lead.next_follow_up = now.date() + timedelta(days=follow_up_days)
    lead.save(update_fields=["last_contacted", "next_follow_up", "updated_at"])
    return message


@transaction.atomic
def reply_to_thread(
    *, thread: EmailThread, body_text: str, follow_up_days: int = 5
) -> LeadEmailMessage:
    mailbox = thread.mailbox
    lead = thread.lead
    if not mailbox.is_active:
        raise ValueError("Mailbox is not active")
    if not lead.email:
        raise ValueError("Lead has no email address")

    from communications.models import EmailSuppression

    if EmailSuppression.objects.filter(
        org=lead.org,
        email_address__iexact=lead.email,
        is_active=True,
    ).exists():
        raise ValueError("This email address is suppressed")

    rendered = render_outbound_email(body_text, organization=lead.org)
    raw, rfc_message_id = _raw_message(
        mailbox=mailbox,
        to_address=lead.email,
        subject=thread.subject,
        body_text=rendered.body_text,
        body_html=rendered.body_html,
        thread=thread,
    )
    result = (
        _service(mailbox)
        .users()
        .messages()
        .send(
            userId="me",
            body={"raw": raw, "threadId": thread.provider_thread_id},
        )
        .execute()
    )
    now = timezone.now()
    message = LeadEmailMessage.objects.create(
        org=thread.org,
        thread=thread,
        mailbox=mailbox,
        provider_message_id=result["id"],
        rfc_message_id=rfc_message_id.strip("<>"),
        direction=LeadEmailMessage.DIRECTION_OUTBOUND,
        from_address=mailbox.email_address,
        to_addresses=[lead.email],
        subject=thread.subject,
        body_text=rendered.body_text,
        body_html=rendered.body_html,
        provider_labels=result.get("labelIds", ["SENT"]),
        occurred_at=now,
    )
    thread.last_message_at = now
    thread.save(update_fields=["last_message_at", "updated_at"])
    lead.last_contacted = now.date()
    lead.next_follow_up = now.date() + timedelta(days=follow_up_days)
    lead.save(update_fields=["last_contacted", "next_follow_up", "updated_at"])
    return message


def _ingest_gmail_message(
    mailbox: MailboxConnection, message_id: str, service=None
) -> bool:
    if LeadEmailMessage.objects.filter(
        mailbox=mailbox, provider_message_id=message_id
    ).exists():
        return False

    service = service or _service(mailbox)
    try:
        payload = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="raw")
            .execute()
        )
    except HttpError as exc:
        status_code = getattr(exc, "status_code", None) or getattr(
            getattr(exc, "resp", None), "status", None
        )
        if status_code != 404:
            raise
        logger.info(
            "Skipping Gmail history message %s because it no longer exists",
            message_id,
        )
        return False
    thread = (
        EmailThread.objects.filter(
            mailbox=mailbox, provider_thread_id=payload["threadId"]
        )
        .select_related("lead")
        .first()
    )
    if thread is None:
        return False

    raw = base64.urlsafe_b64decode(payload["raw"].encode("ascii"))
    parsed = parse_raw_email(raw)
    labels = payload.get("labelIds", [])
    from_address = parseaddr(parsed.from_address)[1].lower()
    direction = (
        LeadEmailMessage.DIRECTION_OUTBOUND
        if "SENT" in labels or from_address == mailbox.email_address.lower()
        else LeadEmailMessage.DIRECTION_INBOUND
    )
    occurred_at = datetime.fromtimestamp(
        int(payload.get("internalDate", "0")) / 1000, tz=dt_timezone.utc
    )
    LeadEmailMessage.objects.create(
        org=mailbox.org,
        thread=thread,
        mailbox=mailbox,
        provider_message_id=payload["id"],
        rfc_message_id=parsed.message_id,
        in_reply_to=parsed.in_reply_to,
        references=" ".join(parsed.references),
        direction=direction,
        from_address=from_address or mailbox.email_address,
        to_addresses=parsed.to_addresses,
        cc_addresses=parsed.cc_addresses,
        subject=parsed.subject,
        body_text=parsed.body_text,
        body_html=parsed.body_html,
        provider_labels=labels,
        occurred_at=occurred_at,
    )
    thread.last_message_at = occurred_at
    if direction == LeadEmailMessage.DIRECTION_INBOUND:
        thread.reply_received_at = occurred_at
        thread.lead.next_follow_up = None
        thread.lead.save(update_fields=["next_follow_up", "updated_at"])
    thread.save(update_fields=["last_message_at", "reply_received_at", "updated_at"])
    return True


def sync_mailbox(mailbox: MailboxConnection) -> int:
    """Synchronize Gmail additions since the stored History ID."""
    service = _service(mailbox)
    if not mailbox.provider_history_id:
        profile = service.users().getProfile(userId="me").execute()
        mailbox.provider_history_id = str(profile["historyId"])
        mailbox.last_synced_at = timezone.now()
        mailbox.last_error = ""
        mailbox.save(
            update_fields=[
                "provider_history_id",
                "last_synced_at",
                "last_error",
                "updated_at",
            ]
        )
        return 0

    message_ids: set[str] = set()
    page_token = None
    latest_history_id = mailbox.provider_history_id
    try:
        while True:
            response = (
                service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=mailbox.provider_history_id,
                    historyTypes=["messageAdded"],
                    pageToken=page_token,
                    maxResults=500,
                )
                .execute()
            )
            latest_history_id = str(response.get("historyId", latest_history_id))
            for history in response.get("history", []):
                for addition in history.get("messagesAdded", []):
                    message_id = addition.get("message", {}).get("id")
                    if message_id:
                        message_ids.add(message_id)
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except HttpError as exc:
        if (
            getattr(exc, "status_code", None) != 404
            and getattr(getattr(exc, "resp", None), "status", None) != 404
        ):
            raise
        profile = service.users().getProfile(userId="me").execute()
        latest_history_id = str(profile["historyId"])
        mailbox.last_error = "Gmail history expired; synchronization baseline was reset"

    ingested = sum(
        _ingest_gmail_message(mailbox, item, service=service) for item in message_ids
    )
    mailbox.provider_history_id = latest_history_id
    mailbox.last_synced_at = timezone.now()
    if not mailbox.last_error.startswith("Gmail history expired"):
        mailbox.last_error = ""
    mailbox.save(
        update_fields=[
            "provider_history_id",
            "last_synced_at",
            "last_error",
            "updated_at",
        ]
    )
    return ingested
