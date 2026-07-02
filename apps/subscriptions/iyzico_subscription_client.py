"""
Iyzico Subscription API (v2) client.
Uses IYZWSv2 HMAC-SHA256 auth; requests to /v2/subscription/*.
"""
import base64
import hashlib
import hmac
import json
import time

import requests
from django.conf import settings


def _get_base_url():
    raw = (settings.IYZICO_BASE_URL or "").strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    host = raw.split("/")[0] if raw else "sandbox-api.iyzipay.com"
    return f"https://{host}"


def _make_authorization(method, uri_path, body_str, api_key, secret_key):
    """IYZWSv2: randomKey + uri_path + body -> HMAC-SHA256 -> base64(apiKey:...&randomKey:...&signature:...)."""
    random_key = str(int(time.time() * 1000)) + "123456789"
    payload = random_key + uri_path
    if body_str:
        payload += body_str
    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    auth_str = f"apiKey:{api_key}&randomKey:{random_key}&signature:{signature}"
    b64 = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
    return f"IYZWSv2 {b64}", random_key


def _request(method, path, body=None):
    api_key = (settings.IYZICO_API_KEY or "").strip()
    secret_key = (settings.IYZICO_SECRET_KEY or "").strip()
    if not api_key or not secret_key:
        return None, {"status": "failure", "errorMessage": "Iyzico API keys not set"}
    base_url = _get_base_url()
    url = base_url + path
    body_str = json.dumps(body, separators=(",", ":")) if body else ""
    auth_header, random_key = _make_authorization(method, path, body_str, api_key, secret_key)
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json",
        "x-iyzi-rnd": random_key,
    }
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=30)
        else:
            r = requests.post(url, headers=headers, data=body_str, timeout=30)
        data = r.json() if r.text else {}
        if r.status_code != 200 and isinstance(data, dict):
            data.setdefault("httpStatus", r.status_code)
        return r.status_code, data
    except Exception as e:
        return None, {"status": "failure", "errorMessage": str(e)}


def list_products():
    """GET /v2/subscription/products -> list of {referenceCode, name, ...}."""
    path = "/v2/subscription/products"
    code, data = _request("GET", path)
    if code != 200 or data.get("status") != "success":
        return None, data
    inner = data.get("data") or {}
    items = inner.get("items", []) if isinstance(inner, dict) else []
    return items, data


def create_product(name, description="", conversation_id=None):
    """POST /v2/subscription/products -> productReferenceCode in data."""
    path = "/v2/subscription/products"
    body = {"name": name, "description": description or name}
    if conversation_id:
        body["conversationId"] = conversation_id
    body["locale"] = "tr"
    code, data = _request("POST", path, body)
    if code != 200 or data.get("status") != "success":
        return None, data
    ref = (data.get("data") or {}).get("referenceCode")
    return ref, data


def list_pricing_plans(product_reference_code):
    """GET /v2/subscription/products/{productReferenceCode}/pricing-plans -> list of {referenceCode, name, price, ...}."""
    path = f"/v2/subscription/products/{product_reference_code}/pricing-plans"
    code, data = _request("GET", path)
    if code != 200 or data.get("status") != "success":
        return None, data
    inner = data.get("data") or {}
    items = inner.get("items", []) if isinstance(inner, dict) else []
    return items, data


def create_pricing_plan(product_reference_code, name, price, currency_code="TRY", conversation_id=None):
    """POST /v2/subscription/products/{productReferenceCode}/pricing-plans -> referenceCode in data."""
    path = f"/v2/subscription/products/{product_reference_code}/pricing-plans"
    body = {
        "name": name,
        "price": str(price),
        "currencyCode": currency_code,
        "paymentInterval": "MONTHLY",
        "planPaymentType": "RECURRING",
        "locale": "tr",
    }
    if conversation_id:
        body["conversationId"] = conversation_id
    code, data = _request("POST", path, body)
    if code != 200 or data.get("status") != "success":
        return None, data
    ref = (data.get("data") or {}).get("referenceCode")
    return ref, data


def initialize_subscription_checkout(
    pricing_plan_reference_code,
    callback_url,
    customer_name,
    customer_surname,
    email,
    gsm_number,
    identity_number,
    billing_address,
    billing_contact_name,
    billing_city,
    billing_country,
    billing_zip_code="",
    subscription_initial_status="ACTIVE",
    conversation_id=None,
):
    """POST /v2/subscription/checkoutform/initialize -> token, checkoutFormContent."""
    path = "/v2/subscription/checkoutform/initialize"
    body = {
        "locale": "tr",
        "callbackUrl": callback_url,
        "pricingPlanReferenceCode": pricing_plan_reference_code,
        "subscriptionInitialStatus": subscription_initial_status,
        "customer": {
            "name": customer_name,
            "surname": customer_surname,
            "email": email,
            "gsmNumber": gsm_number,
            "identityNumber": identity_number,
            "billingAddress": {
                "address": billing_address,
                "contactName": billing_contact_name,
                "city": billing_city,
                "country": billing_country,
                "zipCode": billing_zip_code or "34000",
            },
        },
    }
    if conversation_id:
        body["conversationId"] = conversation_id
    code, data = _request("POST", path, body)
    if code != 200:
        return None, data
    if data.get("status") != "success":
        return None, data
    token = data.get("token")
    checkout_form_content = data.get("checkoutFormContent")
    payment_page_url = data.get("paymentPageUrl")
    return {
        "token": token,
        "checkoutFormContent": checkout_form_content,
        "paymentPageUrl": payment_page_url,
    }, data


def retrieve_subscription_checkout_result(token, conversation_id=None):
    """GET /v2/subscription/checkoutform/{token} -> subscription result (referenceCode, subscriptionStatus, startDate, endDate)."""
    path = f"/v2/subscription/checkoutform/{token}"
    # GET has no body; query params are not in path for signature - Iyzico doc uses uri path only
    code, data = _request("GET", path)
    if code != 200:
        return None, data
    if data.get("status") != "success":
        return None, data
    inner = data.get("data") or {}
    return {
        "referenceCode": inner.get("referenceCode"),
        "subscriptionStatus": inner.get("subscriptionStatus"),
        "startDate": inner.get("startDate"),
        "endDate": inner.get("endDate"),
        "createdDate": inner.get("createdDate"),
    }, data
