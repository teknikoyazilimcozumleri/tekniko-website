import time

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.text import slugify
from ninja import Router, Schema
from apps.audit.models import AuditLog

from apps.rbac.models import Role

from .jwt_utils import JWTAuthBearer, build_access_token, build_refresh_token, decode_token

router = Router(tags=["auth"])


class LoginInput(Schema):
    username: str
    password: str


class RefreshInput(Schema):
    refresh: str


class GoogleAuthInput(Schema):
    id_token: str


class GooglePasswordSetupInput(Schema):
    id_token: str
    password: str
    password_confirm: str


class MessageOutput(Schema):
    detail: str


class TokenPairOutput(Schema):
    access: str
    refresh: str


class DeleteOutput(Schema):
    status: str


class RegisterInput(Schema):
    username: str
    email: str
    password: str
    password_confirm: str


class RegisterOutput(Schema):
    id: str
    username: str
    email: str


class MeOutput(Schema):
    id: str
    username: str
    email: str
    roles: list[str]


def _is_throttled(request, username):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"login-throttle:{ip}:{username.lower()}"
    count = cache.get(key, 0) + 1
    cache.set(key, count, timeout=60)
    return count > 5


def _verify_google_id_token(google_id_token: str):
    client_id = (getattr(settings, "GOOGLE_CLIENT_ID", None) or "").strip()
    if not client_id:
        return None, "Google Sign-In is not configured."

    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token_verifier
    except ImportError as exc:
        return None, f"Google auth library not available: {exc}. Install: pip install google-auth"

    last_error = None
    for attempt in range(2):
        try:
            payload = google_id_token_verifier.verify_oauth2_token(
                google_id_token,
                google_requests.Request(),
                client_id,
                clock_skew_in_seconds=30,
            )
            return payload, None
        except ValueError as exc:
            return None, f"Invalid Google token: {exc}"
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == 0:
                time.sleep(0.2)
    return None, f"Google token verification temporarily unavailable: {last_error}"


def _get_or_create_user_from_google_id_token(google_id_token: str):
    payload, error = _verify_google_id_token(google_id_token)
    if error:
        return None, error, False
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return None, "Email not provided by Google.", False

    User = get_user_model()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        return user, None, not user.has_usable_password()

    base_username = slugify((payload.get("name") or email.split("@")[0] or "user")[:30]) or "user"
    username = base_username
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        username = f"{base_username}{suffix}"
        suffix += 1

    user = User.objects.create_user(username=username, email=email, password=None)
    return user, None, True


def _set_password_from_google_id_token(google_id_token: str, password: str):
    payload, error = _verify_google_id_token(google_id_token)
    if error:
        return None, error
    email = (payload.get("email") or "").strip().lower()
    if not email:
        return None, "Email not provided by Google."

    User = get_user_model()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        return None, "User not found for this Google account."
    if user.has_usable_password():
        return None, "Password is already set for this account."

    user.set_password(password)
    user.save(update_fields=["password"])
    return user, None


@router.post("/auth/login/", response={200: TokenPairOutput, 401: MessageOutput, 429: MessageOutput})
def login_endpoint(request, payload: LoginInput):
    if _is_throttled(request, payload.username):
        return 429, {"detail": "Too many login attempts. Please try later."}

    user = authenticate(request, username=payload.username, password=payload.password)
    if not user or not user.is_active:
        return 401, {"detail": "Invalid credentials."}
    
    AuditLog.objects.create(
        user=user,
        action="USER_LOGGED_IN",
        path=request.path,
        metadata={
            "method": "standard_login",
            "ip": request.META.get("REMOTE_ADDR"),
            "user_agent": request.META.get("HTTP_USER_AGENT")
        }
    )

    return {
        "access": build_access_token(user),
        "refresh": build_refresh_token(user),
    }


@router.post("/auth/refresh/", response={200: TokenPairOutput, 401: MessageOutput})
def refresh_endpoint(request, payload: RefreshInput):
    try:
        token_payload = decode_token(payload.refresh, expected_type="refresh")
    except Exception:
        return 401, {"detail": "Invalid refresh token."}

    user = get_user_model().objects.filter(id=token_payload.get("user_id"), is_active=True).first()
    if not user:
        return 401, {"detail": "User not found."}

    return {
        "access": build_access_token(user),
        "refresh": build_refresh_token(user),
    }


@router.post("/auth/google/", response={200: TokenPairOutput, 400: MessageOutput, 428: MessageOutput, 503: MessageOutput})
def google_auth_endpoint(request, payload: GoogleAuthInput):
    user, error, requires_password_setup = _get_or_create_user_from_google_id_token(payload.id_token)
    if error:
        if "not configured" in error or "not available" in error or "temporarily unavailable" in error:
            return 503, {"detail": error}
        return 400, {"detail": error}
    if requires_password_setup:
        return 428, {"detail": "Please set your password to continue."}
    return {"access": build_access_token(user), "refresh": build_refresh_token(user)}


@router.post("/auth/google/set-password/", response={200: TokenPairOutput, 400: MessageOutput, 503: MessageOutput})
def google_set_password_endpoint(request, payload: GooglePasswordSetupInput):
    if payload.password != payload.password_confirm:
        return 400, {"detail": "Passwords do not match."}
    if len(payload.password) < 8:
        return 400, {"detail": "Password must be at least 8 characters."}

    user, error = _set_password_from_google_id_token(payload.id_token, payload.password)
    if error:
        if "not configured" in error or "not available" in error or "temporarily unavailable" in error:
            return 503, {"detail": error}
        return 400, {"detail": error}
    return {"access": build_access_token(user), "refresh": build_refresh_token(user)}


@router.post("/auth/register/", response={201: RegisterOutput, 400: MessageOutput})
def register_endpoint(request, payload: RegisterInput):
    if payload.password != payload.password_confirm:
        return 400, {"detail": "Passwords do not match."}
    if len(payload.password) < 8:
        return 400, {"detail": "Password must be at least 8 characters."}

    username = payload.username.strip()
    email = payload.email.strip().lower()
    User = get_user_model()

    if User.objects.filter(username__iexact=username).exists():
        return 400, {"detail": "A user with that username already exists."}
    if User.objects.filter(email__iexact=email).exists():
        return 400, {"detail": "A user with that email already exists."}

    user = User.objects.create_user(
        username=username,
        email=email,
        password=payload.password,
    )
    
    AuditLog.objects.create(
        user=user,
        action="USER_REGISTERED",
        path=request.path,
        metadata={"email": email, "registration_type": "standard"}
)

    return 201, {"id": str(user.id), "username": user.username, "email": user.email}


@router.get("/account/me/", auth=JWTAuthBearer(), response=MeOutput)
def me_endpoint(request):
    user = request.auth
    roles = list(Role.objects.filter(users=user).values_list("name", flat=True))
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "roles": roles,
    }


@router.post("/account/delete/", auth=JWTAuthBearer(), response=DeleteOutput)
def delete_my_account_endpoint(request):
    user = request.auth
    user.soft_delete()
    return {"status": "deletion-requested"}
