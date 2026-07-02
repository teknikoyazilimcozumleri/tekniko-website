"""
Context processors for templates.
"""


def google_oauth_available(request):
    """
    Expose whether Google OAuth is configured so the login/signup pages
    can show the Google login button only when it will work.
    When GOOGLE_CLIENT_ID is unset (e.g. local dev), the button is hidden to avoid 500.
    """
    from django.conf import settings

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "").strip()
    return {
        "google_oauth_available": bool(client_id),
        "google_client_id": client_id,
    }
