import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def env(name: str, default=None):
    return os.environ.get(name, default)

def env_bool(name: str, default: bool = False) -> bool:
    value = env(name, None)
    if value is None:
        return default
    return str(value).lower() == "true"

SECRET_KEY = env("DJANGO_SECRET_KEY", "change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS", "").split(",") if env("DJANGO_ALLOWED_HOSTS") else []

CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if env("DJANGO_CSRF_TRUSTED_ORIGINS") else []
DEFAULT_SITE_DOMAIN = env("DJANGO_SITE_DOMAIN", "localhost")
DEFAULT_SITE_NAME = env("DJANGO_SITE_NAME", "localhost")

INSTALLED_APPS = [
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
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "core",
    "users",
    "courses",
    "purchases",
    "progress",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "app.wsgi.application"

if env("USE_SQLITE_FOR_TESTS", "False").lower() == "true":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "postgres"),
            "USER": env("POSTGRES_USER", "postgres"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = env("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
# Source static files (e.g. legal docs) live under /app/app/static
STATICFILES_DIRS = [BASE_DIR / "static"]
# Храним статику/медиа на верхнем уровне проекта (/app/static, /app/media),
# чтобы их можно было монтировать в контейнеры nginx/web.
STATIC_ROOT = BASE_DIR.parent / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR.parent / "media"

MAX_UPLOAD_SIZE = int(env("MAX_UPLOAD_SIZE", 20 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

SITE_ID = int(env("SITE_ID", 1))

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_SIGNUP_ENABLED = False
ACCOUNT_LOGIN_METHODS = {"email"}
# align signup fields with login method to avoid account.W001
ACCOUNT_SIGNUP_FIELDS = ["email*"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("ANON_THROTTLE_RATE", "100/day"),
        "user": env("USER_THROTTLE_RATE", "1000/day"),
        "auth": env("AUTH_THROTTLE_RATE", "20/min"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(seconds=int(env("JWT_ACCESS_TTL", 3600))),
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=int(env("JWT_REFRESH_TTL", 86400))),
    "SIGNING_KEY": env("JWT_SECRET_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "UstaBIM API",
    "DESCRIPTION": "API для онлайн-платформы обучения Revit",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

CORS_ALLOWED_ORIGINS = env("DJANGO_CORS_ALLOWED_ORIGINS", "").split(",") if env("DJANGO_CORS_ALLOWED_ORIGINS") else []
CORS_ALLOW_CREDENTIALS = True

USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", False)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("USE_SECURE_PROXY_HEADER", False) else None

# Security (defaults assume HTTPS in production)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", not DEBUG)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", not DEBUG)
SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", "same-origin")

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", "")
GOOGLE_DEV_BYPASS_TOKEN = env("GOOGLE_DEV_BYPASS_TOKEN", "")
GOOGLE_REDIRECT_URI = env("GOOGLE_REDIRECT_URI", "")

# Finik payments
FINIK_BASE_URL = env("FINIK_BASE_URL", "https://api.acquiring.averspay.kg")
FINIK_API_KEY = env("FINIK_API_KEY", "")
FINIK_PRIVATE_PEM = env("FINIK_PRIVATE_PEM", "")
FINIK_PUBLIC_PEM = env("FINIK_PUBLIC_PEM", "")
FINIK_ACCOUNT_ID = env("FINIK_ACCOUNT_ID", "")
FINIK_MERCHANT_CATEGORY_CODE = env("FINIK_MERCHANT_CATEGORY_CODE", env("FINIK_MCC", ""))
FINIK_QR_NAME = env("FINIK_QR_NAME", "")
FINIK_REDIRECT_URL = env("FINIK_REDIRECT_URL", "")
FINIK_WEBHOOK_URL = env("FINIK_WEBHOOK_URL", "")
FINIK_WEBHOOK_SKEW_MS = int(env("FINIK_WEBHOOK_SKEW_MS", "300000"))
FINIK_TIMEOUT_SECONDS = int(env("FINIK_TIMEOUT_SECONDS", "15"))

LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[{levelname}] {asctime} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL},
        "django.request": {"handlers": ["console"], "level": LOG_LEVEL},
    },
}
