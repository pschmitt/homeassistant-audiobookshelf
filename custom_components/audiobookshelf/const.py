"""Constants for Audiobookshelf."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "audiobookshelf"
PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.EVENT]

CONF_ABS_URL = "abs_url"
CONF_ABS_TOKEN = "abs_token"
CONF_DEVICE_NAME = "device_name"
CONF_WEBHOOK_ID = "webhook_id"
CONF_VERIFY_SSL = "verify_ssl"

CONF_AUTO_SEND = "auto_send"

DEFAULT_NAME = "Audiobookshelf"
DEFAULT_VERIFY_SSL = True
DEFAULT_AUTO_SEND = False

SERVICE_SEND_EBOOK_TO_DEVICE = "send_ebook_to_device"
SERVICE_SEND_ITEM = "send_item"
SERVICE_RESET_SENT_ITEM = "reset_sent_item"

ISSUE_AUTH = "auth_failed"
ISSUE_CONNECTIVITY = "connectivity_failed"
ISSUE_SEND_FAILED = "send_failed"
ISSUE_MISSING_EBOOK = "missing_ebook"
ISSUE_MISSING_DEVICE = "missing_device"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sent_items"
SIGNAL_UPDATED = f"{DOMAIN}_updated"
EVENT_ITEM_RECEIVED = f"{DOMAIN}_item_received"
EVENT_LIBRARY_ITEM_RECEIVED = "library_item_received"
EVENT_LIBRARY_ITEM_UPDATED = "library_item_updated"
EVENT_LIBRARY_ITEM_UNKNOWN = "library_item"
