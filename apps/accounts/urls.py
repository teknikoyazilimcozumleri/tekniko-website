from django.urls import include, path
from django.views.generic import RedirectView

from .views import (
    LoginViewWithEmailOtp,
    SocialSignupView,
    VerifyEmailOtpView,
    home_page,
    about_page,
    contact_page,
    esentre_page,
    konutarsiv_page,
    software_templates_page,
    profile_page,
    services_page,
    products_page,
)

accounts_urlpatterns = [
    path("verify-email-otp/", VerifyEmailOtpView.as_view(), name="verify_email_otp"),
    path("login/", LoginViewWithEmailOtp.as_view(), name="account_login"),
    path("3rdparty/signup/", SocialSignupView.as_view(), name="socialaccount_signup"),
    path("", include("allauth.urls")),
]

urlpatterns = [
    path("", home_page, name="home"),
    path("about/", about_page, name="about"),
    path("services/", services_page, name="services"),
    path("profile/", profile_page, name="profile"),
    path("products/", products_page, name="products"),
    path("products/esentre/", esentre_page, name="esentre"),
    path("products/konutarsiv/", konutarsiv_page, name="konutarsiv"),
    path("products/software-templates/", software_templates_page, name="software_templates"),
    path("contact/", contact_page, name="contact"),
    path(
        "login/",
        RedirectView.as_view(pattern_name="account_login", permanent=False),
        name="login_page",
    ),
    path(
        "register/",
        RedirectView.as_view(pattern_name="account_signup", permanent=False),
        name="register_page",
    ),
    path(
        "logout/",
        RedirectView.as_view(pattern_name="account_logout", permanent=False),
        name="logout_page",
    ),
    path(
        "reset/",
        RedirectView.as_view(pattern_name="account_reset_password", permanent=False),
        name="password_reset_request",
    ),
    path("accounts/", include(accounts_urlpatterns)),
]
