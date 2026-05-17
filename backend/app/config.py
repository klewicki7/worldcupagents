from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/worldcupagents"
    jwt_secret: str = "dev-secret-not-for-prod"
    jwt_algorithm: str = "HS256"
    environment: str = "development"
    log_level: str = "info"
    google_oauth_client_id: str = ""
    admin_emails: str = ""
    public_base_url: str = "http://localhost:3000"
    mcp_base_url: str = "http://localhost:8000"

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.admin_emails.split(",") if e.strip())

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
