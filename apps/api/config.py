from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core System & App
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

    # Phase 2: Database (PostgreSQL)
    RV_DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/rekanvault"
    RV_DATABASE_POOL_MIN_SIZE: int = 1
    RV_DATABASE_POOL_MAX_SIZE: int = 10
    RV_DATABASE_STATEMENT_TIMEOUT_MS: int = 30000

    # Phase 2: Supabase Auth & JWT
    RV_SUPABASE_URL: str = "http://localhost:54321"
    RV_SUPABASE_JWKS_URL: str = "http://localhost:54321/auth/v1/jwks.json"
    RV_SUPABASE_JWT_ISSUER: str = "http://localhost:54321/auth/v1"
    RV_SUPABASE_JWT_AUDIENCE: str = "authenticated"
    RV_SUPABASE_SECRET_KEY: str = ""  # Admin / Migration worker only (Risk R-003)

    # Phase 2: Credential Encryption (AES-GCM)
    RV_CREDENTIAL_ENCRYPTION_KEYS: str = ""
    RV_ACTIVE_CREDENTIAL_KEY_ID: str = "key-1"

    # Phase 2: Worker & Job Queue
    RV_WORKER_QUEUES: str = "default"
    RV_WORKER_CONCURRENCY: int = 2
    RV_JOB_POLL_INTERVAL_MS: int = 1000
    RV_JOB_LEASE_SECONDS: int = 300
    RV_JOB_MAX_ATTEMPTS: int = 8
    RV_ARTIFACT_STORAGE_BACKEND: str = "filesystem"
    RV_ARTIFACT_STORAGE_PATH: str = "/tmp/rekanvault_artifacts"
    RV_MAX_SOURCE_FILE_BYTES: int = 52_428_800


settings = Settings()

