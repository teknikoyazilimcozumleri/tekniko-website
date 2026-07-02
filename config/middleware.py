"""
Middleware that forces the request host from BASE_URL.

When BASE_URL is set (e.g. http://localhost:8000), this ensures
request.get_host() and thus request.build_absolute_uri() use that host
(including port). Fixes OAuth redirect_uri being built as http://localhost/...
instead of http://localhost:8000/... when the browser or proxy sends
Host: localhost without the port.
"""
from urllib.parse import urlparse


class BaseUrlHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        base_url = getattr(settings, "BASE_URL", "").strip().rstrip("/")
        if base_url:
            parsed = urlparse(base_url)
            if parsed.netloc:
                request.META["HTTP_HOST"] = parsed.netloc
        return self.get_response(request)
