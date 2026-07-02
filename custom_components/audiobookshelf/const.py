"""Constants for Audiobookshelf."""

from __future__ import annotations

import json
from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "audiobookshelf"
PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.EVENT, Platform.SELECT]

SCAN_INTERVAL = timedelta(minutes=5)

CONF_ABS_URL = "abs_url"
CONF_ABS_TOKEN = "abs_token"
CONF_DEVICE_NAME = "device_name"
CONF_VERIFY_SSL = "verify_ssl"

# Sentinel CONF_DEVICE_NAME/device_name value meaning "every configured e-reader
# device", not a real Audiobookshelf device name.
ALL_DEVICES = "all"
ALL_DEVICES_LABEL = "All devices"

CONF_AUTO_SEND = "auto_send"

CONF_NOTIFY_TARGETS = "notify_targets"
CONF_NOTIFY_EVENTS = "notify_events"
CONF_NOTIFY_TITLE = "notify_title"
CONF_NOTIFY_DATA = "notify_data"
CONF_NOTIFY_MESSAGE_BOOK_ADDED = "notify_message_book_added"
CONF_NOTIFY_MESSAGE_EBOOK_SENT = "notify_message_ebook_sent"
CONF_NOTIFY_MESSAGE_SEND_FAILED = "notify_message_send_failed"

NOTIFY_EVENT_BOOK_ADDED = "book_added"
NOTIFY_EVENT_EBOOK_SENT = "ebook_sent"
NOTIFY_EVENT_SEND_FAILED = "send_failed"
NOTIFY_EVENTS = [
    NOTIFY_EVENT_BOOK_ADDED,
    NOTIFY_EVENT_EBOOK_SENT,
    NOTIFY_EVENT_SEND_FAILED,
]

DEFAULT_NAME = "Audiobookshelf"
DEFAULT_VERIFY_SSL = True
DEFAULT_AUTO_SEND = False

DEFAULT_NOTIFY_EVENTS = [NOTIFY_EVENT_BOOK_ADDED, NOTIFY_EVENT_EBOOK_SENT]
DEFAULT_NOTIFY_TITLE = "Audiobookshelf"
DEFAULT_NOTIFY_DATA_DICT = {
    "tag": "audiobookshelf",
    "timeout": 3600,
}
DEFAULT_NOTIFY_DATA = json.dumps(DEFAULT_NOTIFY_DATA_DICT, indent=2, sort_keys=True)
DEFAULT_NOTIFY_MESSAGE_BOOK_ADDED = "📚 New in {library}: {title_authors}"
DEFAULT_NOTIFY_MESSAGE_EBOOK_SENT = "📖 Sent “{title}” to {device}"
DEFAULT_NOTIFY_MESSAGE_SEND_FAILED = "⚠️ Couldn’t send “{title}” to {device}: {reason}"

SERVICE_SEND_EBOOK_TO_DEVICE = "send_ebook_to_device"
SERVICE_SEND_ITEM = "send_item"
SERVICE_RESET_SENT_ITEM = "reset_sent_item"

ISSUE_AUTH = "auth_failed"
ISSUE_CONNECTIVITY = "connectivity_failed"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sent_items"
SIGNAL_UPDATED = f"{DOMAIN}_updated"
EVENT_ITEM_RECEIVED = f"{DOMAIN}_item_received"
EVENT_LIBRARY_ITEM_RECEIVED = "library_item_received"
EVENT_LIBRARY_ITEM_UPDATED = "library_item_updated"
EVENT_LIBRARY_ITEM_UNKNOWN = "library_item"
