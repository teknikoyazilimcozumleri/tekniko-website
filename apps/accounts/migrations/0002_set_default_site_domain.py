from django.conf import settings
from django.db import migrations


def set_default_site_domain(apps, schema_editor):
    """
    Keep django.contrib.sites Site(id=1) in sync with BASE_URL.

    This ensures that django-allauth builds callback/redirect URLs with the
    correct host *and port* (e.g. localhost:8000), so Google OAuth redirects
    do not drop the :8000 part in local/dev environments.
    """

    Site = apps.get_model("sites", "Site")

    # Fallback to a sensible local default if BASE_URL is not set.
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000").rstrip("/")
    # Extract host:port from URL-like value.
    for prefix in ("http://", "https://"):
        if base_url.startswith(prefix):
            base_url = base_url[len(prefix) :]
            break

    if not base_url:
        # As a last resort, keep the existing value; nothing to do.
        return

    site, _ = Site.objects.get_or_create(id=getattr(settings, "SITE_ID", 1))
    site.domain = base_url
    site.name = base_url
    site.save()


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0002_alter_domain_unique"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(set_default_site_domain, migrations.RunPython.noop),
    ]

