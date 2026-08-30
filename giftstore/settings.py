import os
from pathlib import Path
import dj_database_url
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-key-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# Production security hardening (only active when DEBUG=False)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    'axes',

    'accounts',
    'products',
    'cart',
    'orders',
    'wishlist',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',  # must be first — enforces lockout
    'django.contrib.auth.backends.ModelBackend',
]

# Fix SECURITY_AUDIT.md #8/#15: lock out an IP+username combo after repeated
# failed logins (covers both /accounts/login/ and /admin/login/, since both
# use Django's auth backend chain).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_RESET_ON_SUCCESS = True

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',  # must be last
]

ROOT_URLCONF = 'giftstore.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'wishlist.context_processors.wishlist',
                'products.context_processors.whatsapp',
            ],
        },
    },
]

WSGI_APPLICATION = 'giftstore.wsgi.application'

# Database
# Local dev: SQLite. Production: set DATABASE_URL env var (Postgres) on Render/Railway.
DATABASE_URL = config('DATABASE_URL', default='')
if DATABASE_URL:
    # conn_max_age=0 on purpose: Vercel's serverless functions can freeze/thaw
    # containers unpredictably, and a "kept alive" DB connection (conn_max_age>0)
    # can be resumed in a half-dead state after a freeze, causing exactly the
    # "works after a reload" intermittent-error pattern. A fresh connection per
    # request is slightly slower but far more reliable here. Neon's pooler
    # (the "-pooler" hostname in your connection string) makes opening a new
    # connection on every request cheap, so this isn't a real performance cost.
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=0)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles_build' / 'static'
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Product/review/personalization photo uploads to local disk (default below)
# won't survive on Vercel's read-only serverless filesystem — uploads vanish
# on the next deploy or cold start. If CLOUDINARY_URL is set, uploaded media
# is stored on Cloudinary's free tier instead and works correctly on Vercel.
# Get a free CLOUDINARY_URL from https://cloudinary.com/users/register/free
# (Dashboard -> shows it directly as "CLOUDINARY_URL=cloudinary://...").
CLOUDINARY_URL = config('CLOUDINARY_URL', default='')
if CLOUDINARY_URL:
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    STORAGES['default'] = {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'}
else:
    STORAGES['default'] = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CART_SESSION_ID = 'cart'

# Cache backend for rate limiting (django-ratelimit). LocMemCache is fine for
# a single-process deploy; switch to Redis/Memcached if you run multiple
# gunicorn workers, so rate-limit counters are shared across processes.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Business WhatsApp number customers are sent to for order confirmation
# (used in Order.whatsapp_confirm_link() and throughout the site).
WHATSAPP_BUSINESS_NUMBER = config('WHATSAPP_BUSINESS_NUMBER', default='919201461413')

LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = 'accounts:login'

SITE_NAME = 'BestOneGifted'
SITE_DOMAIN = config('SITE_DOMAIN', default='bestonegifted.onrender.com')
