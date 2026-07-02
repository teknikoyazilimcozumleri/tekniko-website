from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja.security import HttpBearer


ALGORITHM = "HS256"


def _now():
    return datetime.now(timezone.utc)


def build_access_token(user):
    payload = {
        "type": "access",
        "user_id": str(user.id),
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(minutes=15)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def build_refresh_token(user):
    payload = {
        "type": "refresh",
        "user_id": str(user.id),
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(raw_token, expected_type):
    payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Invalid token type.")
    return payload


class JWTAuthBearer(HttpBearer):
    def authenticate(self, request, token):
        payload = decode_token(token, expected_type="access")
        user_model = get_user_model()
        user = user_model.objects.filter(id=payload.get("user_id"), is_active=True).first()
        if not user:
            return None
        request.user = user
        return user
