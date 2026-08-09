"""Base configuration module for DocuMind AI application."""

import os
from pathlib import Path


class BaseConfig:
    """Base application configuration containing shared default settings."""

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-dev-secret-key-must-be-changed")
    
    # Database Settings
    SQLALCHEMY_DATABASE_URI: str = os.environ.get(
        "DATABASE_URL", 
        "mysql+pymysql://root:ansh%40%23%246969@localhost:3306/documind_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Upload Settings
    UPLOAD_FOLDER: str = str(BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)) # 16 MB
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "png", "jpg", "jpeg"}

    # AI & OCR API Settings
    TESSERACT_CMD: str | None = os.getenv("TESSERACT_CMD")
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "eng")
    
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
