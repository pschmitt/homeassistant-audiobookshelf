"""Audiobookshelf API client."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ClientResponseError, ClientSession

from .exceptions import AudiobookshelfError, CannotConnect, InvalidAuth, SendFailed


class AudiobookshelfClient:
    """Small async client for the Audiobookshelf API."""

    def __init__(self, session: ClientSession, base_url: str, token: str) -> None:
        """Initialize the client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token = token

    @property
    def base_url(self) -> str:
        """Return configured base URL."""
        return self._base_url

    async def async_request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Run an authenticated ABS API request."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with asyncio.timeout(30):
                response = await self._session.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
                if response.content_type == "application/json":
                    return await response.json()
                return await response.read()
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise InvalidAuth("Audiobookshelf rejected the API token") from err
            raise CannotConnect(f"Audiobookshelf returned HTTP {err.status}") from err
        except (TimeoutError, ClientError) as err:
            raise CannotConnect("Could not connect to Audiobookshelf") from err

    async def async_validate(self) -> dict[str, Any]:
        """Validate credentials and return server/user information."""
        return await self.async_request("GET", "/api/me")

    async def async_get_ereader_devices(self) -> list[dict[str, Any]]:
        """Return e-reader devices configured on the server.

        ABS stores e-reader devices in the (admin-only) email settings. Fall back
        to the authenticated user's own devices. Never raises: a missing or
        forbidden source just yields an empty list so the rest of the refresh
        still succeeds.
        """
        devices = await self._async_get_ereader_devices_from_email_settings()
        if devices:
            return devices
        return await self._async_get_ereader_devices_from_me()

    async def _async_get_ereader_devices_from_email_settings(self) -> list[dict[str, Any]]:
        """Return e-reader devices from the server email settings."""
        try:
            payload = await self.async_request("GET", "/api/emails/settings")
        except AudiobookshelfError:
            return []
        settings = payload.get("settings") if isinstance(payload, dict) else None
        devices = settings.get("ereaderDevices") if isinstance(settings, dict) else None
        return devices if isinstance(devices, list) else []

    async def _async_get_ereader_devices_from_me(self) -> list[dict[str, Any]]:
        """Return e-reader devices attached to the authenticated user."""
        try:
            me = await self.async_validate()
        except AudiobookshelfError:
            return []
        devices = me.get("ereaderDevices") or []
        return devices if isinstance(devices, list) else []

    async def async_get_status(self) -> dict[str, Any]:
        """Return server status.

        The public ``/status`` endpoint carries ``serverVersion`` and ``isInit``;
        ``/api/status`` does not exist.
        """
        return await self.async_request("GET", "/status")

    async def async_get_libraries(self) -> list[dict[str, Any]]:
        """Return libraries visible to the authenticated user."""
        payload = await self.async_request("GET", "/api/libraries")
        libraries = payload.get("libraries") if isinstance(payload, dict) else []
        return libraries if isinstance(libraries, list) else []

    async def async_get_recently_added_book_for_library(
        self,
        library_id: str,
        library_name: str | None,
    ) -> dict[str, Any] | None:
        """Return the most recently added item from a library."""
        query = urlencode(
            {
                "limit": 1,
                "page": 0,
                "sort": "addedAt",
                "desc": 1,
            }
        )
        payload = await self.async_request("GET", f"/api/libraries/{library_id}/items?{query}")
        total = payload.get("total") if isinstance(payload, dict) else None
        results = payload.get("results") if isinstance(payload, dict) else []
        if not isinstance(results, list) or not results:
            return {
                "_libraryName": library_name,
                "_libraryId": library_id,
                "_libraryTotal": total,
            }
        item = results[0]
        if not isinstance(item, dict):
            return {
                "_libraryName": library_name,
                "_libraryId": library_id,
                "_libraryTotal": total,
            }
        item["_libraryName"] = library_name
        item["_libraryId"] = library_id
        item["_libraryTotal"] = total
        return item

    async def async_get_item(self, item_id: str) -> dict[str, Any]:
        """Return an ABS library item."""
        return await self.async_request("GET", f"/api/items/{item_id}")

    async def async_send_ebook_to_device(self, item_id: str, device_name: str) -> None:
        """Ask Audiobookshelf to send an ebook to a configured e-reader device."""
        try:
            await self.async_request(
                "POST",
                "/api/emails/send-ebook-to-device",
                json={"libraryItemId": item_id, "deviceName": device_name},
            )
        except CannotConnect as err:
            raise SendFailed(str(err)) from err
