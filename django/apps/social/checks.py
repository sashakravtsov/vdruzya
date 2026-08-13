from django.core.checks import Error, Tags, Warning, register
from django.conf import settings


@register(Tags.security, deploy=True)
def check_secret_and_hosts(app_configs, **kwargs):
    errs = []
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errs.append(Error("SECRET_KEY too short", id="social.E001"))
    if settings.DEBUG:
        errs.append(Warning("DEBUG is True", id="social.W001"))
    return errs


@register(Tags.caches, deploy=True)
def check_redis_cache(app_configs, **kwargs):
    from django.core.cache import cache
    try:
        cache.set("djcheck", 1, 5)
        if cache.get("djcheck") != 1:
            return [Error("Redis cache roundtrip failed", id="social.E002")]
    except Exception as exc:
        return [Error(f"Redis unavailable: {exc}", id="social.E002")]
    return []


@register(Tags.compatibility, deploy=True)
def check_media_s3(app_configs, **kwargs):
    from django.conf import settings
    from django.core.files.storage import default_storage
    if getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""):
        name = default_storage.__class__.__name__
        if "S3" not in name:
            return [Warning("MEDIA_DISK=s3 expected but storage is " + name, id="social.W002")]
        if not getattr(settings, "AWS_URL", ""):
            return [Warning("AWS_URL empty — media URLs may be wrong", id="social.W003")]
    return []
