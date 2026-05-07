from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    @field_validator(
        "QBO_CLIENT_ID",
        "QBO_CLIENT_SECRET",
        "QBO_REDIRECT_URI",
        "QBO_ACCESS_TOKEN",
        "QBO_REALM_ID",
        "TOKEN_FILE_PATH",
        mode="before",
    )
    @classmethod
    def strip_optional_qbo_strings(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @field_validator("QBO_REDIRECT_URI", mode="after")
    @classmethod
    def normalize_redirect_uri(cls, v: str | None) -> str | None:
        """Intuit matches redirect_uri exactly; trailing slashes usually cause mismatch."""
        if v is None:
            return None
        return v.rstrip("/") or None

    APP_NAME: str = "Vengage API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # CORS — comma-separated origins in .env
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/vengage"

    # Local storage for customer file uploads (mirrored alongside QBO attach API). Relative paths are resolved from the API process working directory.
    CUSTOMER_ATTACHMENTS_DIR: str = "data/customer_attachments"

    QBO_ENVIRONMENT: str = "sandbox"
    QBO_MINOR_VERSION: str = "65"
    QBO_ACCESS_TOKEN: str | None = None
    QBO_REALM_ID: str | None = None
    QBO_INVOICE_TEMPLATE_ID: str | None = None

    # OAuth (sandbox or prod); tokens file default: repo-root tokens.json (see TOKEN_FILE_PATH)
    QBO_CLIENT_ID: str | None = None
    QBO_CLIENT_SECRET: str | None = None
    QBO_REDIRECT_URI: str | None = None
    FRONTEND_URL: str = "http://localhost:3000"
    TOKEN_FILE_PATH: str | None = None

    INTUIT_WEBHOOK_VERIFIER_TOKEN: str | None = None

    # Auth
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days


settings = Settings()
