from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    debug: bool = False

    database_url: str = "postgresql://pole_emploi:changeme@db:5432/pole_emploi_db"
    redis_url: str = "redis://redis:6379/0"

    allowed_origins: list[str] = ["http://localhost:3000"]

    gemini_api_key: str = ""
    # LLM des lettres : "hermes" (proxy LAN d'Hermes) ou "gemini"
    llm_provider: str = "hermes"
    hermes_url: str = ""
    hermes_token: str = ""
    francetravail_client_id: str = ""
    francetravail_client_secret: str = ""
    # Agrégateurs d'offres par API (clés gratuites)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_api_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""
    resend_api_key: str = ""
    upload_dir: str = "/app/uploads"

    # Auth — set API_USERNAME and API_PASSWORD_HASH (bcrypt) in prod
    api_username: str = "admin"
    # Default hash for "changeme" — MUST be overridden in production via env
    api_password_hash: str = "$2b$12$MEoQRa.2zmSRdrG/SuWQyOeYG5v2xM.GDPLK3rCIioU.vvHZ9OGUG"
    access_token_expire_minutes: int = 480  # 8 hours

    # User's own email — used to validate audit report recipients (SEC-02)
    user_email: str = ""


settings = Settings()
