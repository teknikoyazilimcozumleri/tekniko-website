from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    BASE_URL=(str, ""),
)
environ.Env.read_env(BASE_DIR / ".env")


BASE_URL = env("BASE_URL", default="").rstrip("/")

SECRET_KEY = env("SECRET_KEY", default="change-this-in-production")
DEBUG = env("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost", "testserver", "0.0.0.0"])
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://0.0.0.0:8000",
        "https://0.0.0.0",
    ],
)
USE_X_FORWARDED_PROTO = env.bool("USE_X_FORWARDED_PROTO", default=False)
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
)
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.mfa",
    "apps.accounts",
    "apps.rbac",
    "apps.audit",
    "apps.payments",
    "apps.subscriptions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "config.middleware.BaseUrlHostMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "apps.accounts.socialapp_sync.GoogleSocialAppSyncMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.google_oauth_available",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# DEBUG'ta manifest gerekmez; collectstatic olmadan da static'ler çalışır
STATICFILES_STORAGE = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# Email (e.g. password reset): logs to console in development; use SMTP in production
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@tyc.local")

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME_MINUTES": 1,
    "REFRESH_TOKEN_LIFETIME_DAYS": 7,
}

LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_SIGNUP_REDIRECT_URL = "/"

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")

ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"

ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email", "password1*", "password2*"]
ACCOUNT_SESSION_REMEMBER = None
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_LOGOUT_ON_GET = True

SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_FORMS = {
    "signup": "apps.accounts.forms.SocialSignupForm",
}
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
        },
        "OAUTH_PKCE_ENABLED": True,
    }
}

MFA_SUPPORTED_TYPES = ["recovery_codes", "totp"]
MFA_TOTP_ISSUER = "TYC"
MFA_RECOVERY_CODE_COUNT = 10
MFA_ALLOW_UNVERIFIED_EMAIL = False

# --- IYZICO PAYMENT (Checkout Form) ---
# Sandbox: https://sandbox-merchant.iyzipay.com ; Production: https://merchant.iyzico.com
IYZICO_API_KEY = env("IYZICO_API_KEY", default="")
IYZICO_SECRET_KEY = env("IYZICO_SECRET_KEY", default="")
IYZICO_BASE_URL = env("IYZICO_BASE_URL", default="sandbox-api.iyzipay.com")
# Callback base URL for Iyzico redirect (must be reachable from the internet).
# Ngrok: set NGROK_PUBLIC_URL=https://xxx.ngrok.io (no trailing slash) in .env
PAYMENT_CALLBACK_HOST = (env("PAYMENT_CALLBACK_HOST", default="") or env("NGROK_PUBLIC_URL", default="")).strip().rstrip("/") or ""
# Frontend application base URL used after backend callback finishes.
FRONTEND_APP_URL = env("FRONTEND_APP_URL", default="http://localhost:5174").strip().rstrip("/")
# Optional: Iyzico Merchant ID for subscription webhook X-IYZ-SIGNATURE-V3 verification (from merchant panel)
IYZICO_MERCHANT_ID = env("IYZICO_MERCHANT_ID", default="")

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    if USE_X_FORWARDED_PROTO:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")