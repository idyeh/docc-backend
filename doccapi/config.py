from functools import lru_cache
from typing import Optional

import logging
from minio import Minio
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

class BaseConfig(BaseSettings):
    ENV_STATE: Optional[str] = None

    """Loads the dotenv file."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class GlobalConfig(BaseConfig):
    DATABASE_URL: Optional[str] = None
    DB_FORCE_ROLL_BACK: bool = False
    LOGTAIL_API_KEY: Optional[str] = None
    # MinIO Config
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: Optional[str] = None
    MINIO_ROOT_PASSWORD: Optional[str] = None
    MINIO_BUCKET: str
    MINIO_SECURE: bool = False


class DevConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="DEV_")


class ProdConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="PROD_")


class TestConfig(GlobalConfig):
    DATABASE_URL: Optional[str] = None
    DB_FORCE_ROLL_BACK: bool = True
    model_config = SettingsConfigDict(env_prefix="TEST_")


@lru_cache()
def get_config(env_state: str):
    """Instantiate config based on the environment."""
    configs = {"dev": DevConfig, "prod": ProdConfig, "test": TestConfig}
    return configs[env_state]()


config = get_config(BaseConfig().ENV_STATE)

try:
    minio_client = Minio(
        endpoint=config.MINIO_ENDPOINT,
        access_key=config.MINIO_ROOT_USER,
        secret_key=config.MINIO_ROOT_PASSWORD,
        secure=config.MINIO_SECURE
    )
    # only try bucket ops if credentials worked
    bucket = config.MINIO_BUCKET
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)
    logger.info(f"MinIO bucket '{bucket}' is ready.")
except Exception as e:
    logger.error(f"MinIO setup failed: {e}")