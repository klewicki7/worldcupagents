from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/worldcupagents"
    jwt_secret: str = "dev-secret-not-for-prod"
    jwt_algorithm: str = "HS256"
    environment: str = "development"
    log_level: str = "info"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
