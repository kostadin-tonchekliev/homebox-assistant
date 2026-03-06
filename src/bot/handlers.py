"""Telegram message handlers for the HomeBox inventory bot."""

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from src.core.parser import parse_inventory_check, parse_location_items_request
from src.homebox import HomeBoxClient, HomeBoxItem, HomeBoxLocation

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)

HELP_TEXT = """I can check your HomeBox inventory from Telegram. Currently supported features:

*Check items* — e.g. Do I have: M3x10, M3x15, ESP32C3
*Items in a location* — e.g. List items in Hardware

*Commands:* /help · /locations (list all locations)"""

UNSUPPORTED_TEXT = """Command not supported. Currently supported:
• Do I have: <list of items>
• What do I have under <location>
• /help
• /locations"""


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help: show usage."""
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_locations(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    homebox_client: HomeBoxClient,
) -> None:
    """Handle /locations: list all locations from HomeBox."""
    if not update.message:
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        locations = await homebox_client.get_locations()
    except Exception as e:
        logger.exception("Failed to fetch locations: %s", e)
        await update.message.reply_text(
            "Could not load locations. HomeBox may be unreachable."
        )
        return
    if not locations:
        await update.message.reply_text("No locations found.")
        return
    lines = ["📍 Locations"]
    for loc in locations:
        count = f" ({loc.item_count} items)" if loc.item_count is not None else ""
        lines.append(f"  • {loc.name}{count}")
    await update.message.reply_text("\n".join(lines))


def _search_term_in_item(search: str, item: HomeBoxItem) -> bool:
    s = search.lower().strip()
    name = (item.name or "").lower()
    desc = (item.description or "").lower()
    return s in name or s in desc or (len(s) >= 2 and (s in name or s in desc))


def _get_matching_available_items(
    items: list[HomeBoxItem], search_term: str
) -> list[HomeBoxItem]:
    return [
        item
        for item in items
        if not item.archived
        and item.quantity is not None
        and item.quantity >= 1
        and _search_term_in_item(search_term, item)
    ]


def _get_primary_brand_tag(item: HomeBoxItem) -> str | None:
    if not item.tags:
        return None
    for tag in item.tags:
        t = (tag or "").strip()
        if t:
            return t
    return None


def _format_item_with_optional_brand(
    item: HomeBoxItem, *, include_brand: bool
) -> str:
    if include_brand:
        brand = _get_primary_brand_tag(item)
        if brand:
            return f"{item.name} (qty: {item.quantity}, brand: {brand})"
    return f"{item.name} (qty: {item.quantity})"


async def handle_location_items(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    homebox_client: HomeBoxClient,
    location_name: str,
) -> None:
    if not update.message:
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    try:
        locations = await homebox_client.get_locations()
    except Exception as e:
        logger.exception("Failed to fetch locations: %s", e)
        await update.message.reply_text(
            "Could not load locations. HomeBox may be unreachable."
        )
        return
    matched: HomeBoxLocation | None = None
    for loc in locations:
        if loc.name and loc.name.strip().lower() == location_name.strip().lower():
            matched = loc
            break
    if not matched:
        names = ", ".join(l.name for l in locations if l.name) or "none"
        await update.message.reply_text(
            f"Location \"{location_name}\" not found. Use /locations to see available locations.\n\nAvailable: {names}"
        )
        return
    try:
        items = await homebox_client.get_items_in_location(matched.id)
    except Exception as e:
        logger.exception("Failed to fetch items for location %s: %s", matched.name, e)
        await update.message.reply_text(
            "Could not load items for that location. HomeBox may be unreachable."
        )
        return
    items = [i for i in items if not i.archived and (i.quantity or 0) > 0]
    lines = [f"📦 {matched.name}"]
    include_brand = matched.name.strip().lower() == "filament"
    if not items:
        lines.append("  (no items in stock)")
    else:
        for item in items:
            lines.append(
                f"  • {_format_item_with_optional_brand(item, include_brand=include_brand)}"
            )
    await update.message.reply_text("\n".join(lines))


async def handle_inventory_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    homebox_client: HomeBoxClient,
) -> None:
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    loc_parsed = parse_location_items_request(text)
    if loc_parsed.intent_matched and loc_parsed.location_name:
        await handle_location_items(
            update, context, homebox_client=homebox_client, location_name=loc_parsed.location_name
        )
        return

    parsed = parse_inventory_check(text)
    if not parsed.intent_matched:
        await update.message.reply_text(UNSUPPORTED_TEXT)
        return

    if not parsed.items:
        await update.message.reply_text(
            "I didn't find any items in your message. List them after \"Do I have\" (e.g. with bullets or commas)."
        )
        return

    if len(parsed.items) > 30:
        await update.message.reply_text("Please list at most 30 items at a time.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        locations = await homebox_client.get_locations()
        all_location_ids = [loc.id for loc in locations if loc.id]
    except Exception as e:
        logger.exception("Failed to fetch locations: %s", e)
        await update.message.reply_text(
            "Could not load locations. HomeBox may be unreachable."
        )
        return

    available_items: list[HomeBoxItem] = []
    unavailable: list[str] = []
    failed: list[str] = []

    for item_query in parsed.items:
        try:
            results = await homebox_client.search_items(
                q=item_query,
                location_ids=all_location_ids if all_location_ids else None,
                page_size=100,
            )
            matches = _get_matching_available_items(results, item_query)
            if matches:
                available_items.extend(matches)
            else:
                unavailable.append(item_query)
        except Exception as e:
            logger.exception("HomeBox search failed for %r: %s", item_query, e)
            failed.append(item_query)

    lines: list[str] = []
    if available_items:
        lines.append("✅ Available")
        for item in available_items:
            loc = f" — {item.location_name}" if item.location_name else ""
            include_brand = (item.location_name or "").strip().lower() == "filament"
            item_text = _format_item_with_optional_brand(item, include_brand=include_brand)
            lines.append(f"  • {item_text}{loc}")
    if unavailable:
        if lines:
            lines.append("")
        lines.append("❌ Unavailable")
        for name in unavailable:
            lines.append(f"  • {name}")
    if failed:
        if lines:
            lines.append("")
        lines.append("⚠️ Couldn't check (HomeBox may be unreachable)")
        for name in failed:
            lines.append(f"  • {name}")

    if not lines:
        lines.append("No items to show.")

    await update.message.reply_text("\n".join(lines))


def register_handlers(app: "Application", homebox_client: HomeBoxClient) -> None:
    from telegram.ext import CommandHandler, MessageHandler, filters

    app.add_handler(CommandHandler("help", cmd_help))

    async def locations_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await cmd_locations(update, context, homebox_client=homebox_client)

    app.add_handler(CommandHandler("locations", locations_handler))

    async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await handle_inventory_check(update, context, homebox_client=homebox_client)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
