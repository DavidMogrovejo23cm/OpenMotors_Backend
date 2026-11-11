import os
import re
from urllib.parse import quote_plus
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de OpenAuto Backend.
    Soporta tanto las variables de entorno actuales de Render/Spring Boot
    (DB_URL con prefijo jdbc:postgresql://, DB_USER, DB_PASSWORD, JWT_SECRET, etc.)
    como base de datos SQLite local para desarrollo inmediato.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "OpenAuto"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = os.getenv("APP_ENV", "development")
    PORT: int = int(os.getenv("PORT", "8080"))

    # Base de datos
    DB_URL: str = os.getenv("DB_URL", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # JWT
    # No hay valor por defecto: desplegar sin esta variable debe fallar de forma visible.
    JWT_SECRET: str = Field(..., min_length=32)
    JWT_EXPIRATION_MINUTES: int = Field(default=480, ge=15, le=1440)

    # CORS
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:4200,https://openmotor.vercel.app",
    )
    SEED_DEMO_DATA: bool = os.getenv("SEED_DEMO_DATA", "false").lower() == "true"
    BOOTSTRAP_ADMIN_USERNAME: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "")
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # Proveedores de Email
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "noreply@openauto.com")
    MAIL_HOST: str = os.getenv("MAIL_HOST", "smtp.gmail.com")
    MAIL_PORT: int = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "Open Auto")

    # Supabase Storage
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_BUCKET: str = os.getenv("SUPABASE_BUCKET", "autos")

    # OCR
    FLASK_OCR_URL: str = os.getenv("FLASK_OCR_URL", "http://localhost:5000/api/ocr/placa")

    # KeepAlive & Métricas
    KEEPALIVE_ENABLED: bool = os.getenv("KEEPALIVE_ENABLED", "true").lower() == "true"
    RENDER_EXTERNAL_URL: str = os.getenv(
        "RENDER_EXTERNAL_URL", "https://backend-openmotors.onrender.com"
    )
    METRICS_OUTPUT_DIR: str = os.getenv(
        "METRICS_OUTPUT_DIR", "./metrics-reports/incremental"
    )
    METRICS_REPORTS_DIRECTORY: str = os.getenv(
        "METRICS_REPORTS_DIRECTORY", "./metrics-reports"
    )
    METRICS_STORAGE_LOCAL_ENABLED: bool = (
        os.getenv("METRICS_STORAGE_LOCAL_ENABLED", "true").lower() == "true"
    )
    METRICS_TIMEZONE: str = os.getenv("METRICS_TIMEZONE", "America/Guayaquil")

    # GitLab Reportes
    GITLAB_ENABLED: bool = os.getenv("GITLAB_ENABLED", "false").lower() == "true"
    GITLAB_TOKEN: str = os.getenv("GITLAB_TOKEN", "")
    GITLAB_PROJECT_ID: str = os.getenv("GITLAB_PROJECT_ID", "")
    GITLAB_BASE_URL: str = os.getenv("GITLAB_BASE_URL", "https://gitlab.com")
    GITLAB_API_URL: str = os.getenv("GITLAB_API_URL", "https://gitlab.com/api/v4")
    GITLAB_BRANCH: str = os.getenv("GITLAB_BRANCH", "main")

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Construye una URL válida para SQLAlchemy a partir de DB_URL o DATABASE_URL.
        Convierte automáticamente URLs JDBC (`jdbc:postgresql://...`) o `postgres://`
        e inyecta `DB_USER` y `DB_PASSWORD` si vienen por separado (como en Render).
        Si no hay base externa configurada o es H2, usa SQLite local (`./openauto_db.sqlite`).
        """
        raw = (self.DB_URL or self.DATABASE_URL or "").strip()
        if not raw or "jdbc:h2:" in raw:
            return "sqlite:///./openauto_db.sqlite"

        # Quitar prefijo jdbc: si viene de configuración previa de Spring Boot
        if raw.startswith("jdbc:"):
            raw = raw[len("jdbc:") :]

        if raw.startswith("postgres://"):
            raw = raw.replace("postgres://", "postgresql+psycopg2://", 1)
        elif raw.startswith("postgresql://"):
            raw = raw.replace("postgresql://", "postgresql+psycopg2://", 1)

        # Si es postgresql y no tiene usuario:password embebido en la URL, inyectarlos
        if raw.startswith("postgresql") and "@" not in raw:
            match = re.match(r"^(postgresql(?:\+\w+)?://)(.+)$", raw)
            if match:
                scheme, rest = match.groups()
                user = quote_plus(self.DB_USER or "postgres")
                pwd = quote_plus(self.DB_PASSWORD or "")
                if pwd:
                    raw = f"{scheme}{user}:{pwd}@{rest}"
                else:
                    raw = f"{scheme}{user}@{rest}"

        return raw


settings = Settings()
