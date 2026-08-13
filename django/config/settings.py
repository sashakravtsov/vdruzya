from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(
    DEBUG=(bool, False),
    EMAIL_USE_TLS=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

_sk = env("SECRET_KEY")
SECRET_KEY = _sk.removeprefix("base64:") if _sk.startswith("base64:") else _sk
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = ["vdruzya.ru", "www.vdruzya.ru", "127.0.0.1", "localhost", "testserver"]
# Prefer CSRF_TRUSTED_ORIGINS (comma-list in .env); keep singular fallback for older envs.
_csrf_origins = [
    u.strip()
    for u in env.list("CSRF_TRUSTED_ORIGINS", default=[])
    if isinstance(u, str) and u.strip().startswith("http")
]
if not _csrf_origins:
    _one = env("CSRF_TRUSTED_ORIGIN", default="").strip()
    if _one.startswith("http"):
        _csrf_origins = [_one]
if not _csrf_origins:
    _csrf_origins = ["https://vdruzya.ru", "https://www.vdruzya.ru"]
CSRF_TRUSTED_ORIGINS = _csrf_origins

INSTALLED_APPS = [
    "daphne",
    "channels",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "django.contrib.sitemaps",
    "apps.accounts",
    "apps.social.apps.SocialConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "apps.social.context.classic",
        ],
    },
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", default="127.0.0.1"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.auth.BcryptBackend"]
APPEND_SLASH = False
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptPasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
LANGUAGES = [("ru", "Русский")]
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/storage/"
MEDIA_ROOT = Path("/var/www/projects/vdruzya.ru/storage/public")
FILE_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
# Multipart may include video files (streamed to temp disk above FILE_UPLOAD_MAX_MEMORY_SIZE).
DATA_UPLOAD_MAX_MEMORY_SIZE = 40 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
FFMPEG_BIN = env("FFMPEG_BIN", default="ffmpeg")

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_BUCKET", default="")
AWS_S3_ENDPOINT_URL = env("AWS_ENDPOINT", default="")
AWS_S3_REGION_NAME = env("AWS_DEFAULT_REGION", default="ru1")
AWS_URL = env("AWS_URL", default="").rstrip("/")
AWS_S3_CUSTOM_DOMAIN = AWS_URL.split("://", 1)[-1] if AWS_URL else ""
AWS_S3_URL_PROTOCOL = "https:"
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "public, max-age=604800"}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if env("MEDIA_DISK", default="local") == "s3" and AWS_ACCESS_KEY_ID and AWS_STORAGE_BUCKET_NAME:
    from botocore.client import Config as BotoConfig
    _s3_opts = {
        "access_key": AWS_ACCESS_KEY_ID,
        "secret_key": AWS_SECRET_ACCESS_KEY,
        "bucket_name": AWS_STORAGE_BUCKET_NAME,
        "endpoint_url": AWS_S3_ENDPOINT_URL or None,
        "region_name": AWS_S3_REGION_NAME,
        "addressing_style": "path",
        "signature_version": "s3v4",
        "default_acl": None,
        "querystring_auth": False,
        "file_overwrite": False,
        "object_parameters": AWS_S3_OBJECT_PARAMETERS,
        "client_config": BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    }
    if AWS_S3_CUSTOM_DOMAIN:
        _s3_opts["custom_domain"] = AWS_S3_CUSTOM_DOMAIN
        _s3_opts["url_protocol"] = "https:"
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": _s3_opts}
    if AWS_URL:
        MEDIA_URL = f"{AWS_URL}/"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "feed"
LOGOUT_REDIRECT_URL = "home"

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

REDIS_URL = f"redis://:{env('REDIS_PASSWORD', default='')}@{env('REDIS_HOST', default='127.0.0.1')}:{env('REDIS_PORT', default='6379')}/0"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
# Channels layer for app WebSockets (Redis logical DB 2).
CHANNEL_REDIS_URL = REDIS_URL.rsplit("/", 1)[0] + "/2"
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [CHANNEL_REDIS_URL], "capacity": 1500, "expiry": 30},
    },
}

EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="").strip("'\"")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="").strip("'\"")
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=EMAIL_PORT == 465)
EMAIL_USE_TLS = False if EMAIL_USE_SSL else env.bool("EMAIL_USE_TLS", default=EMAIL_PORT == 587)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=20)
_from = env("DEFAULT_FROM_EMAIL", default="noreply@vdruzya.ru").strip("'\"")
DEFAULT_FROM_EMAIL = _from if "<" in _from else f"ВДрузья <{_from}>"
SERVER_EMAIL = env("SERVER_EMAIL", default=_from).strip("'\"")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"

LEGAL_OPERATOR_NAME = env("LEGAL_OPERATOR_NAME", default="").strip("'\"")
LEGAL_OPERATOR_SHORT = env("LEGAL_OPERATOR_SHORT", default="").strip("'\"")
LEGAL_INN = env("LEGAL_INN", default="").strip("'\"")
LEGAL_KPP = env("LEGAL_KPP", default="").strip("'\"")
LEGAL_OGRN = env("LEGAL_OGRN", default="").strip("'\"")
LEGAL_ADDRESS = env("LEGAL_ADDRESS", default="").strip("'\"")
LEGAL_SUPPORT_EMAIL = env("LEGAL_SUPPORT_EMAIL", default="").strip("'\"")
LEGAL_SUPPORT_PHONE = env("LEGAL_SUPPORT_PHONE", default="").strip("'\"")
LEGAL_BANK_NAME = env("LEGAL_BANK_NAME", default="").strip("'\"")
LEGAL_BANK_ACCOUNT = env("LEGAL_BANK_ACCOUNT", default="").strip("'\"")
LEGAL_BANK_BIK = env("LEGAL_BANK_BIK", default="").strip("'\"")
LEGAL_BANK_CORR = env("LEGAL_BANK_CORR", default="").strip("'\"")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CSRF_FAILURE_VIEW = "apps.social.views_meta.csrf_failure"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
