from django.conf import settings
from django.contrib.auth import login
from django.contrib.messages import success
from django.core.mail import EmailMessage
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import FormView

from allauth.account.views import LoginView as AllauthLoginView
from allauth.socialaccount.views import SignupView as SocialSignupViewBase

from .forms import ContactForm
from .otp import create_and_send_otp, get_otp_expires_at, verify_otp


def home_page(request):
    return render(request, "landing_page.html")


def about_page(request):
    return render(request, "about_page.html")


def profile_page(request):
    return render(request, "account/profile.html")


def services_page(request):
    return render(request, "services_page.html")


def products_page(request):
    return render(request, "products_page.html")


def contact_page(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            service_label = dict(ContactForm.SERVICE_CHOICES).get(
                data["service_type"], "Belirtilmedi"
            )
            body = (
                f"Ad Soyad: {data['full_name']}\n"
                f"E-posta: {data['email']}\n"
                f"Şirket: {data['company'] or '—'}\n"
                f"Telefon: {data['phone'] or '—'}\n"
                f"Hizmet Türü: {service_label}\n\n"
                f"Mesaj:\n{data['message']}"
            )
            recipient = settings.CONTACT_EMAIL or settings.DEFAULT_FROM_EMAIL
            EmailMessage(
                subject=f"İletişim formu: {data['full_name']}",
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
                reply_to=[data["email"]],
            ).send(fail_silently=False)
            success(request, "Mesajınız alındı. En kısa sürede size dönüş yapacağız.")
            return redirect("contact")
    else:
        form = ContactForm()

    return render(request, "contact_page.html", {"form": form})

def esentre_page(request):
    return render(request, "esentre.html")


def konutarsiv_page(request):
    return render(request, "konutarsiv.html")


def software_templates_page(request):
    return render(request, "software_templates.html")


class LoginViewWithEmailOtp(AllauthLoginView):
    """
    On successful credential login, send email OTP and redirect to verify page.
    OAuth login is unchanged.
    """

    def form_valid(self, form):
        user = form.user
        token = create_and_send_otp(user)
        verify_url = reverse("verify_email_otp") + "?token=" + token
        redirect_field_name = getattr(settings, "REDIRECT_FIELD_NAME", "next")
        redirect_to = self.request.POST.get(redirect_field_name) or self.request.GET.get(
            redirect_field_name
        )
        if redirect_to:
            from urllib.parse import urlencode
            verify_url += "&" + urlencode({redirect_field_name: redirect_to})
        return redirect(verify_url)


class VerifyEmailOtpView(FormView):
    """Verify the 6-digit email OTP and complete login."""

    template_name = "account/verify_email_otp.html"
    success_url = None

    def get_form_class(self):
        from django import forms

        class VerifyOtpForm(forms.Form):
            code = forms.CharField(
                max_length=6,
                min_length=6,
                strip=True,
                widget=forms.TextInput(
                    attrs={
                        "autocomplete": "one-time-code",
                        "placeholder": "000000",
                        "inputmode": "numeric",
                        "pattern": "[0-9]*",
                    }
                ),
            )
        return VerifyOtpForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        token = self.request.GET.get("token") or self.request.POST.get("token", "")
        ctx["token"] = token
        ctx["redirect_field_name"] = getattr(settings, "REDIRECT_FIELD_NAME", "next")
        ctx["redirect_field_value"] = (
            self.request.GET.get(ctx["redirect_field_name"])
            or self.request.POST.get(ctx["redirect_field_name"], "")
        )
        expires_at = get_otp_expires_at(token) if token else None
        ctx["otp_expires_at"] = int(expires_at) if expires_at else None
        return ctx

    def get_success_url(self):
        redirect_field_name = getattr(settings, "REDIRECT_FIELD_NAME", "next")
        next_url = (
            self.request.GET.get(redirect_field_name)
            or self.request.POST.get(redirect_field_name)
        )
        return next_url or settings.LOGIN_REDIRECT_URL

    def form_valid(self, form):
        token = self.request.GET.get("token") or self.request.POST.get("token")
        code = form.cleaned_data.get("code", "")
        if not token:
            form.add_error(
                None,
                "Eksik veya geçersiz bağlantı. Lütfen giriş sayfasından tekrar deneyin.",
            )
            return self.form_invalid(form)
        user = verify_otp(token, code)
        if not user:
            form.add_error(
                None,
                "Kod geçersiz veya süresi dolmuş. Lütfen tekrar deneyin veya giriş sayfasından yeni kod isteyin.",
            )
            return self.form_invalid(form)
        login(
            self.request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        success(self.request, "Doğrulama kodu başarıyla onaylandı. Giriş yaptınız.")
        return redirect(self.get_success_url())

    def get(self, request, *args, **kwargs):
        if not request.GET.get("token"):
            return redirect(reverse("account_login"))
        return super().get(request, *args, **kwargs)


class SocialSignupView(SocialSignupViewBase):
    """Social (OAuth) signup view using our account template."""

    template_name = "account/social_account_signup.html"
