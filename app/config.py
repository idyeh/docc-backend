import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "docc-app")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///docc.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "docc-app")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    JWT_VERIFY_SUB = False
    # MinIO Config
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER")
    MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD")
    MINIO_BUCKET = os.getenv("MINIO_BUCKET", "docc-files")
    MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() in ("true","1","yes")
