"""
One-time sync of Google SocialApp from settings (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET).
Runs on first request to avoid database access during AppConfig.ready().
"""

_sync_done = False


def ensure_google_socialapp():
    global _sync_done
    if _sync_done:
        return
    from django.conf import settings
    from django.db.utils import OperationalError, ProgrammingError

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", None)
    secret = getattr(settings, "GOOGLE_CLIENT_SECRET", None)
    if not client_id or not secret:
        _sync_done = True
        return

    try:
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site

        site = Site.objects.get(id=getattr(settings, "SITE_ID", 1))
        app, _created = SocialApp.objects.get_or_create(
            provider="google",
            defaults={"name": "Google", "client_id": client_id, "secret": secret},
        )
        updated = False
        if app.client_id != client_id:
            app.client_id = client_id
            updated = True
        if app.secret != secret:
            app.secret = secret
            updated = True
        if updated:
            app.save()
        if site not in app.sites.all():
            app.sites.add(site)
    except (OperationalError, ProgrammingError):
        pass
    except Exception:
        # Site.DoesNotExist or any other failure (e.g. tables not ready)
        pass
    _sync_done = True


class GoogleSocialAppSyncMiddleware:
    """Runs ensure_google_socialapp() once on first request (no DB access in ready())."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ensure_google_socialapp()
        return self.get_response(request)
