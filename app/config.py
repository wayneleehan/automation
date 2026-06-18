"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime settings with development-friendly defaults."""

    app_name: str = os.getenv("APP_NAME", "chat-to-obsidian")
    app_env: str = os.getenv("APP_ENV", "development")
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "8000"))
    vault_path: Path = Path(os.getenv("VAULT_PATH", "vault"))
    line_channel_access_token: str = os.getenv(
        "LINE_CHANNEL_ACCESS_TOKEN",
        "",
    )
    line_channel_secret: str = os.getenv("LINE_CHANNEL_SECRET", "")


settings = Settings()
