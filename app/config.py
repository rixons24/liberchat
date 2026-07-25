from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://liberchat:liberchat@localhost:5432/liberchat"
    sync_database_url: str = "postgresql://liberchat:liberchat@localhost:5432/liberchat"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    media_bucket: str = "liberchat-media-dev"
    media_storage_endpoint: str = "http://localhost:9000"  # e.g. local MinIO for dev, R2/S3 in prod
    media_storage_access_key: str = "devkey"
    media_storage_secret_key: str = "devsecret"

    safer_api_key: str = ""       # Thorn Safer — required before real launch
    ncmec_report_endpoint: str = ""  # requires registration at report.cybertip.org

    contact_ref_salt: str = "dev-only-change-me-too"

    media_session_timeout_minutes: int = 5
    post_default_expiry_hours: int = 72

    sms_provider_api_key: str = ""   # e.g. Twilio / Africa's Talking

    class Config:
        env_file = ".env"


settings = Settings()
