import uuid

from django.conf import settings
from ninja import Router, Schema

from apps.accounts.jwt_utils import JWTAuthBearer
from apps.audit.models import AuditLog

from .iyzico_client import initialize_checkout_form
from .models import Payment

router = Router(tags=["payments"])


class CheckoutInitializeInput(Schema):
    price: str
    currency: str = "TRY"
    basket_id: str | None = None
    return_url: str | None = None


class CheckoutInitializeOutput(Schema):
    payment_id: str
    payment_page_url: str
    token: str | None = None


class PaymentDetailOutput(Schema):
    id: str
    status: str
    amount: str
    currency: str


def _buyer_from_user(user):
    """Build Iyzico buyer dict from user (placeholder where needed)."""
    return {
        "id": str(user.id),
        "name": getattr(user, "first_name", None) or "User",
        "surname": getattr(user, "last_name", None) or "Name",
        "gsmNumber": "+905350000000",
        "email": getattr(user, "email", None) or "user@example.com",
        "identityNumber": "11111111111",
        "registrationAddress": "Address",
        "ip": "85.34.78.112",
        "city": "Istanbul",
        "country": "Turkey",
        "zipCode": "34000",
    }


def _address_placeholder():
    return {
        "contactName": "User",
        "city": "Istanbul",
        "country": "Turkey",
        "address": "Address",
        "zipCode": "34000",
    }


def _default_basket_item(price, currency):
    return [
        {
            "id": "default-item",
            "name": "Payment",
            "category1": "General",
            "category2": "Payment",
            "itemType": "VIRTUAL",
            "price": str(price),
        }
    ]


@router.post(
    "/payments/checkout/initialize/",
    auth=JWTAuthBearer(),
    response={200: CheckoutInitializeOutput, 400: dict},
)
def checkout_initialize(request, payload: CheckoutInitializeInput):
    """Create a pending Payment and return Iyzico checkout page URL. Use conversation_id for idempotency."""
    user = request.auth
    try:
        price = float(payload.price)
    except (TypeError, ValueError):
        return 400, {"detail": "Invalid price"}
    if price <= 0:
        return 400, {"detail": "Price must be positive"}

    conversation_id = str(uuid.uuid4())
    if settings.PAYMENT_CALLBACK_HOST:
        callback_url = f"{settings.PAYMENT_CALLBACK_HOST.rstrip('/')}/payments/callback/"
    else:
        callback_url = request.build_absolute_uri("/payments/callback/")

    payment = Payment.objects.create(
        user=user,
        amount=price,
        currency=payload.currency,
        status=Payment.Status.PENDING,
        conversation_id=conversation_id,
        metadata={"basket_id": payload.basket_id} if payload.basket_id else {},
        return_url=payload.return_url or "",
    )

    buyer = _buyer_from_user(user)
    address = _address_placeholder()
    basket_items = _default_basket_item(price, payload.currency)

    result = initialize_checkout_form(
        price=price,
        paid_price=price,
        currency=payload.currency,
        callback_url=callback_url,
        conversation_id=conversation_id,
        buyer=buyer,
        shipping_address=address,
        billing_address=address,
        basket_items=basket_items,
        basket_id=payload.basket_id,
    )

    AuditLog.objects.create(
        user=user,
        action="PAYMENT_INITIALIZE",
        path=request.path,
        metadata={
            "payment_id": str(payment.id),
            "status": payment.status,
            "conversation_id": conversation_id,
        },
    )

    if result.get("status") != "success":
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        return 400, {
            "detail": result.get("errorMessage", "Iyzico initialize failed"),
            "error_code": result.get("errorCode"),
        }

    payment.iyzico_token = result.get("token", "")
    payment.save(update_fields=["iyzico_token", "updated_at"])

    return 200, {
        "payment_id": str(payment.id),
        "payment_page_url": result.get("paymentPageUrl") or result.get("checkoutFormContent") or "",
        "token": result.get("token"),
    }


@router.get(
    "/payments/{payment_id}/",
    auth=JWTAuthBearer(),
    response={200: PaymentDetailOutput, 404: dict},
)
def payment_detail(request, payment_id: str):
    """Return payment status (own payments only)."""
    user = request.auth
    payment = Payment.objects.filter(id=payment_id, user=user).first()
    if not payment:
        return 404, {"detail": "Not found"}
    return 200, {
        "id": str(payment.id),
        "status": payment.status,
        "amount": str(payment.amount),
        "currency": payment.currency,
    }
