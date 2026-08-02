"""Configuración central segura para ejecución local y Railway."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

if load_dotenv:
    # Solo para desarrollo local. Los archivos .env están excluidos del paquete.
    load_dotenv(PROJECT_DIR / ".env", override=False)
    load_dotenv(BACKEND_DIR / ".env", override=False)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _absolute_path(raw: str | None, default: Path, *, relative_to: Path = BACKEND_DIR) -> Path:
    path = Path(raw).expanduser() if raw and raw.strip() else default
    if not path.is_absolute():
        path = relative_to / path
    return path.resolve()


def resolve_path(name: str, default: Path, *, relative_to: Path = BACKEND_DIR) -> str:
    return str(_absolute_path(os.getenv(name), default, relative_to=relative_to))


def _default_data_dir() -> Path:
    # Railway expone automáticamente RAILWAY_VOLUME_MOUNT_PATH cuando hay volumen.
    mount = (os.getenv("DATA_DIR") or os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or "").strip()
    return _absolute_path(mount, BACKEND_DIR, relative_to=PROJECT_DIR)


def _sqlite_url(path: str) -> str:
    return f"sqlite:///{Path(path).as_posix()}"


def password_policy_errors(password: str, minimum: int = 12) -> list[str]:
    errors: list[str] = []
    if len(password or "") < minimum:
        errors.append(f"mínimo {minimum} caracteres")
    if not re.search(r"[A-ZÁÉÍÓÚÑ]", password or ""):
        errors.append("una mayúscula")
    if not re.search(r"[a-záéíóúñ]", password or ""):
        errors.append("una minúscula")
    if not re.search(r"\d", password or ""):
        errors.append("un número")
    if not re.search(r"[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ]", password or ""):
        errors.append("un símbolo")
    return errors


class BaseConfig:
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    APP_VERSION = os.getenv("APP_VERSION", "2.3.6-railway-clean")
    BUILD_COMMIT = os.getenv("BUILD_COMMIT", os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown"))
    BUILD_DATE = os.getenv("BUILD_DATE", "unknown")

    BASE_DIR = str(BACKEND_DIR)
    PROJECT_DIR = str(PROJECT_DIR)
    DATA_DIR = str(_default_data_dir())
    SEED_TEMPLATES_FOLDER = str(BACKEND_DIR / "seed_data" / "templates_originales")

    DATABASE_PATH = resolve_path("DATABASE_PATH", Path(DATA_DIR) / "database.sqlite3")
    DATABASE_URL = os.getenv("DATABASE_URL", _sqlite_url(DATABASE_PATH)).strip()
    ENABLE_POSTGRESQL_RUNTIME = env_bool("ENABLE_POSTGRESQL_RUNTIME", False)
    SQLITE_TIMEOUT_SECONDS = env_int("SQLITE_TIMEOUT_SECONDS", 30)

    UPLOAD_FOLDER = resolve_path("UPLOAD_FOLDER", Path(DATA_DIR) / "uploads")
    TEMPLATES_FOLDER = resolve_path("TEMPLATES_FOLDER", Path(DATA_DIR) / "templates_originales")
    OUTPUT_FOLDER = resolve_path("OUTPUT_FOLDER", Path(DATA_DIR) / "archivos_actualizados")
    BACKUPS_FOLDER = resolve_path("BACKUPS_FOLDER", Path(DATA_DIR) / "backups")
    DOCUMENTOS_FOLDER = resolve_path("DOCUMENTOS_FOLDER", Path(DATA_DIR) / "documentos_institucionales")
    CUENTAS_COBRO_FOLDER = resolve_path("CUENTAS_COBRO_FOLDER", Path(DATA_DIR) / "cuentas_cobro_plantillas")
    LOCAL_STORAGE_PATH = resolve_path("LOCAL_STORAGE_PATH", Path(DATA_DIR) / "storage")
    LOG_FOLDER = resolve_path("LOG_FOLDER", Path(DATA_DIR) / "logs")

    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-jwt-only-change-me")

    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").strip()
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").strip()
    PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", FRONTEND_ORIGIN).rstrip("/")

    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower().strip()
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
    S3_REGION = os.getenv("S3_REGION", "")
    S3_BUCKET = os.getenv("S3_BUCKET", "")
    S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
    S3_USE_SSL = env_bool("S3_USE_SSL", True)

    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "primera_infancia_session")
    SESSION_LIFETIME_MINUTES = env_int("SESSION_LIFETIME_MINUTES", 720)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)

    MIN_PASSWORD_LENGTH = env_int("MIN_PASSWORD_LENGTH", 12)
    INITIAL_ADMIN_USERNAME = os.getenv("INITIAL_ADMIN_USERNAME", "").strip()
    INITIAL_ADMIN_EMAIL = os.getenv("INITIAL_ADMIN_EMAIL", "").strip()
    INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    INITIAL_ADMIN_NAME = os.getenv("INITIAL_ADMIN_NAME", "Administrador inicial").strip()
    INITIAL_ADMIN_FORCE_PASSWORD_CHANGE = env_bool("INITIAL_ADMIN_FORCE_PASSWORD_CHANGE", True)
    INITIAL_FOUNDATION_NAME = os.getenv("INITIAL_FOUNDATION_NAME", "Entorno de pruebas").strip()

    LOGIN_MAX_ATTEMPTS = env_int("LOGIN_MAX_ATTEMPTS", 5)
    LOGIN_WINDOW_SECONDS = env_int("LOGIN_WINDOW_SECONDS", 900)
    LOGIN_LOCK_SECONDS = env_int("LOGIN_LOCK_SECONDS", 900)
    RECOVERY_MAX_ATTEMPTS = env_int("RECOVERY_MAX_ATTEMPTS", 5)
    RECOVERY_WINDOW_SECONDS = env_int("RECOVERY_WINDOW_SECONDS", 3600)
    RECOVERY_LOCK_SECONDS = env_int("RECOVERY_LOCK_SECONDS", 3600)

    PASSWORD_RESET_EXPIRES_MINUTES = env_int("PASSWORD_RESET_EXPIRES_MINUTES", 30)
    ALLOW_PASSWORD_RESET_TOKEN_RESPONSE = env_bool("ALLOW_PASSWORD_RESET_TOKEN_RESPONSE", False)
    PASSWORD_RESET_PUBLIC_URL = os.getenv("PASSWORD_RESET_PUBLIC_URL", PUBLIC_APP_URL).rstrip("/")
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
    PASSWORD_RESET_FROM_EMAIL = os.getenv("PASSWORD_RESET_FROM_EMAIL", "").strip()

    ALLOW_LEGACY_QUERY_TOKENS = env_bool("ALLOW_LEGACY_QUERY_TOKENS", False)
    ENABLE_LEGACY_TENANT_BACKFILL = env_bool("ENABLE_LEGACY_TENANT_BACKFILL", False)

    MAX_CONTENT_LENGTH = env_int("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    FORCE_HTTPS = env_bool("FORCE_HTTPS", False)
    TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 0)
    BACKUP_RETENTION_DAYS = env_int("BACKUP_RETENTION_DAYS", 90)
    DEMO_MODE = env_bool("DEMO_MODE", False)

    # Esta entrega Railway queda restringida a una sola fundación. El código
    # histórico aún contiene consultas que no han sido certificadas para
    # aislamiento multi-tenant completo; habilitarlo exige aceptación explícita.
    SINGLE_TENANT_MODE = env_bool("SINGLE_TENANT_MODE", True)
    ALLOW_EXPERIMENTAL_MULTI_TENANT = env_bool("ALLOW_EXPERIMENTAL_MULTI_TENANT", False)

    FLASK_HOST = os.getenv("FLASK_HOST", os.getenv("HOST", "127.0.0.1"))
    FLASK_PORT = env_int("FLASK_PORT", env_int("PORT", 5000))
    FRONTEND_PORT = env_int("FRONTEND_PORT", 8080)
    SERVER_MODE = os.getenv("SERVER_MODE", "LOCAL")

    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = {
        "pool_pre_ping": True,
        "future": True,
    }


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    DEBUG = env_bool("FLASK_DEBUG", False)
    TESTING = False
    SESSION_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    APP_ENV = "production"
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    FORCE_HTTPS = env_bool("FORCE_HTTPS", True)  # ProxyFix conserva el esquema externo; healthcheck está exento.
    TRUSTED_PROXY_COUNT = env_int("TRUSTED_PROXY_COUNT", 1)


CONFIGS = {
    "development": DevelopmentConfig,
    "dev": DevelopmentConfig,
    "testing": TestingConfig,
    "test": TestingConfig,
    "production": ProductionConfig,
    "prod": ProductionConfig,
}


def get_config(name: str | None = None):
    selected = (name or os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development").lower()
    return CONFIGS.get(selected, DevelopmentConfig)


def validate_runtime_config(config: dict[str, Any]) -> None:
    """Rechaza configuraciones productivas inseguras antes de abrir el servicio."""
    if str(config.get("APP_ENV", "")).lower() != "production":
        return

    errors: list[str] = []
    secret = str(config.get("SECRET_KEY", "")).strip()
    jwt_secret = str(config.get("JWT_SECRET_KEY", "")).strip()
    invalid = {
        "", "development-only-change-me", "development-jwt-only-change-me",
        "your-secret-key-change-in-production", "your-jwt-secret-change-in-production",
    }
    if secret in invalid or len(secret) < 32:
        errors.append("SECRET_KEY debe ser aleatoria y tener al menos 32 caracteres.")
    if jwt_secret in invalid or len(jwt_secret) < 32:
        errors.append("JWT_SECRET_KEY debe ser distinta y tener al menos 32 caracteres.")
    if secret and jwt_secret and secret == jwt_secret:
        errors.append("SECRET_KEY y JWT_SECRET_KEY no pueden ser iguales.")

    username = str(config.get("INITIAL_ADMIN_USERNAME", "")).strip()
    email = str(config.get("INITIAL_ADMIN_EMAIL", "")).strip()
    password = str(config.get("INITIAL_ADMIN_PASSWORD", ""))
    marker = Path(str(config.get("DATA_DIR", ""))) / ".primera_infancia_initialized.json"
    database_path = Path(str(config.get("DATABASE_PATH", "")))
    initialized = marker.is_file() and database_path.is_file()
    any_admin_value = bool(username or email or password)
    if not initialized or any_admin_value:
        if not username:
            errors.append("INITIAL_ADMIN_USERNAME es obligatorio antes del primer inicio.")
        if not email or "@" not in email:
            errors.append("INITIAL_ADMIN_EMAIL debe ser un correo válido antes del primer inicio.")
        policy_errors = password_policy_errors(password, int(config.get("MIN_PASSWORD_LENGTH", 12)))
        if policy_errors:
            errors.append("INITIAL_ADMIN_PASSWORD requiere " + ", ".join(policy_errors) + ".")
        if username.lower() == "admin" and password.lower() in {"admin", "admin123", "password"}:
            errors.append("No se permiten credenciales administrativas predeterminadas.")

    if config.get("STORAGE_BACKEND") not in {"local", "s3"}:
        errors.append("STORAGE_BACKEND debe ser local o s3.")
    if str(config.get("ALLOWED_ORIGINS", "")).strip() == "*":
        errors.append("ALLOWED_ORIGINS=* no está permitido en producción.")
    if config.get("ALLOW_LEGACY_QUERY_TOKENS"):
        errors.append("ALLOW_LEGACY_QUERY_TOKENS debe permanecer desactivado en producción.")
    if config.get("ALLOW_PASSWORD_RESET_TOKEN_RESPONSE"):
        errors.append("ALLOW_PASSWORD_RESET_TOKEN_RESPONSE debe permanecer desactivado en producción.")
    if not config.get("FORCE_HTTPS", True):
        errors.append("FORCE_HTTPS debe permanecer activado en esta entrega Railway.")
    if not Path(str(config.get("DATA_DIR", ""))).is_absolute():
        errors.append("DATA_DIR debe ser una ruta absoluta.")
    if not config.get("SINGLE_TENANT_MODE", True) and not config.get("ALLOW_EXPERIMENTAL_MULTI_TENANT", False):
        errors.append(
            "El modo multi-fundación todavía no está certificado para esta entrega. "
            "Mantenga SINGLE_TENANT_MODE=true o habilite conscientemente "
            "ALLOW_EXPERIMENTAL_MULTI_TENANT=true."
        )

    if errors:
        raise RuntimeError("Configuración de producción inválida: " + " ".join(errors))
