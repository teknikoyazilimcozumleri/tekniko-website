from datetime import datetime

from django.conf import settings
from django.utils import timezone
from ninja import Router, Schema

from apps.accounts.jwt_utils import JWTAuthBearer

from .iyzico_subscription_client import (
    initialize_subscription_checkout,
    retrieve_subscription_checkout_result,
)
from .models import Subscription, SubscriptionPlan
from .result_urls import (
    build_subscription_callback_url,
    normalize_subscription_result_url,
    store_subscription_checkout_form,
    store_subscription_result_url,
)

router = Router(tags=["subscriptions"])


class SubscriptionPlanOutput(Schema):
    id: int
    name: str
    slug: str
    description: str
    price: str
    currency: str
    interval: str


class SubscriptionInitializeInput(Schema):
    plan_id: int
    callback_url: str | None = None
    return_url: str | None = None


class SubscriptionInitializeOutput(Schema):
    subscription_id: str
    token: str
    payment_page_url: str
    checkout_form_content: str | None = None


class SubscriptionCompleteInput(Schema):
    token: str


class SubscriptionOutput(Schema):
    id: str
    plan: dict
    status: str
    status_display: str
    iyzico_subscription_reference_code: str | None = None
    current_period_start: str | None = None
    current_period_end: str | None = None


def _to_iso(dt):
    return dt.isoformat() if dt else None


def _customer_and_address(user):
    name = getattr(user, "first_name", None) or "User"
    surname = getattr(user, "last_name", None) or "Name"
    email = getattr(user, "email", None) or "user@example.com"
    return {
        "name": name,
        "surname": surname,
        "email": email,
        "gsm_number": "+905350000000",
        "identity_number": "11111111111",
        "billing_address": "Address",
        "billing_contact_name": f"{name} {surname}",
        "billing_city": "Istanbul",
        "billing_country": "Turkey",
        "billing_zip_code": "34000",
    }


@router.get("/subscriptions/plans/", auth=JWTAuthBearer(), response=list[SubscriptionPlanOutput])
def subscription_plans(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("sort_order", "name")
    return [
        {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "price": str(p.price),
            "currency": p.currency,
            "interval": p.interval,
        }
        for p in plans
    ]


@router.post(
    "/subscriptions/checkout/initialize/",
    auth=JWTAuthBearer(),
    response={200: SubscriptionInitializeOutput, 400: dict, 404: dict},
)
def subscription_checkout_initialize(request, payload: SubscriptionInitializeInput):
    plan = SubscriptionPlan.objects.filter(pk=payload.plan_id, is_active=True).first()
    if not plan:
        return 404, {"detail": "Plan not found"}
    if not plan.iyzico_pricing_plan_reference_code:
        return 400, {"detail": "Selected plan is not mapped to Iyzico yet."}

    callback_url = build_subscription_callback_url(request)
    result_url = normalize_subscription_result_url(payload.return_url)

    customer = _customer_and_address(request.auth)
    result, full_response = initialize_subscription_checkout(
        pricing_plan_reference_code=plan.iyzico_pricing_plan_reference_code,
        callback_url=callback_url,
        customer_name=customer["name"],
        customer_surname=customer["surname"],
        email=customer["email"],
        gsm_number=customer["gsm_number"],
        identity_number=customer["identity_number"],
        billing_address=customer["billing_address"],
        billing_contact_name=customer["billing_contact_name"],
        billing_city=customer["billing_city"],
        billing_country=customer["billing_country"],
        billing_zip_code=customer["billing_zip_code"],
        subscription_initial_status="ACTIVE",
    )
    if result is None:
        return 400, {"detail": full_response.get("errorMessage", "Subscription initialize failed")}

    token = result.get("token")
    if not token:
        return 400, {"detail": "Iyzico did not return a token"}
    store_subscription_result_url(token, result_url)
    store_subscription_checkout_form(token, result.get("checkoutFormContent") or "")

    payment_page_url = result.get("paymentPageUrl") or ""
    if not payment_page_url:
        payment_page_url = request.build_absolute_uri(f"/subscriptions/checkout/form/public/?tid={token}")

    subscription = Subscription.objects.create(
        user=request.auth,
        plan=plan,
        status=Subscription.Status.PENDING,
        iyzico_subscription_reference_code="",
        subscription_checkout_token=token,
    )
    return 200, {
        "subscription_id": str(subscription.id),
        "token": token,
        "payment_page_url": payment_page_url,
        "checkout_form_content": result.get("checkoutFormContent"),
    }


@router.post(
    "/subscriptions/checkout/complete/",
    auth=JWTAuthBearer(),
    response={200: SubscriptionOutput, 400: dict, 404: dict},
)
def subscription_checkout_complete(request, payload: SubscriptionCompleteInput):
    subscription = Subscription.objects.filter(
        user=request.auth,
        subscription_checkout_token=payload.token,
    ).first()
    if not subscription:
        return 404, {"detail": "Pending subscription not found for this token"}

    result, full_response = retrieve_subscription_checkout_result(payload.token)
    if result is None:
        subscription.status = Subscription.Status.FAILED
        subscription.save(update_fields=["status", "updated_at"])
        return 400, {"detail": full_response.get("errorMessage", "Subscription result could not be retrieved")}

    status_str = (result.get("subscriptionStatus") or "").upper()
    reference_code = result.get("referenceCode")
    start_ts = result.get("startDate")
    end_ts = result.get("endDate")
    is_success = status_str == "ACTIVE" and bool(reference_code)

    if is_success:
        Subscription.objects.filter(
            user=request.auth,
            status=Subscription.Status.ACTIVE,
        ).exclude(pk=subscription.pk).update(status=Subscription.Status.CANCELLED, updated_at=timezone.now())
        subscription.status = Subscription.Status.ACTIVE
        subscription.iyzico_subscription_reference_code = reference_code
    else:
        subscription.status = Subscription.Status.FAILED

    if start_ts:
        try:
            subscription.current_period_start = datetime.utcfromtimestamp(start_ts / 1000.0)
        except (TypeError, OSError, ValueError):
            subscription.current_period_start = None
    if end_ts:
        try:
            subscription.current_period_end = datetime.utcfromtimestamp(end_ts / 1000.0)
        except (TypeError, OSError, ValueError):
            subscription.current_period_end = None

    subscription.subscription_checkout_token = ""
    subscription.save(
        update_fields=[
            "status",
            "iyzico_subscription_reference_code",
            "current_period_start",
            "current_period_end",
            "subscription_checkout_token",
            "updated_at",
        ]
    )
    return 200, {
        "id": str(subscription.id),
        "plan": {
            "name": subscription.plan.name,
            "price": str(subscription.plan.price),
            "currency": subscription.plan.currency,
        },
        "status": subscription.status,
        "status_display": subscription.get_status_display(),
        "iyzico_subscription_reference_code": subscription.iyzico_subscription_reference_code,
        "current_period_start": _to_iso(subscription.current_period_start),
        "current_period_end": _to_iso(subscription.current_period_end),
    }


@router.get("/subscriptions/my/", auth=JWTAuthBearer(), response=list[SubscriptionOutput])
def my_subscriptions(request):
    subscriptions = Subscription.objects.filter(user=request.auth).select_related("plan").order_by("-updated_at")
    return [
        {
            "id": str(s.id),
            "plan": {
                "name": s.plan.name,
                "price": str(s.plan.price),
                "currency": s.plan.currency,
            },
            "status": s.status,
            "status_display": s.get_status_display(),
            "iyzico_subscription_reference_code": s.iyzico_subscription_reference_code,
            "current_period_start": _to_iso(s.current_period_start),
            "current_period_end": _to_iso(s.current_period_end),
        }
        for s in subscriptions
    ]
