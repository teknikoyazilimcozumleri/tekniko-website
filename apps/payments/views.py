import socket
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.urls import reverse
from django.conf import settings

from apps.audit.models import AuditLog

from .iyzico_client import initialize_checkout_form, retrieve_checkout_form
from .models import Payment

# Para birimleri
ALLOWED_CURRENCIES = {"TRY", "USD", "EUR", "GBP", "CHF", "NOK"}


def _build_callback_url(request, path: str) -> str:
    callback_host = (getattr(settings, "PAYMENT_CALLBACK_HOST", "") or "").strip().rstrip("/")
    if callback_host:
        return f"{callback_host}{path}"
    return request.build_absolute_uri(path)


def _append_result_params(base_url: str, success: bool, reason: str | None = None) -> str:
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["success"] = "true" if success else "false"
    if reason:
        query["reason"] = reason
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _default_result_url() -> str:
    return reverse("payment_result")


@csrf_exempt
def payment_callback(request):
    """
    Iyzico redirects here after payment. Use only the token to call Retrieve;
    do not trust query params like 'status'. Then update Payment and redirect to result.
    """
        
    token = request.GET.get("token") or (request.POST.get("token") if request.method == "POST" else None)
    if not token:
        return HttpResponseRedirect(_append_result_params(_default_result_url(), False, "missing_token"))

    try:
        result = retrieve_checkout_form(token)
    except Exception:
        return HttpResponseRedirect(_append_result_params(_default_result_url(), False, "retrieve_error"))

    conversation_id = result.get("conversationId")
    payment = Payment.objects.filter(conversation_id=conversation_id).first() if conversation_id else None

    
    if not payment and token:
        payment = Payment.objects.filter(iyzico_token=token).first()
    if not payment:
        return HttpResponseRedirect(_append_result_params(_default_result_url(), False, "payment_not_found"))

   # Başarı Durumu Kontrolü ve Kayıt 
    success = (result.get("status") or "").lower() == "success"
    payment.status = Payment.Status.SUCCESS if success else Payment.Status.FAILED
    payment.iyzico_payment_id = result.get("paymentId") or ""
    payment.iyzico_token = token
    payment.save(update_fields=["status", "iyzico_payment_id", "iyzico_token", "updated_at"])

    if not success:
        err_msg = result.get("errorMessage") or result.get("errorCode") or "payment_failed"
        request.session["payment_error_message"] = str(err_msg)[:500]

    # Audit log 
    AuditLog.objects.create(
        user=payment.user,
        action="PAYMENT_CALLBACK",
        path=request.path,
        metadata={"payment_id": str(payment.id), "status": payment.status},
    )
         
       
    # Başarılı/başarısız durumunu URL'e ekliyoruz
    result_base_url = payment.return_url or _default_result_url()
    reason = None if success else (result.get("errorMessage") or "payment_failed")
    return HttpResponseRedirect(_append_result_params(result_base_url, success, reason))

def payment_result(request):
    """Result page: success/failure, optional reason and Iyzico error message."""
    success = request.GET.get("success", "false").lower() == "true"
    reason = (request.GET.get("reason") or "").strip() or None
    error_message = request.session.pop("payment_error_message", None)
    return render(
        request,
        "payments/result.html",
        {"success": success, "reason": reason, "error_message": error_message},
    )


def _buyer_from_user(user):
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

@csrf_exempt
@login_required
@require_http_methods(["GET", "POST"])
def payment_start(request):
    """Start payment: show form (GET) or create payment and redirect to Iyzico (POST)."""
    if request.method == "GET":
        return render(request, "payments/start.html", {"default_amount": "10", "default_currency": "TRY"})

    amount_str = (request.POST.get("amount") or "10").strip()
    currency = (request.POST.get("currency") or "TRY").strip().upper() or "TRY"
    if currency not in ALLOWED_CURRENCIES:
        return render(
            request,
            "payments/start.html",
            {"error": "Desteklenmeyen para birimi.", "default_amount": amount_str, "default_currency": "TRY"},
        )
    try:
        price = float(amount_str)
    except ValueError:
        return render(
            request,
            "payments/start.html",
            {"error": "Geçersiz tutar.", "default_amount": amount_str, "default_currency": currency},
        )
    if price <= 0:
        return render(
            request,
            "payments/start.html",
            {"error": "Tutar pozitif olmalıdır.", "default_amount": amount_str, "default_currency": currency},
        )

    user = request.user
    conversation_id = str(uuid.uuid4())
    callback_url = _build_callback_url(request, "/payments/callback/")

    payment = Payment.objects.create(
        user=user,
        amount=price,
        currency=currency,
        status=Payment.Status.PENDING,
        conversation_id=conversation_id,
        metadata={},
        return_url="",
    )

    buyer = _buyer_from_user(user)
    address = _address_placeholder()
    basket_items = [
        {
            "id": "default-item",
            "name": "Payment",
            "category1": "General",
            "category2": "Payment",
            "itemType": "VIRTUAL",
            "price": str(price),
        }
    ]

    try:
        result = initialize_checkout_form(
            price=price,
            paid_price=price,
            currency=currency,
            callback_url=callback_url,
            conversation_id=conversation_id,
            buyer=buyer,
            shipping_address=address,
            billing_address=address,
            basket_items=basket_items,
        )
    except ValueError as e:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        return render(
            request,
            "payments/start.html",
            {"error": str(e) or "Iyzico yapılandırması eksik.", "default_amount": amount_str, "default_currency": currency},
        )
    except (socket.gaierror, OSError) as e:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        return render(
            request,
            "payments/start.html",
            {
                "error": "Iyzico API'ye bağlanılamadı (DNS/ağ). Docker kullanıyorsanız container'ın internet erişimini kontrol edin; yerel test için 'python manage.py runserver' deneyin.",
                "default_amount": amount_str,
                "default_currency": currency,
            },
        )

    AuditLog.objects.create(
        user=user,
        action="PAYMENT_INITIALIZE",
        path=request.path,
        metadata={"payment_id": str(payment.id), "status": payment.status, "conversation_id": conversation_id},
    )

    if result.get("status") != "success":
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        return render(
            request,
            "payments/start.html",
            {"error": result.get("errorMessage", "Ödeme başlatılamadı."), "default_amount": amount_str, "default_currency": currency},
        )

    payment.iyzico_token = result.get("token", "")
    payment.save(update_fields=["iyzico_token", "updated_at"])

    payment_page_url = result.get("paymentPageUrl") or result.get("checkoutFormContent") or ""
    if not payment_page_url and result.get("token"):
        payment_page_url = f"https://sandbox-merchant.iyzipay.com/checkout/form/auth?token={result['token']}"
    if payment_page_url:
        return HttpResponseRedirect(payment_page_url)
    return render(
        request,
        "payments/start.html",
        {"error": "Ödeme sayfası alınamadı.", "default_amount": amount_str, "default_currency": currency},
    )