from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    debug: bool = False

    database_url: str = "postgresql://pole_emploi:changeme@db:5432/pole_emploi_db"
    redis_url: str = "redis://redis:6379/0"

    allowed_origins: list[str] = ["http://localhost:3000"]

    anthropic_api_key: str = ""
    francetravail_client_id: str = ""
    francetravail_client_secret: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""


settings = Settings()
