import uuid
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from django.http import JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from .iyzico_subscription_client import (
    initialize_subscription_checkout,
    retrieve_subscription_checkout_result,
)
from .models import Subscription, SubscriptionPlan
from .result_urls import (
    build_subscription_callback_url,
    build_subscription_result_url,
    pop_subscription_checkout_form,
    pop_subscription_result_url,
)


def _build_callback_url(request, path: str) -> str:
    if path == "/subscriptions/callback/":
        return build_subscription_callback_url(request)
    callback_host = (getattr(settings, "PAYMENT_CALLBACK_HOST", "") or "").strip().rstrip("/")
    if callback_host:
        return f"{callback_host}{path}"
    return request.build_absolute_uri(path)


def _build_frontend_result_url(success: bool, reason: str | None = None) -> str:
    return build_subscription_result_url(success, reason)


def _build_backend_result_url(success: bool, reason: str | None = None) -> str:
    parts = urlsplit(reverse("subscriptions:result"))
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["success"] = "true" if success else "false"
    if reason:
        query["reason"] = reason
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def plan_list(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    data = []
    for p in plans:
        data.append({
            "id": p.id,
            "name": str(p.name),
            "price": str(p.price),
            "description": p.description or "",
            "currency": "TRY", 
            "features": [], 
            "iyzico_pricing_plan_reference_code": p.iyzico_pricing_plan_reference_code or ""
        })
    return JsonResponse(data, safe=False)

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


@login_required
@require_http_methods(["GET", "POST"])
def checkout_start(request, plan_id):
    """Start subscription: create Subscription (PENDING), call Iyzico initialize, show checkout form or redirect."""
    plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
    if not plan.iyzico_pricing_plan_reference_code:
        return render(
            request,
            "subscriptions/plan_list.html",
            {"plans": SubscriptionPlan.objects.filter(is_active=True), "error": "Bu plan henüz Iyzico ile eşleştirilmedi. Yönetici setup_subscription_plans komutunu çalıştırsın."},
        )

    callback_url = _build_callback_url(request, "/subscriptions/callback/")

    user = request.user
    cust = _customer_and_address(user)
    conversation_id = str(uuid.uuid4())

    result, full_response = initialize_subscription_checkout(
        pricing_plan_reference_code=plan.iyzico_pricing_plan_reference_code,
        callback_url=callback_url,
        customer_name=cust["name"],
        customer_surname=cust["surname"],
        email=cust["email"],
        gsm_number=cust["gsm_number"],
        identity_number=cust["identity_number"],
        billing_address=cust["billing_address"],
        billing_contact_name=cust["billing_contact_name"],
        billing_city=cust["billing_city"],
        billing_country=cust["billing_country"],
        billing_zip_code=cust["billing_zip_code"],
        subscription_initial_status="ACTIVE",
        conversation_id=conversation_id,
    )

    if result is None:
        return render(
            request,
            "subscriptions/plan_list.html",
            {
                "plans": SubscriptionPlan.objects.filter(is_active=True),
                "error": full_response.get("errorMessage", "Abonelik başlatılamadı."),
            },
        )

    token = result.get("token")
    checkout_form_content = result.get("checkoutFormContent") or ""


    checkouts = dict(request.session.get("subscription_checkouts") or {})
    checkouts[token] = plan_id
    request.session["subscription_checkouts"] = checkouts

        # --- DOĞRU VE GÜVENLİ YÖNLENDİRME ---
    if checkout_form_content and token:
        
        form_by_token = dict(request.session.get("subscription_checkout_form") or {})
        form_by_token[token] = {"html": checkout_form_content}
        request.session["subscription_checkout_form"] = form_by_token
        
        
        return HttpResponseRedirect(f"/subscriptions/checkout/form/?tid={token}")

  
    return HttpResponseRedirect(_build_backend_result_url(False, "form_not_found"))


@login_required
@require_GET
def checkout_form(request):
    """Display the Iyzico subscription checkout form (HTML from session, keyed by token)."""
    tid = request.GET.get("tid")
    if not tid:
        return HttpResponseRedirect("/subscriptions/")
    form_by_token = request.session.get("subscription_checkout_form") or {}
    form_data = form_by_token.get(tid) if isinstance(form_by_token, dict) else None
    if not form_data:
        return HttpResponseRedirect("/subscriptions/")
    html = form_data.get("html", "")
    if not html:
        return HttpResponseRedirect("/subscriptions/")
    form_by_token = dict(form_by_token)
    del form_by_token[tid]
    request.session["subscription_checkout_form"] = form_by_token if form_by_token else None
    return HttpResponse(html, content_type="text/html; charset=utf-8")


@require_GET
def public_checkout_form(request):
    """Display cached subscription checkout form for API-driven flow."""
    tid = (request.GET.get("tid") or "").strip()
    if not tid:
        return HttpResponseRedirect("/subscriptions/result/?success=false&reason=missing_token")

    html = pop_subscription_checkout_form(tid)
    if not html:
        return HttpResponseRedirect("/subscriptions/result/?success=false&reason=session_expired")

    return HttpResponse(html, content_type="text/html; charset=utf-8")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def subscription_callback(request):
    """Iyzico redirects here after subscription checkout. Create Subscription only here (after payment); plan_id from session."""
    token = request.GET.get("token") or (request.POST.get("token") if request.method == "POST" else None)
    if not token:
        return HttpResponseRedirect(_build_backend_result_url(False, "missing_token"))

    checkouts = dict(request.session.get("subscription_checkouts") or {})
    plan_id = checkouts.pop(token, None)
    request.session["subscription_checkouts"] = checkouts if checkouts else None

    pending_subscription = Subscription.objects.filter(
        subscription_checkout_token=token,
        status=Subscription.Status.PENDING,
    ).select_related("plan", "user").first()

    if plan_id is None and pending_subscription is None:
        return HttpResponseRedirect(_build_backend_result_url(False, "session_expired"))

    if pending_subscription is not None:
        subscription = pending_subscription
        plan = subscription.plan
        user = subscription.user
    else:
        plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return HttpResponseRedirect(reverse("login") + f"?next={reverse('subscriptions:plan_list')}")
        subscription = None

    result, full_response = retrieve_subscription_checkout_result(token)
    result_url = pop_subscription_result_url(token)

    if result is None:
        if subscription is None:
            Subscription.objects.create(
                user=user,
                plan=plan,
                status=Subscription.Status.FAILED,
                iyzico_subscription_reference_code="",
            )
        else:
            subscription.status = Subscription.Status.FAILED
            subscription.subscription_checkout_token = ""
            subscription.save(update_fields=["status", "subscription_checkout_token", "updated_at"])
        error_msg = (full_response.get("errorMessage") or "retrieve_error")[:500]
        return HttpResponseRedirect(_build_frontend_result_url(False, error_msg) if not result_url else build_subscription_result_url(False, error_msg, result_url))
    
    # --- Başarı Durumu Kontrolü ve Kayıt ---
    ref_code = result.get("referenceCode")
    status_str = (result.get("subscriptionStatus") or "").upper()
    start_ts = result.get("startDate")
    end_ts = result.get("endDate")

    success = status_str == "ACTIVE" and bool(ref_code)

    if success:
        Subscription.objects.filter(
            user=user,
            status=Subscription.Status.ACTIVE,
        ).exclude(pk=getattr(subscription, "pk", None)).update(status=Subscription.Status.CANCELLED, updated_at=timezone.now())

        if subscription is None:
            subscription = Subscription(
                user=user,
                plan=plan,
            )
        subscription.status = Subscription.Status.ACTIVE
        subscription.iyzico_subscription_reference_code = ref_code
        if start_ts:
            try: subscription.current_period_start = datetime.utcfromtimestamp(start_ts / 1000.0)
            except: pass
        if end_ts:
            try: subscription.current_period_end = datetime.utcfromtimestamp(end_ts / 1000.0)
            except: pass
        subscription.subscription_checkout_token = ""
        subscription.save()
    else:
        if subscription is None:
            Subscription.objects.create(
                user=user,
                plan=plan,
                status=Subscription.Status.FAILED,
                iyzico_subscription_reference_code=ref_code or "",
            )
        else:
            subscription.status = Subscription.Status.FAILED
            subscription.iyzico_subscription_reference_code = ref_code or ""
            subscription.subscription_checkout_token = ""
            subscription.save(update_fields=["status", "iyzico_subscription_reference_code", "subscription_checkout_token", "updated_at"])

    reason = None if success else (full_response.get("errorMessage") or "subscription_failed")
    if result_url:
        return HttpResponseRedirect(build_subscription_result_url(success, reason, result_url))
    return HttpResponseRedirect(_build_frontend_result_url(success, reason))

@require_GET
def subscription_result(request):
    """Show success/failure after subscription callback."""
    success = request.GET.get("success", "false").lower() == "true"
    reason = (request.GET.get("reason") or "").strip() or None
    error_message = request.session.pop("subscription_error_message", None)
    return render(
        request,
        "subscriptions/result.html",
        {"success": success, "reason": reason, "error_message": error_message},
    )


from django.http import JsonResponse


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_subscriptions(request):
    subscriptions = Subscription.objects.filter(user=request.user).select_related("plan")
    data = []
    for s in subscriptions:
        st = str(s.status or "").lower()
        if st in ["aktif", "active"]: st = "active"
        data.append({
            "id": str(s.id),
            "plan_name": s.plan.name,
            "status": st,
            "price": str(s.plan.price)
        })
    return JsonResponse(data, safe=False)

   


def _verify_subscription_webhook_signature(payload, signature_v3):
    """Verify X-IYZ-SIGNATURE-V3 for subscription format."""
    import hashlib
    import hmac

    merchant_id = getattr(settings, "IYZICO_MERCHANT_ID", "") or ""
    secret_key = (settings.IYZICO_SECRET_KEY or "").encode("utf-8")
    event_type = payload.get("iyziEventType", "")
    sub_ref = payload.get("subscriptionReferenceCode", "")
    order_ref = payload.get("orderReferenceCode", "")
    customer_ref = payload.get("customerReferenceCode", "")
    message = f"{merchant_id}{settings.IYZICO_SECRET_KEY or ''}{event_type}{sub_ref}{order_ref}{customer_ref}"
    expected = hmac.new(secret_key, message.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_v3 or "")


@csrf_exempt
@require_http_methods(["POST"])
def subscription_webhook(request):
    """Iyzico subscription webhook: renewal success/failure."""
    try:
        import json as _json
        payload = _json.loads(request.body.decode("utf-8"))
    except Exception:
        return HttpResponse(status=400)
    sig = request.headers.get("X-IYZ-SIGNATURE-V3") or request.headers.get("x-iyz-signature-v3") or ""
    if getattr(settings, "IYZICO_MERCHANT_ID", None) and settings.IYZICO_SECRET_KEY:
        if not _verify_subscription_webhook_signature(payload, sig):
            return HttpResponse(status=401)
    event_type = payload.get("iyziEventType", "")
    sub_ref = payload.get("subscriptionReferenceCode", "")
    subscription = Subscription.objects.filter(iyzico_subscription_reference_code=sub_ref).first()
    if subscription:
        if event_type == "subscription.order.success":
            subscription.status = Subscription.Status.ACTIVE
            subscription.save(update_fields=["status", "updated_at"])
        elif event_type == "subscription.order.failure":
            subscription.status = Subscription.Status.PAST_DUE
            subscription.save(update_fields=["status", "updated_at"])
    return HttpResponse(status=200)
