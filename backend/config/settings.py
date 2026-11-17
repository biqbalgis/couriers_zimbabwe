import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-pano-logistics-change-this-secret-before-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "django_filters", "drf_spectacular", "marketplace",
]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
if os.getenv("POSTGRES_DB"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("POSTGRES_DB"), "USER": os.getenv("POSTGRES_USER"), "PASSWORD": os.getenv("POSTGRES_PASSWORD"), "HOST": os.getenv("POSTGRES_HOST", "localhost"), "PORT": os.getenv("POSTGRES_PORT", "5432")}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
AUTH_USER_MODEL = "marketplace.User"
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "en-us"; TIME_ZONE = "Africa/Harare"; USE_I18N = True; USE_TZ = True
STATIC_URL = "static/"; STATIC_ROOT = BASE_DIR / "staticfiles"; MEDIA_URL = "/api/files/"; MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = [x for x in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if x]
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = (*default_headers, 'idempotency-key')
MIDDLEWARE.insert(MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')+1,'marketplace.audit_context.AdminAuditMiddleware')
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",), "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",), "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend", "rest_framework.filters.OrderingFilter", "rest_framework.filters.SearchFilter"), "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "DEFAULT_PAGINATION_CLASS": "marketplace.pagination.WorkspacePagination", "PAGE_SIZE": 50}
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(hours=8)}
SPECTACULAR_SETTINGS = {"TITLE": "Pano Logistics API", "VERSION": "1.0.0", "ENUM_NAME_OVERRIDES": {"UserRoleEnum":"marketplace.models.User.Role","RegistrationRoleEnum":["customer","rider","carrier"],"ParcelStatusEnum":"marketplace.models.Parcel.Status","TaskStatusEnum":"marketplace.models.Task.Status","ApprovalStatusEnum":"marketplace.models.ApprovalStatus","PaymentStatusEnum":"marketplace.models.Payment.Status"}}
PUBLIC_WEB_URL=os.getenv("PUBLIC_WEB_URL","http://localhost:5173").rstrip("/")
SMS_DELIVERY_MODE=os.getenv("SMS_DELIVERY_MODE","console" if DEBUG else "webhook")
SMS_WEBHOOK_URL=os.getenv("SMS_WEBHOOK_URL","")
SMS_WEBHOOK_TOKEN=os.getenv("SMS_WEBHOOK_TOKEN","")
HELPDESK_WEBHOOK_URL=os.getenv("HELPDESK_WEBHOOK_URL","")
HELPDESK_WEBHOOK_TOKEN=os.getenv("HELPDESK_WEBHOOK_TOKEN","")
HELPDESK_PORTAL_URL=os.getenv("HELPDESK_PORTAL_URL","")
SUPPORT_PHONE=os.getenv("SUPPORT_PHONE","")
EVENT_ARCHIVE_PATH=os.getenv("EVENT_ARCHIVE_PATH",str(BASE_DIR / "custody_archive.sqlite3"))
GEOCODING_URL=os.getenv('GEOCODING_URL','')
GEOCODING_TOKEN=os.getenv('GEOCODING_TOKEN','')
GEOCODING_USER_AGENT=os.getenv('GEOCODING_USER_AGENT','PanoLogistics/1.0')
REST_FRAMEWORK.update(DEFAULT_THROTTLE_CLASSES=("rest_framework.throttling.AnonRateThrottle","rest_framework.throttling.UserRateThrottle"),DEFAULT_THROTTLE_RATES={"anon":"60/hour","user":"600/hour"})
