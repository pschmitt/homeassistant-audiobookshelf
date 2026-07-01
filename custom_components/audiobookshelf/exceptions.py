"""Exceptions for Audiobookshelf."""

from __future__ import annotations


class AudiobookshelfError(Exception):
    """Base integration error."""


class CannotConnect(AudiobookshelfError):
    """Raised when Audiobookshelf cannot be reached."""


class InvalidAuth(AudiobookshelfError):
    """Raised when Audiobookshelf authentication fails."""


class SendFailed(AudiobookshelfError):
    """Raised when Audiobookshelf cannot send an ebook to a device."""


class MissingEbook(AudiobookshelfError):
    """Raised when an ABS item has no ebook file."""


class MissingDevice(AudiobookshelfError):
    """Raised when no e-reader device is configured."""
