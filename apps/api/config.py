from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core System & App
    RV_ENV: str = "development"
    RV_API_BASE_URL: str = "http://localhost:8000"
    RV_ALLOWED_ORIGINS: str = "http://localhost:9001"
    RV_RELEASE_VERSION: str = "0.1.0"
    RV_COMPONENT_INSTANCE: str = "api-1"
    RV_API_HOST: str = "0.0.0.0"
    RV_API_PORT: int = 9002
    RV_SHUTDOWN_GRACE_SECONDS: int = 30

    # Phase 2: Database (PostgreSQL)
    RV_DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rekanvault"
    RV_DATABASE_POOL_MIN_SIZE: int = 1
    RV_DATABASE_POOL_MAX_SIZE: int = 10

    # Phase 2: Supabase Auth & JWT
    RV_SUPABASE_JWT_ISSUER: str = "http://localhost:54321/auth/v1"

    # Phase 2: Credential Encryption (AES-GCM - RV-DEC-P2-0004)
    RV_CREDENTIAL_KEY_ACTIVE: str = "key-1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    RV_CREDENTIAL_KEY_PREVIOUS: str = ""
    RV_CREDENTIAL_ENCRYPTION_KEYS: str = ""
    RV_ACTIVE_CREDENTIAL_KEY_ID: str = "key-1"

    # Phase 2: Worker & Job Engine (RV-DEC-P2-0005, RV-DEC-P2-0006)
    RV_WORKER_QUEUES: str = "default"
    RV_WORKER_CONCURRENCY: int = 2
    RV_JOB_POLL_INTERVAL_MS: int = 1000
    RV_JOB_LEASE_SECONDS: int = 300
    RV_JOB_MAX_ATTEMPTS: int = 8
    RV_ARTIFACT_STORAGE_BACKEND: str = "filesystem"
    RV_ARTIFACT_STORAGE_PATH: str = "/tmp/rekanvault_artifacts"
    RV_MAX_SOURCE_FILE_BYTES: int = 52_428_800

    # Phase 3: Google Drive OAuth (RV-DEC-P3-0001)
    RV_GOOGLE_CLIENT_ID: str = ""
    RV_GOOGLE_CLIENT_SECRET: str = ""
    RV_GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback/google"
    RV_GOOGLE_OAUTH_SCOPES: str = "https://www.googleapis.com/auth/drive.readonly"
    RV_GOOGLE_PILOT_REFRESH_TOKEN: str = ""
    RV_GOOGLE_API_TIMEOUT_SECONDS: int = 30

    # Phase 3: Notion Internal Integration (RV-DEC-P3-0002)
    RV_NOTION_API_VERSION: str = "2026-03-11"
    RV_NOTION_TOKEN: str = ""
    RV_NOTION_API_TIMEOUT_SECONDS: int = 30
    RV_NOTION_WEBHOOK_VERIFICATION_TOKEN: str = ""


settings = Settings()
