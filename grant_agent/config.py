import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    port: int = 8000
    env: str = "development"
    scan_hour: int = 6
    scan_minute: int = 0
    db_path: str = os.environ.get("DB_PATH", "grant_agent.db")

    # Email notifications
    notify_email: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
