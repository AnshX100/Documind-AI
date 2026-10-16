"""Base configuration module for DocuMind AI application."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class BaseConfig:
    """Base application configuration containing shared default settings."""

    BASE_DIR = BASE_DIR
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-dev-secret-key-must-be-changed")
    
    # Database Settings
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Upload Settings
    UPLOAD_FOLDER: str = str(BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)) # 16 MB
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "png", "jpg", "jpeg", "webp", "docx"}
    # AI & OCR API Settings
    TESSERACT_CMD: str | None = os.getenv("TESSERACT_CMD")
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "eng")
    
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "none")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Controlled LLM Assistant Layer Settings (Sprint 9 Phase 3)
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", os.getenv("AI_PROVIDER", "none"))
    LLM_API_KEY: str | None = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY"))
    LLM_MODEL: str = os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "10"))

    # Rate Limiter Settings (Sprint 10.5C)
    RATELIMIT_STORAGE_URI: str = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    # Google OAuth 2.0 / OIDC Settings (Sprint 11)
    GOOGLE_CLIENT_ID: str | None = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/auth/google/callback")



