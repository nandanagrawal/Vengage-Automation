from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    APP_NAME: str = "Vengage API"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # CORS — comma-separated origins in .env
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]


settings = Settings()
