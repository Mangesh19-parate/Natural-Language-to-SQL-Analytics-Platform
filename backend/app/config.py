import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "local"
    DEBUG: bool = True

    # Database URLs
    METADATA_DB_URL: Optional[str] = None
    METADATA_SQLITE_URL: str = "sqlite:///./local_data/metadata.db"
    
    BUSINESS_DB_URL: Optional[str] = None
    BUSINESS_ADMIN_DB_URL: Optional[str] = None
    BUSINESS_SQLITE_URL: str = "sqlite:///./local_data/business.db"

    # Security & JWT
    JWT_SECRET_KEY: str = "dev-insecure-secret-key-replace-in-production-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Settings
    LLM_PROVIDER: str = "mock"  # 'openai' | 'groq' | 'gemini' | 'openrouter' | 'mock'
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    DEFAULT_MODEL_NAME: str = "gpt-4o-mini"
    DEFAULT_TEMPERATURE: float = 0.0

    # CORS Settings
    ALLOWED_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def validate_production_environment(self) -> None:
        """Enforces security boundaries at boot time: fails hard if running in production with dev secrets."""
        if self.ENVIRONMENT.lower() == "production":
            if not self.JWT_SECRET_KEY or "dev-insecure" in self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                raise RuntimeError(
                    "CRITICAL SECURITY ERROR: Production deployment must configure a high-entropy JWT_SECRET_KEY (min 32 characters)."
                )

    def get_effective_metadata_db_url(self) -> str:
        """Returns PostgreSQL URL if configured and reachable, otherwise SQLite local path."""
        if self.METADATA_DB_URL and "postgresql" in self.METADATA_DB_URL:
            return self.METADATA_DB_URL
        # Ensure local_data dir exists if using sqlite
        os.makedirs("./local_data", exist_ok=True)
        return self.METADATA_SQLITE_URL

    def get_effective_business_db_url(self, admin: bool = False) -> str:
        """Returns Business DB connection string (readonly by default, or admin for migrations/seeding)."""
        if admin and self.BUSINESS_ADMIN_DB_URL and "postgresql" in self.BUSINESS_ADMIN_DB_URL:
            return self.BUSINESS_ADMIN_DB_URL
        if not admin and self.BUSINESS_DB_URL and "postgresql" in self.BUSINESS_DB_URL:
            return self.BUSINESS_DB_URL
        os.makedirs("./local_data", exist_ok=True)
        return self.BUSINESS_SQLITE_URL


settings = Settings()
settings.validate_production_environment()

