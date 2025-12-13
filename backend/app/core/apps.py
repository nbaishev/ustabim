from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(ensure_site_and_socialapp, dispatch_uid="core.ensure_site_and_socialapp", weak=False)


def ensure_site_and_socialapp(**kwargs):
    """
    Ensure default Site matches env and SocialApp(Google) is created from env creds.
    Safe to run multiple times; skips if no env credentials.
    """
    from django.contrib.sites.models import Site
    from allauth.socialaccount.models import SocialApp

    # Update default site
    domain = getattr(settings, "DEFAULT_SITE_DOMAIN", "localhost")
    name = getattr(settings, "DEFAULT_SITE_NAME", domain)
    Site.objects.update_or_create(id=settings.SITE_ID, defaults={"domain": domain, "name": name})

    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
    client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "") or ""
    if not client_id or not client_secret:
        return

    social_app, _ = SocialApp.objects.get_or_create(
        provider="google",
        defaults={"name": "Google", "client_id": client_id, "secret": client_secret},
    )
    if (social_app.client_id != client_id) or (social_app.secret != client_secret):
        social_app.client_id = client_id
        social_app.secret = client_secret
        social_app.name = "Google"
        social_app.save(update_fields=["client_id", "secret", "name"])

    # Attach site if missing
    site = Site.objects.get(id=settings.SITE_ID)
    if site not in social_app.sites.all():
        social_app.sites.add(site)
