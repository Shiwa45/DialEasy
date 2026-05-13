# telecrm_project/settings.py
# ─────────────────────────────────────────────────────────────────────────────
# PHASE 0: Multi-tenancy with django-tenants
# PHASE 2: Centralised API domain for mobile (api.dialeasy.easyian.com)
# IMPORTANT: DATABASE must be PostgreSQL. SQLite is NOT supported by django-tenants.
# ─────────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# ─── Tenant-Aware Database Router ─────────────────────────────────────────────
# django-tenants requires this specific database engine.
DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': os.getenv('DB_NAME', 'telecrm_db'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
    }
}

DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']

# ─── Tenant Configuration ─────────────────────────────────────────────────────
TENANT_MODEL = 'tenants.Client'
TENANT_DOMAIN_MODEL = 'tenants.Domain'

# ─── App Separation ───────────────────────────────────────────────────────────
# SHARED_APPS  → live in the PUBLIC schema (visible to all tenants + super admin)
# TENANT_APPS  → live in EACH TENANT's private schema
#
# Rule: SHARED_APPS must come first in installation order.
# django-tenants INSTALLED_APPS = SHARED_APPS + [a for a in TENANT_APPS if a not in SHARED_APPS]

SHARED_APPS = [
    # django-tenants must be first
    'django_tenants',

    # Tenant & plan management (public schema only)
    'tenants',

    # Django built-ins that must be in shared schema
    'django.contrib.contenttypes',
    'django.contrib.auth',          # Users live in public schema
    'django.contrib.admin',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party shared
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',  # Enables logout blacklisting
    'corsheaders',

    # Centralised API gateway — lives in public schema (resolves tenants)
    'tenants_api',
]

TENANT_APPS = [
    # These apps get their own tables per tenant schema
    'django.contrib.contenttypes',  # Required in tenant apps too
    'rest_framework.authtoken',

    # Your CRM apps — each tenant gets isolated data
    'leads',
    'agents',
    'api',
    'notifications',
    'reports',
    'ai',
]

# FCM Settings
FCM_SERVER_KEY = os.getenv('FCM_SERVER_KEY', '')

# django-tenants requires INSTALLED_APPS to be the union
INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# ─── Middleware ───────────────────────────────────────────────────────────────
# TenantMainMiddleware MUST be first — it routes requests to the correct schema.
# CentralApiTenantMiddleware runs second — it re-routes /mobile/ requests by
# reading the JWT claim or X-Tenant-Slug header instead of the subdomain.
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',      # ← MUST be first
    'corsheaders.middleware.CorsMiddleware',                    # ← before CommonMiddleware
    'tenants_api.middleware.CentralApiTenantMiddleware',        # ← mobile schema switcher
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ─── URL Routing ──────────────────────────────────────────────────────────────
# PUBLIC_SCHEMA_URLCONF handles requests on the public/admin domain.
# ROOT_URLCONF handles requests on tenant subdomains.
ROOT_URLCONF = 'telecrm_project.urls'
PUBLIC_SCHEMA_URLCONF = 'telecrm_project.urls_public'

# ─── Templates ────────────────────────────────────────────────────────────────
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
                # ← Injects `tenant_features` and `current_tenant` into every template
                'tenants.feature_gates.tenant_features_context_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'telecrm_project.wsgi.application'

# ─── Static & Media Files ─────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─── Authentication ───────────────────────────────────────────────────────────
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/leads/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ─── Django REST Framework ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # JWT auth with tenant schema-switching (mobile / centralised API)
        'tenants_api.authentication.JWTTenantAuthentication',
        # Legacy token auth — kept for backward compatibility with old Flutter builds
        'rest_framework.authentication.TokenAuthentication',
        # Session auth — for Django web admin and browser-based API calls
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# ─── Password Validation ──────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ─── Misc ─────────────────────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'False') == 'True'
CORS_ALLOWED_ORIGINS = [o for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if o]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    # ← Custom tenant identifier header for mobile pre-auth requests
    'x-tenant-slug',
]

# ─── SimpleJWT Configuration ──────────────────────────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    # Access token lifetime: short (15 min) for security
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES',  '15'))),
    # Refresh token lifetime: long (7 days) for mobile UX
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', '7'))),

    # Rotate refresh tokens on each use (more secure)
    'ROTATE_REFRESH_TOKENS': True,
    # Blacklist the old refresh token after rotation
    'BLACKLIST_AFTER_ROTATION': True,

    # Algorithm & signing
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.getenv('JWT_SECRET_KEY', SECRET_KEY),

    # Standard JWT fields
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    # Custom serializer that embeds tenant_slug, features, etc.
    'TOKEN_OBTAIN_SERIALIZER': 'tenants_api.serializers.TenantTokenObtainPairSerializer',

    # Token types
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    # Sliding tokens (optional — disabled by default)
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# ─── Central API Domain ───────────────────────────────────────────────────────
# The single HTTPS domain used by mobile apps to reach the API.
# No wildcard SSL needed — this is a single fixed subdomain.
CENTRAL_API_DOMAIN = os.getenv('CENTRAL_API_DOMAIN', 'api.dialeasy.easyian.com')

# Mobile API URL prefix — must match MOBILE_API_PREFIX in middleware.py
MOBILE_API_PREFIX = '/mobile/'
