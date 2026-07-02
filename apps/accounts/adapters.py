from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.utils.text import slugify


User = get_user_model()


class AccountAdapter(DefaultAccountAdapter):
    """
    Project-specific account adapter.

    Currently relies on the default behaviour but keeps a hook
    in place for future custom user fields or validation rules.
    """

    def is_open_for_signup(self, request):
        return super().is_open_for_signup(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Ensures a valid username is generated when signing up via social providers.
    New users must complete signup (e.g. set password) before an account is created.
    """

    def is_auto_signup_allowed(self, request, sociallogin):
        return False

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        # Django's default user model (and our custom one) require a username.
        # Some providers may not supply one, so derive it from email or name.
        base_username = (
            (data.get("username") or "")
            or (data.get("email") or "").split("@")[0]
            or (data.get("name") or "").replace(" ", "")
        )
        base_username = slugify(base_username) or "user"

        candidate = base_username
        suffix = 1
        while User.objects.filter(username__iexact=candidate).exists():
            suffix += 1
            candidate = f"{base_username}{suffix}"

        user.username = candidate
        return user

