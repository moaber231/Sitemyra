import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    secret = (settings.SECRET_KEY or "development-only-secret").encode()
    digest = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_value(plaintext: str | None) -> str:
    if plaintext is None:
        return ""
    return _fernet().encrypt(str(plaintext).encode()).decode()


def decrypt_value(token: str | None) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(str(token).encode()).decode()
    except (InvalidToken, ValueError):
        # Backwards-compat: value may predate encryption.
        return str(token)


class EncryptedTextField(models.TextField):
    """Text field encrypted at rest with Fernet (AES-128-CBC + HMAC).

    Values are transparently encrypted on save and decrypted on load.
    Lookups on this field are not supported (exact search would leak).
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        text = str(value)
        # Avoid double-encryption: Fernet tokens always start with gAAAAA.
        if text.startswith("gAAAAA"):
            return text
        return encrypt_value(text)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return decrypt_value(value)

    def to_python(self, value):
        if value is None or value == "":
            return value
        text = str(value)
        if text.startswith("gAAAAA"):
            return decrypt_value(text)
        return text
