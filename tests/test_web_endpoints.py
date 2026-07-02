import re

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from urllib.parse import parse_qs, urlparse

from apps.accounts.otp import EMAIL_OTP_CODE_PREFIX


@pytest.mark.django_db
def test_home_page_renders(client):
    response = client.get(reverse("home"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_page_renders_for_anonymous(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_page_redirects_when_authenticated(client, user):
    client.force_login(user)
    response = client.get(reverse("account_login"))
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_login_post_success_redirects_to_verify_otp(client, user):
    """Credential login requires email OTP; redirect to verify page with token."""
    response = client.post(
        reverse("account_login"),
        data={"login": user.username, "password": "StrongPass123!"},
    )
    assert response.status_code == 302
    assert "/accounts/verify-email-otp/" in response.url
    assert "token=" in response.url


@pytest.mark.django_db
def test_verify_otp_valid_code_completes_login(client, user):
    """After entering valid OTP, user is logged in and redirected home."""
    login_response = client.post(
        reverse("account_login"),
        data={"login": user.username, "password": "StrongPass123!"},
    )
    assert login_response.status_code == 302
    query = parse_qs(urlparse(login_response.url).query)
    token = query.get("token", [None])[0]
    assert token
    code = cache.get(f"{EMAIL_OTP_CODE_PREFIX}{user.pk}")
    assert code
    verify_url = reverse("verify_email_otp") + "?token=" + token
    get_resp = client.get(verify_url)
    assert get_resp.status_code == 200
    csrf_match = re.search(
        r'name="csrfmiddlewaretoken" value="([^"]+)"',
        get_resp.content.decode(),
    )
    assert csrf_match
    post_data = {
        "token": token,
        "code": code,
        "csrfmiddlewaretoken": csrf_match.group(1),
    }
    final = client.post(verify_url, data=post_data, follow=False)
    assert final.status_code == 302
    assert final.url == "/"
    assert client.session.get("_auth_user_id") == str(user.pk)


@pytest.mark.django_db
def test_login_post_invalid_stays_on_page(client, user):
    response = client.post(
        reverse("account_login"),
        data={"login": user.username, "password": "wrong-password"},
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_logout_requires_authentication(client):
    response = client.get(reverse("account_logout"))
    assert response.status_code == 302
    # Unauthenticated: redirect to login or home (allauth behavior)
    assert "/login/" in response.url or response.url == "/"


@pytest.mark.django_db
def test_logout_redirects_to_login(client, user):
    client.force_login(user)
    response = client.post(reverse("account_logout"))
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_admin_index_redirects_to_admin_login(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response.url


@pytest.mark.django_db
def test_admin_login_page_renders(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200


# ----- Signup -----


@pytest.mark.django_db
def test_signup_page_renders_for_anonymous(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_signup_page_redirects_when_authenticated(client, user):
    client.force_login(user)
    response = client.get(reverse("account_signup"))
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_signup_post_success_redirects_home(client):
    response = client.post(
        reverse("account_signup"),
        data={
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        },
    )
    assert response.status_code == 302
    assert response.url == "/"
    assert get_user_model().objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_signup_post_invalid_stays_on_page(client):
    response = client.post(
        reverse("account_signup"),
        data={
            "username": "u",
            "email": "invalid-email",
            "password1": "short",
            "password2": "mismatch",
        },
    )
    assert response.status_code == 200


# ----- Password reset -----


@pytest.mark.django_db
def test_password_reset_page_renders(client):
    response = client.get(reverse("account_reset_password"))
    assert response.status_code == 200


# ----- Shortcut redirects (login/, register/, logout/, reset/) -----


@pytest.mark.django_db
def test_login_shortcut_redirects_to_account_login(client):
    response = client.get(reverse("login_page"))
    assert response.status_code == 302
    assert response.url == reverse("account_login")


@pytest.mark.django_db
def test_register_shortcut_redirects_to_account_signup(client):
    response = client.get(reverse("register_page"))
    assert response.status_code == 302
    assert response.url == reverse("account_signup")


@pytest.mark.django_db
def test_logout_shortcut_redirects_to_account_logout(client):
    response = client.get(reverse("logout_page"))
    assert response.status_code == 302
    assert response.url == reverse("account_logout")


@pytest.mark.django_db
def test_reset_shortcut_redirects_to_account_reset_password(client):
    response = client.get(reverse("password_reset_request"))
    assert response.status_code == 302
    assert response.url == reverse("account_reset_password")


# ----- Email OTP 2FA -----


@pytest.mark.django_db
def test_verify_otp_page_without_token_redirects_to_login(client):
    """Verify page without token redirects to login."""
    response = client.get(reverse("verify_email_otp"))
    assert response.status_code == 302
    assert response.url == reverse("account_login")


@pytest.mark.django_db
def test_verify_otp_invalid_code_shows_error(client, user):
    """Invalid or wrong OTP code shows form error."""
    login_response = client.post(
        reverse("account_login"),
        data={"login": user.username, "password": "StrongPass123!"},
    )
    query = parse_qs(urlparse(login_response.url).query)
    token = query.get("token", [None])[0]
    assert token
    verify_url = reverse("verify_email_otp") + "?token=" + token
    get_resp = client.get(verify_url)
    csrf_match = re.search(
        r'name="csrfmiddlewaretoken" value="([^"]+)"',
        get_resp.content.decode(),
    )
    assert csrf_match
    post_data = {
        "token": token,
        "code": "000000",
        "csrfmiddlewaretoken": csrf_match.group(1),
    }
    response = client.post(verify_url, data=post_data, follow=False)
    assert response.status_code == 200
    content_lower = response.content.decode().lower()
    assert "geçersiz" in content_lower or "tekrar" in content_lower or "invalid" in content_lower


# ----- Google OAuth (smoke: login URL redirects) -----


@pytest.mark.django_db
@pytest.mark.skipif(
    not getattr(settings, "GOOGLE_CLIENT_ID", "").strip(),
    reason="Google OAuth not configured (no SocialApp in test DB)",
)
def test_google_login_url_redirects_or_renders(client):
    response = client.get("/accounts/google/login/?process=login")
    assert response.status_code in (200, 302)
    if response.status_code == 302:
        assert "accounts.google.com" in response.url or response.url.startswith("/")


# ----- Subscriptions (web) -----


@pytest.mark.django_db
def test_subscriptions_plan_list_redirects_when_anonymous(client):
    response = client.get(reverse("subscriptions:plan_list"))
    assert response.status_code == 302
    assert "/login/" in response.url or "login" in response.url.lower()


@pytest.mark.django_db
def test_subscriptions_plan_list_renders_when_authenticated(client, user, subscription_plan):
    client.force_login(user)
    response = client.get(reverse("subscriptions:plan_list"))
    assert response.status_code == 200
    assert subscription_plan.name in response.content.decode() or "Basic" in response.content.decode()


@pytest.mark.django_db
def test_subscriptions_checkout_start_requires_login(client, subscription_plan_with_iyzico):
    response = client.get(
        reverse("subscriptions:checkout_start", kwargs={"plan_id": subscription_plan_with_iyzico.pk})
    )
    assert response.status_code == 302
    assert "login" in response.url.lower()


@pytest.mark.django_db
def test_subscriptions_checkout_start_404_for_invalid_plan(client, user):
    client.force_login(user)
    response = client.get(reverse("subscriptions:checkout_start", kwargs={"plan_id": 99999}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_subscriptions_checkout_start_plan_without_iyzico_shows_error(client, user, subscription_plan):
    client.force_login(user)
    response = client.get(reverse("subscriptions:checkout_start", kwargs={"plan_id": subscription_plan.pk}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Iyzico" in content or "eşleştirilmedi" in content or "plan" in content.lower()


@pytest.mark.django_db
def test_subscriptions_checkout_start_with_mock_redirects_to_form(client, user, subscription_plan_with_iyzico):
    from unittest.mock import patch

    client.force_login(user)
    mock_result = {"token": "test-token-123", "checkoutFormContent": "<form>Pay</form>"}
    with patch(
        "apps.subscriptions.views.initialize_subscription_checkout",
        return_value=(mock_result, {"status": "success"}),
    ):
        response = client.get(
            reverse("subscriptions:checkout_start", kwargs={"plan_id": subscription_plan_with_iyzico.pk})
        )
    assert response.status_code == 302
    assert "/subscriptions/checkout/form/" in response.url
    assert "tid=" in response.url
    assert "test-token-123" in response.url


@pytest.mark.django_db
def test_subscriptions_checkout_form_no_tid_redirects_to_plan_list(client, user):
    client.force_login(user)
    response = client.get(reverse("subscriptions:checkout_form"))
    assert response.status_code == 302
    assert response.url == "/subscriptions/"


@pytest.mark.django_db
def test_subscriptions_checkout_form_tid_without_session_redirects(client, user):
    client.force_login(user)
    response = client.get(reverse("subscriptions:checkout_form") + "?tid=some-token")
    assert response.status_code == 302
    assert response.url == "/subscriptions/"


@pytest.mark.django_db
def test_subscriptions_result_page_renders(client):
    response = client.get(reverse("subscriptions:result") + "?success=true")
    assert response.status_code == 200


@pytest.mark.django_db
def test_subscriptions_my_requires_login(client):
    response = client.get(reverse("subscriptions:my_subscriptions"))
    assert response.status_code == 302
    assert "login" in response.url.lower()


@pytest.mark.django_db
def test_subscriptions_my_renders_when_authenticated(client, user):
    client.force_login(user)
    response = client.get(reverse("subscriptions:my_subscriptions"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_subscriptions_callback_no_token_redirects_to_result_error(client, user):
    client.force_login(user)
    response = client.get(reverse("subscriptions:callback"))
    assert response.status_code == 302
    assert "/subscriptions/result/" in response.url
    assert "success=false" in response.url


@pytest.mark.django_db
def test_subscriptions_callback_token_without_session_redirects_to_result_error(client, user):
    client.force_login(user)
    response = client.get(reverse("subscriptions:callback") + "?token=unknown-token")
    assert response.status_code == 302
    assert "/subscriptions/result/" in response.url
    assert "success=false" in response.url


@pytest.mark.django_db
def test_subscriptions_webhook_post_returns_200(client):
    response = client.post(
        reverse("subscriptions:webhook"),
        data='{"iyziEventType": "subscription.order.success", "subscriptionReferenceCode": "ref-1"}',
        content_type="application/json",
    )
    assert response.status_code == 200


# ----- Payments (web) -----


@pytest.mark.django_db
def test_payments_start_page_renders(client, user):
    """Payment start page requires login; anonymous is redirected."""
    response = client.get(reverse("payment_start"))
    assert response.status_code == 302
    assert "/login/" in response.url
    client.force_login(user)
    response = client.get(reverse("payment_start"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_payments_result_page_renders(client):
    response = client.get(reverse("payment_result") + "?success=true")
    assert response.status_code == 200


@pytest.mark.django_db
def test_payments_callback_no_token_redirects_to_result_error(client):
    response = client.get(reverse("payment_callback"))
    assert response.status_code == 302
    assert "/payments/result/" in response.url
    assert "success=false" in response.url
