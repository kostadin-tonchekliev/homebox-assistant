"""Telegram bot: handlers and run entry."""

from src.bot.handlers import register_handlers
from src.bot.run import main

__all__ = ["main", "register_handlers"]
