"""Isolated local tests: never connect to the database configured in .env."""
from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
BOT_TOKEN = ""
LANGUAGE_CODE = "en-us"
LANGUAGES = [*LANGUAGES, ("en-us", "English")]  # noqa: F405
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
