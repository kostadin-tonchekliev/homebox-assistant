"""Parse user messages to detect inventory-check intent and extract item list."""

import re
from dataclasses import dataclass
from typing import Match


# Phrases that indicate "do I have these items" intent (case-insensitive)
INTENT_PATTERNS = [
    r"do\s+i\s+have\s*(?:the\s+following\s+)?(?:hardware|stuff|things|items?)?\s*[:\s]",
    r"do\s+we\s+have\s*(?:the\s+following\s+)?(?:hardware|stuff|things|items?)?\s*[:\s]",
    r"have\s+we\s+got\s*(?:the\s+following\s+)?(?:hardware|stuff|things|items?)?\s*[:\s]",
    r"do\s+i\s+have\s*:",
    r"do\s+we\s+have\s*:",
    r"have\s+(?:i|we)\s+got\s*:",
    r"check\s+(?:if\s+)?(?:i|we)\s+have\s*[:\s]",
    r"(?:do\s+)?(?:i|we)\s+have\s+(?:any\s+of\s+)?(?:these\s+)?[:\s]",
]


@dataclass
class ParsedRequest:
    """Result of parsing an inventory-check message."""

    intent_matched: bool
    items: list[str]


def _normalize(s: str) -> str:
    return " ".join(s.split()).strip()


def _extract_list_after_match(text: str, match: Match[str]) -> list[str]:
    """Extract bullet/numbered or comma-separated list after the intent phrase."""
    after = text[match.end() :].strip()
    if not after:
        return []

    items: list[str] = []
    lines = [line.strip() for line in after.splitlines() if line.strip()]

    for line in lines:
        # Bullet: "- M3x10" or "* M3x10" or "• M3x10"
        bullet = re.match(r"^[\-\*•]\s*(.+)$", line)
        if bullet:
            items.append(_normalize(bullet.group(1)))
            continue
        # Numbered: "1. M3x10" or "1) M3x10"
        numbered = re.match(r"^\d+[\.\)]\s*(.+)$", line)
        if numbered:
            items.append(_normalize(numbered.group(1)))
            continue
        # Plain line (no bullet) – treat as single item if no commas, else split
        if "," in line:
            for part in line.split(","):
                part = _normalize(part)
                if part:
                    items.append(part)
        else:
            items.append(_normalize(line))

    # If we got nothing from structured lines, try comma-separated on the whole block
    if not items and after:
        for part in after.split(","):
            part = _normalize(part)
            if part:
                items.append(part)

    return items


def parse_inventory_check(message_text: str) -> ParsedRequest:
    """
    Detect if the message is asking "do I have X, Y, Z?" and extract the list of items.
    """
    text = message_text.strip()
    if not text:
        return ParsedRequest(intent_matched=False, items=[])

    for pattern in INTENT_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            items = _extract_list_after_match(text, m)
            return ParsedRequest(intent_matched=True, items=items)

    # Fallback: entire message might be a comma-separated list (e.g. "M3x10, M3x15, ESP32")
    if text and len(text) < 500:
        parts = [_normalize(p) for p in text.split(",") if _normalize(p)]
        if 1 <= len(parts) <= 20:
            return ParsedRequest(intent_matched=True, items=parts)

    return ParsedRequest(intent_matched=False, items=[])


# Patterns for "what do I have under/in <location>"
LOCATION_ITEMS_PATTERNS = [
    r"what\s+do\s+(?:i|we)\s+have\s+under\s+(.+)$",
    r"what\s+do\s+(?:i|we)\s+have\s+in\s+(.+)$",
    r"what(?:'s|\s+is)\s+under\s+(.+)$",
    r"list\s+(?:items?\s+)?(?:in|under)\s+(.+)$",
    r"items?\s+(?:in|under)\s+(.+)$",
    r"show\s+me\s+(?:items?\s+)?(?:in|under)\s+(.+)$",
    r"(?:show\s+)?(?:items?\s+)?in\s+(.+)$",
]


@dataclass
class ParsedLocationRequest:
    """Result of parsing a 'items in location' request."""

    intent_matched: bool
    location_name: str | None = None


def parse_location_items_request(message_text: str) -> ParsedLocationRequest:
    """
    Detect if the message is asking for items in a location (e.g. "What do I have under Hardware").
    """
    text = message_text.strip()
    if not text:
        return ParsedLocationRequest(intent_matched=False, location_name=None)

    for pattern in LOCATION_ITEMS_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            name = _normalize(m.group(1))
            if name and len(name) < 200:
                return ParsedLocationRequest(
                    intent_matched=True, location_name=name
                )
    return ParsedLocationRequest(intent_matched=False, location_name=None)
