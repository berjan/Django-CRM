import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernet() -> Fernet:
    secret = getattr(settings, "GMAIL_TOKEN_ENCRYPTION_KEY", "") or settings.SECRET_KEY
    if not secret:
        raise ImproperlyConfigured(
            "GMAIL_TOKEN_ENCRYPTION_KEY or SECRET_KEY is required"
        )
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_credentials(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _fernet().encrypt(raw).decode("ascii")


def decrypt_credentials(value: str) -> dict:
    try:
        raw = _fernet().decrypt(value.encode("ascii"))
    except (InvalidToken, ValueError) as exc:
        raise ImproperlyConfigured(
            "Stored Gmail credentials cannot be decrypted with the configured key"
        ) from exc
    return json.loads(raw.decode("utf-8"))
