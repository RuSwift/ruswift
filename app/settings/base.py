import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aioredis
from pydantic import BaseModel, Extra, Field
from pydantic_yaml import parse_yaml_file_as
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


# ======== SETTINGS FROM YAML ==========

class DatabaseCfg(BaseModel, extra=Extra.ignore):
    name: str = os.getenv('DATABASE_NAME', 'postgres')
    user: str = os.getenv('DATABASE_USER', 'postgres')
    password: str = os.getenv('DATABASE_PASSWORD', 'postgres')
    host: str = os.environ.get('DATABASE_HOST') or 'localhost'
    port: int = int(os.environ.get('DATABASE_PORT', 5432))
    conn_max_age: int = int(os.environ.get('DATABASE_CONN_MAX_AGE', 60))


class DSN(BaseModel, extra=Extra.ignore):
    redis: str = os.getenv('REDIS_DSN', 'redis://localhost')


class SentryCfg(BaseModel, extra=Extra.allow):
    enabled: bool = False
    dsn: str
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate: float = 1.0


class AuthWithToken(BaseModel):
    token: str
    permissions: List[str] = Field(default_factory=list)


class APICfg(BaseModel):
    path: str
    auth: Dict[str, AuthWithToken]


class KYC(BaseModel):
    provider_class: str = 'kyc.MTSKYCProvider'


class RatioEngineClassConfig(BaseModel):
    settings: Optional[Dict] = None


class TelegramBotConfig(BaseModel):
    token: Optional[str] = os.getenv('TG_BOT_TOKEN')
    chat_id: Optional[int] = os.getenv('TG_BOT_CHAT_ID')


class GoogleCloudConfig(BaseModel):
    api_key: Optional[str] = os.getenv('GC_API_KEY')


class Settings(BaseModel):
    secret: str
    database: DatabaseCfg
    dsn: DSN
    sentry: SentryCfg = None
    api: APICfg
    kyc: KYC = Field(default_factory=KYC)
    ratios: Dict[str, RatioEngineClassConfig] = Field(default_factory=dict)
    bestchange_mapping: Optional[Dict] = None
    tg_bot: TelegramBotConfig = Field(default_factory=TelegramBotConfig)
    gc: GoogleCloudConfig = Field(default_factory=GoogleCloudConfig)


BASE_DIR = Path(__file__).resolve().parent.parent
SETTINGS_DIR = BASE_DIR.joinpath('settings')
YAML = os.getenv('SETTINGS', str(SETTINGS_DIR.joinpath('cfg.yml')))
_settings = parse_yaml_file_as(Settings, YAML)

# ========== DJANGO SETTINGS ============
SECRET_KEY = _settings.secret
DEBUG = True
ALLOWED_HOSTS = ['*']
SETTINGS_MODULE = 'settings'

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'exchange'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',

     # TODO: при включении не работает на проде
     # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': _settings.database.name,
        'USER': _settings.database.user,
        'PASSWORD': _settings.database.password,
        'HOST': _settings.database.host,
        'PORT': _settings.database.port,
        'CONN_HEALTH_CHECKS': True,
        'CONN_MAX_AGE': _settings.database.conn_max_age,
        'TEST': {
            'NAME': 'test_database' + str(datetime.now()),
        }
    }
}

URL_MODULE = os.getenv('URL_MODULE', 'urls')
ROOT_URLCONF = f'{SETTINGS_MODULE}.{URL_MODULE}'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            str(Path(BASE_DIR).joinpath('templates'))
        ],
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = f'{SETTINGS_MODULE}.wsgi.application'
ASGI_APPLICATION = f'{SETTINGS_MODULE}.asgi.application'

SENTRY_ON = _settings.sentry is not None and _settings.sentry.enabled
if SENTRY_ON:
    sentry_sdk.init(
        **_settings.sentry.model_dump(mode='json', exclude={'enabled'}),
        integrations=[
            DjangoIntegration(
                transaction_style='function_name',
                middleware_spans=True,
                signals_spans=False,
                cache_spans=False,
            )
        ]
    )
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = 'static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [
    BASE_DIR / "static"
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
LOGIN_URL = 'login'
LOGOUT_URL = 'logout'
REGISTER_URL = 'register'

API = {
    'PATH': _settings.api.path,
    'AUTH': _settings.api.auth
}

REDIS_CONN_POOL = aioredis.ConnectionPool.from_url(
    _settings.dsn.redis, max_connections=1000
)


DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

KYC = {
    'PROV_CLASS': _settings.kyc.provider_class
}
RATIOS = {
    class_name: cfg for class_name, cfg in _settings.ratios.items()
}
BESTCHANGE_MAPPING = _settings.bestchange_mapping

TG_BOT = _settings.tg_bot
GC = _settings.gc
