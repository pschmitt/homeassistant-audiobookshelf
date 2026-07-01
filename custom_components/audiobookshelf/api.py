"""Audiobookshelf API client."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .exceptions import CannotConnect, InvalidAuth


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

    async def async_get_status(self) -> dict[str, Any]:
        """Return server status."""
        return await self.async_request("GET", "/api/status")

    async def async_get_item(self, item_id: str) -> dict[str, Any]:
        """Return an ABS library item."""
        return await self.async_request("GET", f"/api/items/{item_id}")

    async def async_download_candidates(self, item_id: str) -> list[bytes]:
        """Try known ebook download endpoints.

        ABS download endpoints have moved over time and the published API docs are
        stale. Keep this isolated so unsupported installs produce a clear repair.
        """
        candidates = (
            f"/api/items/{item_id}/ebook",
            f"/api/items/{item_id}/download",
            f"/api/items/{item_id}/file",
        )
        payloads: list[bytes] = []
        for path in candidates:
            try:
                data = await self.async_request("GET", path)
            except CannotConnect:
                continue
            if isinstance(data, bytes) and data:
                payloads.append(data)
        return payloads
