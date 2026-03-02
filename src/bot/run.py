"""Bot entry point: build app, register handlers, run polling."""

import logging
import sys

from telegram.ext import Application

from src.bot.handlers import register_handlers
from src.core.config import (
    HOMEBOX_BASE_URL,
    HOMEBOX_PASSWORD,
    HOMEBOX_USERNAME,
    TELEGRAM_BOT_TOKEN,
)
from src.homebox import HomeBoxClient

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)
    if not HOMEBOX_BASE_URL:
        logger.error("HOMEBOX_BASE_URL is not set")
        sys.exit(1)
    if not HOMEBOX_USERNAME or not HOMEBOX_PASSWORD:
        logger.error("HOMEBOX_USERNAME and HOMEBOX_PASSWORD are required")
        sys.exit(1)

    client = HomeBoxClient(
        base_url=HOMEBOX_BASE_URL,
        username=HOMEBOX_USERNAME,
        password=HOMEBOX_PASSWORD,
    )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(app, client)

    logger.info("Bot starting. Polling for messages.")
    app.run_polling(drop_pending_updates=True)
