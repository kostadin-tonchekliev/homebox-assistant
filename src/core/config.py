"""Load configuration from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


def get_str(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key, default)
    return value.strip() if value else default


def get_required(key: str) -> str:
    value = get_str(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


# HomeBox
HOMEBOX_BASE_URL: str | None = (
    (url := get_str("HOMEBOX_BASE_URL")) and url.rstrip("/") or None
)
HOMEBOX_USERNAME: str | None = get_str("HOMEBOX_USERNAME")
HOMEBOX_PASSWORD: str | None = get_str("HOMEBOX_PASSWORD")

# Telegram
TELEGRAM_BOT_TOKEN: str | None = get_str("TELEGRAM_BOT_TOKEN")
