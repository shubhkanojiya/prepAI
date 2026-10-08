"""Production-readiness warnings shown by `manage.py check --deploy`."""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def production_services_check(app_configs, **kwargs):
    warnings = []
    if settings.EMAIL_BACKEND.endswith("console.EmailBackend"):
        warnings.append(Warning(
            "EMAIL_BACKEND is the console backend, so password-reset emails are never delivered.",
            hint="Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend and the EMAIL_* settings.",
            id="prepai.W001"))
    if settings.CACHES["default"]["BACKEND"].endswith("LocMemCache"):
        warnings.append(Warning(
            "No REDIS_URL: rate limits and caches are per process and reset on every restart.",
            hint="Set REDIS_URL so throttles are shared across workers.",
            id="prepai.W002"))
    if settings.STORAGE_BACKEND == "local":
        warnings.append(Warning(
            "STORAGE_BACKEND=local: uploaded images under /media/ are not served when DEBUG is off.",
            hint="Use STORAGE_BACKEND=s3 (works with Cloudflare R2) or serve /media/ from the web server.",
            id="prepai.W003"))
    return warnings
