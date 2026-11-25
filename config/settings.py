"""Django settings for the CHORD (new version) project."""

import os
from pathlib import Path

from django.contrib.messages import constants as messages
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable using explicit truthy values."""
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int = 0) -> int:
    """Read an integer environment variable and fail fast on invalid input."""
    return int(os.getenv(name, str(default)))


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.audit.apps.AuditConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.church.apps.ChurchConfig",
    "apps.members.apps.MembersConfig",
    "apps.worship.apps.WorshipConfig",
    "apps.songs.apps.SongsConfig",
    "apps.teams.apps.TeamsConfig",
    "apps.occasions.apps.OccasionsConfig",
    "apps.announcements.apps.AnnouncementsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.PasswordChangeRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.church.middleware.CurrentChurchMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Permissions come from the roles of a person's Membership in the Current
# Church (decision 0014; apps/accounts/backends.py).
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.ChurchRoleBackend"]

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
                "apps.church.context_processors.church",
                "apps.core.settings_menu.settings_menu",
                "apps.notifications.context_processors.notifications",
                "apps.occasions.context_processors.pending_requests",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Every form renders with Bootstrap markup; see apps/core/forms.py.
FORM_RENDERER = "apps.core.forms.ChordFormRenderer"

MESSAGE_TAGS = {messages.ERROR: "danger"}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "chord_newver_db"),
        "USER": os.getenv("DB_USER", "chord_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT")
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS")
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Uploads holding personal data; never served directly (apps/core/storage.py).
PRIVATE_MEDIA_ROOT = BASE_DIR / "protected_media"

# Email: printed to the console in development; set an SMTP backend in .env
# for real sending.
EMAIL_BACKEND = os.getenv(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 25)
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS")
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_DEFAULT_FROM_EMAIL", "chord@localhost")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Tests run with the network blocked and the keyword ML engine
# (apps/core/testing.py).
TEST_RUNNER = "apps.core.testing.ChordTestRunner"

# Song analysis (apps/songs/ml): "onnx" runs the downloaded models (fetch
# them with `manage.py download_models`); "keyword" is the light stand-in.
ML_ENGINE = os.getenv("ML_ENGINE", "onnx")
ML_MODELS_DIR = Path(os.getenv("ML_MODELS_DIR", BASE_DIR / "ml_models"))

# Spotify app credentials: the Client Credentials flow for track search, and
# the Authorization Code flow for each user's own account.
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
# The Fernet key that encrypts users' Spotify tokens (apps/songs/connections.py).
SPOTIFY_TOKEN_KEY = os.getenv("SPOTIFY_TOKEN_KEY", "")
# Where Spotify returns people after connecting; blank means the page's own
# address.
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "")

# LRCLIB asks every client to name itself: app, version and a homepage.
LRCLIB_USER_AGENT = os.getenv(
    "LRCLIB_USER_AGENT", "CHORD worship planner/0.4 (self-hosted)"
)
