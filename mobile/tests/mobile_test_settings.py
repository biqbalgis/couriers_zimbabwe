"""Isolated browser acceptance environment. Never points at the developer database."""
from config.settings import *  # noqa: F403
from pathlib import Path
TEST_ROOT = Path(__file__).resolve().parent / 'artifacts'
TEST_ROOT.mkdir(exist_ok=True)
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': TEST_ROOT / 'acceptance.sqlite3'}}
MEDIA_ROOT = TEST_ROOT / 'media'
EVENT_ARCHIVE_PATH = str(TEST_ROOT / 'archive.sqlite3')
CORS_ALLOWED_ORIGINS = ['http://localhost:8083', 'http://localhost:8082']
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = (*default_headers, 'idempotency-key')
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_CLASSES': ()}  # noqa: F405
DEBUG = True
SMS_DELIVERY_MODE = 'console'
SMS_WEBHOOK_URL = ''
HELPDESK_WEBHOOK_URL = ''
