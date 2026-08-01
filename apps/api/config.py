from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    RV_ENV: str = "development"
    RV_LOG_LEVEL: str = "INFO"
    RV_LOG_FORMAT: str = "json"
    RV_PUBLIC_BASE_URL: str = "http://localhost:3000"
    RV_API_BASE_URL: str = "http://localhost:8000"
    RV_ALLOWED_ORIGINS: str = "http://localhost:3000"
    RV_RELEASE_VERSION: str = "0.1.0"
    RV_COMPONENT_INSTANCE: str = "api-1"
    RV_API_HOST: str = "0.0.0.0"
    RV_API_PORT: int = 8000
    RV_REQUEST_MAX_BODY_BYTES: int = 10_485_760
    RV_SHUTDOWN_GRACE_SECONDS: int = 30


settings = Settings()
