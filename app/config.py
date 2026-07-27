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

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # TEMPORARY: exposes OTP codes via an API endpoint for testing before
    # a real SMS provider is wired up. Must be false/unset in any real
    # deployment — an OTP-retrieval endpoint anyone can hit defeats the
    # entire purpose of phone verification. Remove the endpoint entirely
    # once SMS_PROVIDER_API_KEY is set and confirmed working.
    debug_otp_endpoint_enabled: bool = False

    # TEMPORARY: same pattern as debug_otp_endpoint_enabled. Lets you
    # create the FIRST admin account via HTTP instead of a shell (needed
    # since Render's free tier has no Shell/One-Off Jobs access). This
    # endpoint self-disables after the first admin account exists, and
    # you should unset this env var once you've used it regardless.
    bootstrap_admin_enabled: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
