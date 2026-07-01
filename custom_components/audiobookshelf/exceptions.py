"""Exceptions for Audiobookshelf Kindle."""

from __future__ import annotations


class AudiobookshelfKindleError(Exception):
    """Base integration error."""


class CannotConnect(AudiobookshelfKindleError):
    """Raised when Audiobookshelf cannot be reached."""


class InvalidAuth(AudiobookshelfKindleError):
    """Raised when Audiobookshelf authentication fails."""


class SendFailed(AudiobookshelfKindleError):
    """Raised when a Kindle send fails."""


class MissingEbook(AudiobookshelfKindleError):
    """Raised when an ABS item has no ebook file."""


class UnsupportedFormat(AudiobookshelfKindleError):
    """Raised when an ebook format is not accepted."""


class AttachmentTooLarge(AudiobookshelfKindleError):
    """Raised when an ebook exceeds the configured size limit."""
