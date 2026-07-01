from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "PolyProv"
    environment: str = "development"
    secret_key: str = "change-me-in-prod-use-a-secret-manager"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    algorithm: str = "HS256"

    # Postgres
    database_url: str = "postgresql+asyncpg://polyprov:polyprov@db:5432/polyprov"
    database_url_sync: str = "postgresql+psycopg2://polyprov:polyprov@db:5432/polyprov"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://redis:6379/0"
    config_cache_ttl: int = 3600  # seconds
    checkin_buffer_key: str = "polyprov:checkin:buffer"
    discovery_buffer_key: str = "polyprov:discovery:buffer"
    checkin_flush_batch: int = 500
    discovery_flush_batch: int = 500

    # Provisioning
    provisioning_base_path: str = "/provisioning/"
    provisioning_root: str = "/data/provisioning_root"

    # Object store (firmware)
    s3_endpoint_url: str | None = None
    s3_bucket: str = "polyprov-firmware"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    # Rate limiting (per-MAC, requests per window)
    rate_limit_per_minute: int = 30

    # Active health probing
    health_probe_interval_seconds: int = 900
    health_probe_timeout_seconds: float = 2.5
    health_probe_jitter_seconds: int = 300
    health_probe_batch_size: int = 100
    health_probe_concurrency: int = 25
    health_probe_icmp_enabled: bool = True
    health_probe_icmp_command: str = "ping"
    health_probe_icmp_timeout_seconds: float = 1.0
    health_probe_scheduler_enabled: bool = True
    health_probe_schedule_seconds: float = 60.0
    health_probe_claim_timeout_seconds: int = 300

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
