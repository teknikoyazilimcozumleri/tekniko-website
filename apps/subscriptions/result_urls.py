from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.core.cache import cache

SUBSCRIPTION_RESULT_CACHE_TIMEOUT_SECONDS = 3600
SUBSCRIPTION_CHECKOUT_FORM_CACHE_TIMEOUT_SECONDS = 3600


def build_subscription_callback_url(request) -> str:
    callback_host = (settings.PAYMENT_CALLBACK_HOST or "").strip().rstrip("/")
    if callback_host:
        return f"{callback_host}/subscriptions/callback/"
    return request.build_absolute_uri("/subscriptions/callback/")


def build_subscription_result_url(success: bool, reason: str | None = None, base_url: str | None = None) -> str:
    target_url = (base_url or f"{settings.FRONTEND_APP_URL}/subscriptions/result").strip()
    parts = urlsplit(target_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["success"] = "true" if success else "false"
    if reason:
        query["reason"] = reason
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def normalize_subscription_result_url(raw_url: str | None) -> str:
    if not raw_url:
        return ""
    parts = urlsplit(raw_url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""

    allowed_origins = {urlsplit(settings.FRONTEND_APP_URL).netloc}
    allowed_origins.update(urlsplit(origin).netloc for origin in settings.CORS_ALLOWED_ORIGINS)
    if parts.netloc not in allowed_origins:
        return ""

    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def build_subscription_result_cache_key(token: str) -> str:
    return f"subscription_result_url:{token}"


def build_subscription_checkout_form_cache_key(token: str) -> str:
    return f"subscription_checkout_form:{token}"


def store_subscription_result_url(token: str, result_url: str) -> None:
    if not token or not result_url:
        return
    cache.set(
        build_subscription_result_cache_key(token),
        result_url,
        timeout=SUBSCRIPTION_RESULT_CACHE_TIMEOUT_SECONDS,
    )


def pop_subscription_result_url(token: str) -> str:
    if not token:
        return ""
    cache_key = build_subscription_result_cache_key(token)
    result_url = cache.get(cache_key) or ""
    cache.delete(cache_key)
    return result_url


def store_subscription_checkout_form(token: str, checkout_form_html: str) -> None:
    if not token or not checkout_form_html:
        return
    cache.set(
        build_subscription_checkout_form_cache_key(token),
        checkout_form_html,
        timeout=SUBSCRIPTION_CHECKOUT_FORM_CACHE_TIMEOUT_SECONDS,
    )


def pop_subscription_checkout_form(token: str) -> str:
    if not token:
        return ""
    cache_key = build_subscription_checkout_form_cache_key(token)
    checkout_form_html = cache.get(cache_key) or ""
    cache.delete(cache_key)
    return checkout_form_html
