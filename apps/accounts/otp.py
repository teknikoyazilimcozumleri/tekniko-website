"""
Email OTP (2FA) for credential-based login.

OTP is stored in cache; delivery is abstracted so it can be logged now
and switched to real email later.
"""
from __future__ import annotations

import random
import secrets
import time
from typing import TYPE_CHECKING

from django.core.cache import cache

if TYPE_CHECKING:
    from django.contrib.auth import get_user_model

    User = get_user_model()

# Cache key prefixes and TTL (seconds)
EMAIL_OTP_TOKEN_PREFIX = "email_otp_token:"
EMAIL_OTP_CODE_PREFIX = "email_otp_code:"
EMAIL_OTP_TOKEN_TTL = 180  # 3 minutes
EMAIL_OTP_CODE_TTL = 180   # 3 minutes


def create_and_send_otp(user: "User") -> str:
    """
    Generate a 6-digit OTP, store it in cache for the user, log it (no email yet),
    and return a one-time token to pass to the verify page.
    """
    code = str(random.randint(100_000, 999_999))
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + EMAIL_OTP_TOKEN_TTL

    cache_key_token = f"{EMAIL_OTP_TOKEN_PREFIX}{token}"
    cache_key_code = f"{EMAIL_OTP_CODE_PREFIX}{user.pk}"
    cache.set(
        cache_key_token,
        {"user_id": str(user.pk), "expires_at": expires_at},
        timeout=EMAIL_OTP_TOKEN_TTL,
    )
    cache.set(cache_key_code, code, timeout=EMAIL_OTP_CODE_TTL)

    send_otp_email(user, code)
    return token


def get_otp_expires_at(token: str) -> float | None:
    """
    Return Unix timestamp when the OTP token expires, or None if invalid/expired.
    Does not consume the token.
    """
    cache_key_token = f"{EMAIL_OTP_TOKEN_PREFIX}{token}"
    payload = cache.get(cache_key_token)
    if not payload:
        return None
    return payload.get("expires_at")


def send_otp_email(user: "User", code: str) -> None:
    """
    Deliver OTP to the user. For now only print to terminal; later switch to real email.
    """
    sep = "=" * 50
    print(f"\n{sep}\n  [OTP DOĞRULAMA KODU]\n  E-posta: {user.email}\n  Kod: {code}\n{sep}\n")


def verify_otp(token: str, code: str) -> "User | None":
    """
    Verify the token and code; return the user if valid, else None.
    Rejects if token expired. Consumes the token (removes from cache on success).
    """
    cache_key_token = f"{EMAIL_OTP_TOKEN_PREFIX}{token}"
    payload = cache.get(cache_key_token)
    if not payload:
        return None
    expires_at = payload.get("expires_at")
    if expires_at is not None and time.time() > expires_at:
        cache.delete(cache_key_token)
        return None
    user_id = payload.get("user_id")
    if not user_id:
        return None
    cache_key_code = f"{EMAIL_OTP_CODE_PREFIX}{user_id}"
    stored_code = cache.get(cache_key_code)
    if not stored_code or str(stored_code) != str(code).strip():
        return None
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if not user:
        return None
    cache.delete(cache_key_token)
    cache.delete(cache_key_code)
    return user
