"""Async client for the HomeBox REST API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HomeBoxItem:
    """Simplified item from HomeBox API."""

    id: str
    name: str
    quantity: int
    archived: bool
    description: str | None = None
    location_name: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> HomeBoxItem:
        location = data.get("location")
        location_name: str | None = None
        if isinstance(location, dict):
            location_name = location.get("name") or None
        elif location is not None and not isinstance(location, dict):
            location_name = str(location)
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            quantity=data.get("quantity", 0) or 0,
            archived=data.get("archived", False),
            description=data.get("description") or None,
            location_name=location_name,
        )


@dataclass
class HomeBoxLocation:
    """Location from HomeBox API (GET /v1/locations)."""

    id: str
    name: str
    item_count: int | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> HomeBoxLocation:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            item_count=data.get("itemCount"),
        )


class HomeBoxClient:
    """Async client for HomeBox API with Bearer auth (username/password login)."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._username = username.strip()
        self._password = password.strip()
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _make_client(self, token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            token = await self._login()
            self._client = self._make_client(token)
        return self._client

    def _parse_login_token(self, data: dict[str, Any]) -> str:
        """Extract token from login response; support flat or nested shapes."""
        for key in ("token", "access_token", "accessToken"):
            val = data.get(key)
            if val and isinstance(val, str):
                return self._normalize_token(val)
        for wrapper in ("data", "result", "response"):
            nested = data.get(wrapper)
            if isinstance(nested, dict):
                for key in ("token", "access_token", "accessToken"):
                    val = nested.get(key)
                    if val and isinstance(val, str):
                        return self._normalize_token(val)
        raise ValueError(
            f"Login response missing token. Keys received: {list(data.keys())}"
        )

    @staticmethod
    def _normalize_token(token: str) -> str:
        t = token.strip()
        if t.lower().startswith("bearer "):
            t = t[7:].strip()
        return t

    async def _login(self) -> str:
        """Obtain Bearer token via POST /api/v1/users/login (form-encoded)."""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        ) as client:
            r = await client.post(
                "/api/v1/users/login",
                data={
                    "username": self._username,
                    "password": self._password,
                },
            )
            r.raise_for_status()
            data = r.json()
            token = self._parse_login_token(data)
            logger.info("HomeBox login succeeded (token length=%d)", len(token))
            return token

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _search_items_once(
        self,
        client: httpx.AsyncClient,
        q: str,
        location_ids: list[str] | None,
        page_size: int,
    ) -> list[HomeBoxItem]:
        params: dict[str, Any] = {"pageSize": page_size}
        if q:
            params["q"] = q
        if location_ids:
            params["locations"] = location_ids
        r = await client.get("/api/v1/items", params=params)
        if r.status_code == 401:
            try:
                body = r.text
                if len(body) < 500:
                    logger.info("HomeBox 401 response: %s", body)
                else:
                    logger.info("HomeBox 401 response (truncated): %s...", body[:500])
            except Exception:
                pass
        r.raise_for_status()
        data = r.json()
        items_data = data.get("items") or []
        return [HomeBoxItem.from_api(i) for i in items_data]

    async def search_items(
        self,
        q: str,
        location_ids: list[str] | None = None,
        page_size: int = 10,
    ) -> list[HomeBoxItem]:
        client = await self._get_client()
        try:
            return await self._search_items_once(
                client, q, location_ids, page_size
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 401:
                raise
            logger.warning("HomeBox API returned 401 Unauthorized; re-logging in.")
            await self.close()
            new_token = await self._login()
            self._client = self._make_client(new_token)
            return await self._search_items_once(
                self._client, q, location_ids, page_size
            )

    async def get_locations(self) -> list[HomeBoxLocation]:
        """Fetch all locations (GET /api/v1/locations)."""
        client = await self._get_client()
        r = await client.get("/api/v1/locations")
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            return []
        return [HomeBoxLocation.from_api(item) for item in data]

    async def get_items_in_location(
        self, location_id: str, page_size: int = 200
    ) -> list[HomeBoxItem]:
        return await self.search_items(
            q="",
            location_ids=[location_id],
            page_size=page_size,
        )

    async def __aenter__(self) -> HomeBoxClient:
        await self._get_client()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
