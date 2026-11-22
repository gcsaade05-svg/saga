"""
Configuração do projeto SAGA, Sistema de Agendamento e Gestão Assistencial.
PMR3304 Sistemas de Informação 2026.

Em desenvolvimento tudo funciona sem configurar nada. Na publicação, as
variáveis de ambiente SAGA_SECRET_KEY, SAGA_DEBUG=0 e SAGA_HOSTS ligam o modo
de produção, DATABASE_URL aponta para o PostgreSQL, e o Django passa a servir
também o front-end já compilado.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Chave e modo vêm do ambiente na publicação; o padrão abaixo serve só para desenvolvimento.
SECRET_KEY = os.environ.get("SAGA_SECRET_KEY", "django-insecure-so-para-desenvolvimento-saga-pmr3304")
DEBUG = os.environ.get("SAGA_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"] + [h for h in os.environ.get("SAGA_HOSTS", "").split(",") if h]
# O Render informa o próprio endereço nesta variável.
if os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")] + [
    # Em desenvolvimento o React roda no Vite (porta 5173), que repassa /api ao Django.
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
if not DEBUG and SECRET_KEY.startswith("django-insecure"):
    raise RuntimeError("Defina SAGA_SECRET_KEY antes de rodar com SAGA_DEBUG=0.")

# Front-end compilado (npm run build). Em produção o WhiteNoise serve estes
# arquivos na raiz do site, e o index.html responde por todas as rotas do React.
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    # Apps do SAGA, separados como nas aulas de laboratório:
    "core",  # models, regras de negócio, admin e comandos (seed, ocupacao)
    "accounts",  # cadastro, login e logout; grupos e permissões por perfil
    "api",  # API REST: serializadores, views genéricas e rotas /api/v1/
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "saga.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "saga.wsgi.application"

# SQLite no computador; na publicação, PostgreSQL pela variável DATABASE_URL
# (aula 4, "Implantando no Render").
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# Modelo de usuário próprio: o SAGA tem três perfis, então estendemos o usuário padrão.
AUTH_USER_MODEL = "core.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.exists() else None
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Autenticação (aula 5): sistema do Django com sessão
# ---------------------------------------------------------------------------
# O login cria uma sessão no banco (django_session) e o navegador guarda só a
# chave, no cookie sessionid. AUT001: a sessão vale 8 horas.
SESSION_COOKIE_AGE = int(timedelta(hours=8).total_seconds())
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # o React lê o csrftoken e o devolve no cabeçalho X-CSRFToken
LOGIN_URL = "/entrar"

# ---------------------------------------------------------------------------
# API REST (aula 5)
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # O React e a API navegável usam a sessão do login do site.
        "rest_framework.authentication.SessionAuthentication",
        # No Postman ou Thunder Client: aba Authorization, Basic Auth com usuário e senha.
        "rest_framework.authentication.BasicAuthentication",
    ],
    # Toda a API exige login; cada view restringe ainda por grupo e permissão.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "api.excecoes.tratador_de_erros",
}
