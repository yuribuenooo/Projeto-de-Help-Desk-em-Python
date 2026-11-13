import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-inseguro-troque-em-producao')
DEBUG = os.environ.get('DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
_host = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
CSRF_TRUSTED_ORIGINS = [f'https://{_host}'] if _host else []

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'chamados', 'axes',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',
    'axes.middleware.AxesMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('DB_FILE', BASE_DIR / 'db.sqlite3')}}
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'painel'
LOGOUT_REDIRECT_URL = 'login'
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))  # anexos (servidos só por view autenticada)

# --- Rate limit e bloqueio de força bruta ---
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
    'LOCATION': 'cache_tabela',            # criada por: manage.py createcachetable
}}

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',  # PRIMEIRO: decide se o login está bloqueado
    'django.contrib.auth.backends.ModelBackend',
]
AXES_FAILURE_LIMIT = 5                      # falhas permitidas
AXES_COOLOFF_TIME = timedelta(minutes=15)   # tempo de bloqueio
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']   # bloqueia o IP E o usuário alvo
AXES_RESET_ON_SUCCESS = True
AXES_HTTP_RESPONSE_CODE = 429
AXES_IPWARE_PROXY_COUNT = 1                 # Render põe 1 proxy na frente do app
AXES_IPWARE_META_PRECEDENCE_ORDER = ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR')

RATELIMIT_VIEW = 'chamados.views.limite_excedido'   # resposta 429 amigável