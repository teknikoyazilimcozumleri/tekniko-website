import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings


def _api_post(client, path, payload, **extra):
    return client.post(path, data=json.dumps(payload), content_type="application/json", **extra)


@pytest.mark.django_db
def test_ninja_docs_endpoint(client):
    response = client.get("/api/docs")
    assert response.status_code == 200


@pytest.mark.django_db
def test_ninja_openapi_endpoint(client):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200


@pytest.mark.django_db
def test_auth_login_success_returns_token_pair(client, user):
    response = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert "refresh" in body


@pytest.mark.django_db
def test_auth_login_invalid_credentials_returns_401(client, user):
    response = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_auth_login_throttle_after_multiple_attempts(client, user):
    statuses = []
    for _ in range(6):
        response = _api_post(
            client,
            "/api/auth/login/",
            {"username": user.username, "password": "wrong-password"},
        )
        statuses.append(response.status_code)

    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


@pytest.mark.django_db
def test_auth_refresh_success_returns_new_pair(client, user):
    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    refresh_token = login.json()["refresh"]

    response = _api_post(client, "/api/auth/refresh/", {"refresh": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert "access" in body
    assert "refresh" in body


@pytest.mark.django_db
def test_auth_refresh_invalid_token_returns_401(client):
    response = _api_post(client, "/api/auth/refresh/", {"refresh": "invalid-token"})
    assert response.status_code == 401


@pytest.mark.django_db
def test_account_delete_requires_auth(client):
    response = _api_post(client, "/api/account/delete/", {})
    assert response.status_code == 401


@pytest.mark.django_db
def test_account_delete_soft_deletes_user(client, user):
    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = _api_post(
        client,
        "/api/account/delete/",
        {},
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert response.status_code == 200
    assert response.json()["status"] == "deletion-requested"

    refreshed = get_user_model().objects.get(pk=user.pk)
    assert refreshed.is_deleted is True
    assert refreshed.is_active is False


@pytest.mark.django_db
def test_rbac_protected_requires_auth(client):
    response = client.get("/api/rbac/protected/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_rbac_protected_forbidden_without_role(client, user):
    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = client.get("/api/rbac/protected/", HTTP_AUTHORIZATION=f"Bearer {access_token}")
    assert response.status_code == 403


@pytest.mark.django_db
def test_rbac_protected_success_with_admin_role(client, user, admin_role):
    admin_role.users.add(user)
    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = client.get("/api/rbac/protected/", HTTP_AUTHORIZATION=f"Bearer {access_token}")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ----- Payments API -----


@pytest.mark.django_db
def test_payments_checkout_initialize_requires_auth(client):
    response = _api_post(
        client,
        "/api/payments/checkout/initialize/",
        {"price": "100", "currency": "TRY"},
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_payments_checkout_initialize_invalid_price_returns_400(client, user):
    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = _api_post(
        client,
        "/api/payments/checkout/initialize/",
        {"price": "-1", "currency": "TRY"},
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert response.status_code == 400
    assert "price" in response.json().get("detail", "").lower() or "positive" in response.json().get("detail", "").lower()


@pytest.mark.django_db
def test_payments_checkout_initialize_invalid_price_string_returns_400(client, user):
    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = _api_post(
        client,
        "/api/payments/checkout/initialize/",
        {"price": "not-a-number", "currency": "TRY"},
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_subscriptions_my_returns_plan_details(client, user, subscription_plan_with_iyzico):
    from apps.subscriptions.models import Subscription

    Subscription.objects.create(
        user=user,
        plan=subscription_plan_with_iyzico,
        status=Subscription.Status.ACTIVE,
        iyzico_subscription_reference_code="sub-ref-1",
    )

    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = client.get("/api/subscriptions/my/", HTTP_AUTHORIZATION=f"Bearer {access_token}")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["plan"]["name"] == subscription_plan_with_iyzico.name
    assert payload[0]["plan"]["price"] == str(subscription_plan_with_iyzico.price)
    assert payload[0]["plan"]["currency"] == subscription_plan_with_iyzico.currency
    assert payload[0]["status"] == "active"
    assert payload[0]["status_display"]


@pytest.mark.django_db
@override_settings(PAYMENT_CALLBACK_HOST="http://localhost:8000")
def test_subscription_checkout_initialize_uses_backend_callback_host(
    client,
    user,
    subscription_plan_with_iyzico,
    monkeypatch,
):
    captured = {}

    def fake_initialize_subscription_checkout(**kwargs):
        captured["callback_url"] = kwargs["callback_url"]
        return (
            {
                "token": "subscription-token-1",
                "paymentPageUrl": "https://sandbox-cp.iyzipay.com/mock",
                "checkoutFormContent": "<form></form>",
            },
            {},
        )

    monkeypatch.setattr(
        "apps.subscriptions.api.initialize_subscription_checkout",
        fake_initialize_subscription_checkout,
    )

    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = _api_post(
        client,
        "/api/subscriptions/checkout/initialize/",
        {
            "plan_id": subscription_plan_with_iyzico.id,
            "callback_url": "http://localhost:5174/subscriptions/callback/",
        },
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 200
    assert captured["callback_url"] == "http://localhost:8000/subscriptions/callback/"


@pytest.mark.django_db
def test_subscription_checkout_initialize_returns_public_form_url_when_payment_page_url_missing(
    client,
    user,
    subscription_plan_with_iyzico,
    monkeypatch,
):
    def fake_initialize_subscription_checkout(**kwargs):
        return (
            {
                "token": "subscription-token-2",
                "paymentPageUrl": "",
                "checkoutFormContent": "<form>checkout</form>",
            },
            {},
        )

    monkeypatch.setattr(
        "apps.subscriptions.api.initialize_subscription_checkout",
        fake_initialize_subscription_checkout,
    )

    login = _api_post(
        client,
        "/api/auth/login/",
        {"username": user.username, "password": "StrongPass123!"},
    )
    access_token = login.json()["access"]

    response = _api_post(
        client,
        "/api/subscriptions/checkout/initialize/",
        {"plan_id": subscription_plan_with_iyzico.id},
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
    )

    assert response.status_code == 200
    assert response.json()["payment_page_url"].endswith("/subscriptions/checkout/form/public/?tid=subscription-token-2")
