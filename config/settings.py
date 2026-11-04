"""
Configuración de desarrollo 
Los datos de la base de datos se leen del archivo .env
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "solo-para-desarrollo-cambiar")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
# RF-B4: en desarrollo los correos (ej. recuperar contraseña) se imprimen en la consola.
EMAIL_BACKEND = "apps.identidad.infraestructura.correo_consola.EmailBackend"
DEFAULT_FROM_EMAIL = "Sistema de Préstamos <no-responder@unsa.edu.pe>"
PASSWORD_RESET_TIMEOUT = 60 * 60  # el enlace de recuperación vale 1 hora

# RF-B6: préstamos devueltos a tiempo para que un solicitante sea FRECUENTE.
IDENTIDAD_PRESTAMOS_PARA_FRECUENTE = int(os.getenv("IDENTIDAD_PRESTAMOS_PARA_FRECUENTE", "5"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Apps del proyecto
    "apps.common",
    "apps.identidad",
    "apps.catalogo",
    "apps.reservas",
    "apps.perdidas",
    "apps.reportes",
    "apps.sanciones",
    "apps.auditoria",
    "apps.notificaciones",
    "apps.politicas",
    "apps.circulacion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.identidad.presentacion.context_processors.menu_por_rol",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "prestamos"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# RNF-1: reglas de contraseña (se aplican al registrar, recuperar y cambiar contraseña).
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True

LOGIN_URL = "identidad:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "identidad:login"
STATIC_URL = "static/"

# Archivos subidos (documentos del registro). NO se sirven con una URL pública:
# tienen datos personales y solo el administrador los abre desde una vista protegida.
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "identidad.Cuenta"

