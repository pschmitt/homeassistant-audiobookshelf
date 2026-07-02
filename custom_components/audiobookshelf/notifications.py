"""Optional notifications for Audiobookshelf.

Sends a message to one or more user-configured notify targets when selected
events occur (a new book is added, an ebook is pushed to an e-reader, or a
send fails). Everything is opt-in: with no targets configured, nothing is sent.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_NOTIFY_EVENTS,
    CONF_NOTIFY_MESSAGE_BOOK_ADDED,
    CONF_NOTIFY_MESSAGE_EBOOK_SENT,
    CONF_NOTIFY_MESSAGE_SEND_FAILED,
    CONF_NOTIFY_TARGETS,
    CONF_NOTIFY_TITLE,
    DEFAULT_NOTIFY_EVENTS,
    DEFAULT_NOTIFY_MESSAGE_BOOK_ADDED,
    DEFAULT_NOTIFY_MESSAGE_EBOOK_SENT,
    DEFAULT_NOTIFY_MESSAGE_SEND_FAILED,
    DEFAULT_NOTIFY_TITLE,
    NOTIFY_EVENT_BOOK_ADDED,
    NOTIFY_EVENT_EBOOK_SENT,
    NOTIFY_EVENT_SEND_FAILED,
)

_LOGGER = logging.getLogger(__name__)

# Per-event message template: (options key, built-in default).
_MESSAGE_TEMPLATES: dict[str, tuple[str, str]] = {
    NOTIFY_EVENT_BOOK_ADDED: (CONF_NOTIFY_MESSAGE_BOOK_ADDED, DEFAULT_NOTIFY_MESSAGE_BOOK_ADDED),
    NOTIFY_EVENT_EBOOK_SENT: (CONF_NOTIFY_MESSAGE_EBOOK_SENT, DEFAULT_NOTIFY_MESSAGE_EBOOK_SENT),
    NOTIFY_EVENT_SEND_FAILED: (CONF_NOTIFY_MESSAGE_SEND_FAILED, DEFAULT_NOTIFY_MESSAGE_SEND_FAILED),
}


def title_authors(title: str | None, authors: list[str] | None) -> str:
    """Return ``"Title — Author, Author"`` (or just the title)."""
    title = title or ""
    if authors:
        return f"{title} — {', '.join(authors)}"
    return title


def _render(template: str, context: dict[str, Any]) -> str:
    """Fill a template, leaving unknown placeholders blank instead of raising."""
    safe = defaultdict(str, {key: ("" if value is None else str(value)) for key, value in context.items()})
    try:
        return template.format_map(safe).strip()
    except (KeyError, IndexError, ValueError):
        # A malformed custom template should never break a send/refresh.
        return template.strip()


async def async_send_event_notification(
    hass: HomeAssistant,
    entry: ConfigEntry,
    event_type: str,
    context: dict[str, Any],
) -> None:
    """Notify configured targets about ``event_type`` if the user opted in."""
    options = entry.options
    targets = options.get(CONF_NOTIFY_TARGETS) or []
    if not targets:
        return

    events = options.get(CONF_NOTIFY_EVENTS)
    if events is None:
        events = DEFAULT_NOTIFY_EVENTS
    if event_type not in events:
        return

    conf_key, default_message = _MESSAGE_TEMPLATES[event_type]
    message = _render(options.get(conf_key) or default_message, context)
    if not message:
        return
    title = (options.get(CONF_NOTIFY_TITLE) or DEFAULT_NOTIFY_TITLE).strip() or None

    for target in targets:
        await _async_call_target(hass, target, title, message)


async def _async_call_target(
    hass: HomeAssistant,
    target: str,
    title: str | None,
    message: str,
) -> None:
    """Dispatch one notification, tolerating both notify entities and services.

    ``notify.<name>`` may be a modern notify entity (called via
    ``notify.send_message`` with ``entity_id``) or a legacy notify service; any
    other ``domain.service`` value is called verbatim. Failures are logged, not
    raised, so a bad target never aborts the caller.
    """
    domain, _, service = target.partition(".")
    if not service:
        domain, service = "notify", target
    try:
        if domain == "notify" and hass.states.get(target) is not None:
            payload: dict[str, Any] = {"entity_id": target, "message": message}
            if title:
                payload["title"] = title
            await hass.services.async_call("notify", "send_message", payload, blocking=False)
            return
        payload = {"message": message}
        if title:
            payload["title"] = title
        await hass.services.async_call(domain, service, payload, blocking=False)
    except Exception:  # noqa: BLE001 - a bad notify target must not break refresh/send
        _LOGGER.warning("Audiobookshelf notification to %s failed", target, exc_info=True)
