"""Constants for Audiobookshelf Kindle."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "audiobookshelf"
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

CONF_ABS_URL = "abs_url"
CONF_ABS_TOKEN = "abs_token"
CONF_RECIPIENT_EMAIL = "recipient_email"
CONF_SENDER_EMAIL = "sender_email"
CONF_SMTP_HOST = "smtp_host"
CONF_SMTP_PORT = "smtp_port"
CONF_SMTP_USERNAME = "smtp_username"
CONF_SMTP_PASSWORD = "smtp_password"
CONF_SMTP_STARTTLS = "smtp_starttls"
CONF_WEBHOOK_ID = "webhook_id"
CONF_VERIFY_SSL = "verify_ssl"

CONF_AUTO_SEND = "auto_send"
CONF_ACCEPTED_FORMATS = "accepted_formats"
CONF_MAX_ATTACHMENT_MB = "max_attachment_mb"
CONF_LOCAL_ABS_ROOT = "local_abs_root"
CONF_HA_LOCAL_ROOT = "ha_local_root"

DEFAULT_NAME = "Audiobookshelf"
DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_STARTTLS = True
DEFAULT_VERIFY_SSL = True
DEFAULT_AUTO_SEND = False
DEFAULT_ACCEPTED_FORMATS = ["epub", "pdf"]
DEFAULT_MAX_ATTACHMENT_MB = 45

SERVICE_SEND_ITEM = "send_item"
SERVICE_RESET_SENT_ITEM = "reset_sent_item"

ISSUE_AUTH = "auth_failed"
ISSUE_CONNECTIVITY = "connectivity_failed"
ISSUE_SEND_FAILED = "send_failed"
ISSUE_MISSING_EBOOK = "missing_ebook"
ISSUE_UNSUPPORTED_FORMAT = "unsupported_format"
ISSUE_SIZE_LIMIT = "size_limit"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.sent_items"
SIGNAL_UPDATED = f"{DOMAIN}_updated"
EVENT_ITEM_RECEIVED = f"{DOMAIN}_item_received"
