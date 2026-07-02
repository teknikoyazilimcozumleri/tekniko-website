"""
Thin Iyzico API layer for Checkout Form only.
- Checkout Form: card data never hits our server (no PCI scope).
- conversation_id: used for idempotency and correlation.
"""
import json
from django.conf import settings
import iyzipay


def get_options():
    """Build iyzipay options dict from settings.
    base_url must be host only. Sandbox: sandbox-api.iyzipay.com (not iyzico.com).
    If you set https://... we strip the scheme to avoid 'nonnumeric port' errors.
    """
    raw = (settings.IYZICO_BASE_URL or "").strip().rstrip("/")
    for prefix in ("https://", "http://"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix) :].strip()
            break
    base = raw.split("/")[0] if raw else "sandbox-api.iyzipay.com"

    return {
        "api_key": settings.IYZICO_API_KEY,
        "secret_key": settings.IYZICO_SECRET_KEY,
        "base_url": base,
    }


def initialize_checkout_form(
    *,
    price,
    paid_price,
    currency,
    callback_url,
    conversation_id,
    buyer,
    shipping_address,
    billing_address,
    basket_items,
    locale="tr",
    basket_id=None,
    payment_group="PRODUCT",
):
    """
    Call Iyzico Checkout Form Initialize. Returns token and payment page URL.
    Raises on missing config; returns dict with success/error from API.
    """
    options = get_options()
    if not options["api_key"] or not options["secret_key"]:
        raise ValueError("IYZICO_API_KEY and IYZICO_SECRET_KEY must be set")

    request = {
        "locale": locale,
        "conversationId": conversation_id,
        "price": str(price),
        "paidPrice": str(paid_price),
        "currency": currency,
        "paymentGroup": payment_group,
        "callbackUrl": callback_url,
        "buyer": buyer,
        "shippingAddress": shipping_address,
        "billingAddress": billing_address,
        "basketItems": basket_items,
    }
    if basket_id:
        request["basketId"] = basket_id

    checkout_form_initialize = iyzipay.CheckoutFormInitialize()
    result = checkout_form_initialize.create(request, options)
    data = json.loads(result.read().decode("utf-8"))

    if data.get("status") == "success":
        return {
            "status": "success",
            "token": data.get("token"),
            "paymentPageUrl": data.get("paymentPageUrl"),
            "checkoutFormContent": data.get("checkoutFormContent"),
        }
    return {
        "status": "failure",
        "errorCode": data.get("errorCode"),
        "errorMessage": data.get("errorMessage"),
    }


def retrieve_checkout_form(token):
    """
    Call Iyzico Checkout Form Retrieve with the token from callback.
    Trust only this result for success/failure; do not rely on callback query params.
    """
    options = get_options()
    if not options["api_key"] or not options["secret_key"]:
        raise ValueError("IYZICO_API_KEY and IYZICO_SECRET_KEY must be set")

    request = {
        "locale": "tr",
        "token": token,
    }

    checkout_form_result = iyzipay.CheckoutForm().retrieve(request, options)
    data = json.loads(checkout_form_result.read().decode("utf-8"))

    # Iyzico bazen PascalCase döndürüyor; ikisini de kabul et
    status = (data.get("status") or data.get("Status") or "").strip()
    payment_id = data.get("paymentId") or data.get("PaymentId") or ""
    conversation_id = data.get("conversationId") or data.get("ConversationId") or ""

    return {
        "status": status,
        "paymentId": payment_id,
        "conversationId": conversation_id,
        "price": data.get("price") or data.get("Price"),
        "paidPrice": data.get("paidPrice") or data.get("PaidPrice"),
        "currency": data.get("currency") or data.get("Currency"),
        "fraudStatus": data.get("fraudStatus") or data.get("FraudStatus"),
        "errorCode": data.get("errorCode") or data.get("ErrorCode"),
        "errorMessage": data.get("errorMessage") or data.get("ErrorMessage"),
    }
