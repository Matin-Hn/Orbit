from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    SECRET_KEY: str
    SQLALCHEMY_DATABASE_URL: str = "sqlite:///:memory:"
    ALGORITHM: str

    # S3/MinIO
    S3_ENDPOINT: str
    S3_PUBLIC_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET_NAME: str
    S3_REGION: str
    S3_USE_PATH_STYLE: bool
    S3_USE_SSL: bool

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # Sprite image
    SPRITE_INTERVAL: int
    SPRITE_TILE_WIDTH: int
    SPRITE_TILE_HEIGHT: int
    SPRITE_COLUMNS: int
    SPRITE_MAX_TILES: int

    # Redis for websocket pupsub
    REDIS_WS_PUBSUB: str = "redis://redis:6379/1"



@lru_cache
def get_settings():
    return Settings()

settings = get_settings()