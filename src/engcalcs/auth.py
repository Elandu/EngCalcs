# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Elandu and contributors

"""Authentication helpers shared by the EngCalcs REST API and MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import httpx
from fastapi import HTTPException, Request

DEFAULT_SUPABASE_URL = "https://amfmmkonklwcohbsdiic.supabase.co"
DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_3fLu3fYYX9oMDwZ52CpKBA_v6vItmxH"

CALCULATIONS_READ = "calculations:read"
CALCULATIONS_RUN = "calculations:run"
MCP_CONNECT = "mcp:connect"
USER_SCOPES = (CALCULATIONS_READ, CALCULATIONS_RUN, MCP_CONNECT)


def _setting(name: str, legacy_name: str, default: str) -> str:
    return os.environ.get(name) or os.environ.get(legacy_name) or default


def is_api_key_token(token: str) -> bool:
    return token.startswith(("eng_live_", "oc_live_"))


@dataclass(frozen=True)
class AuthContext:
    """Authenticated caller identity exposed to API/MCP handlers."""

    subject: str
    auth_type: str
    scopes: tuple[str, ...]
    organisation_id: str | None = None
    api_key_id: str | None = None


class Authenticator(Protocol):
    async def authenticate_request(
        self,
        request: Request,
        required_scopes: tuple[str, ...],
    ) -> AuthContext: ...


class EngCalcsAuthenticator:
    """Validate Supabase user JWTs or organisation-scoped EngCalcs API keys."""

    def __init__(
        self,
        *,
        supabase_url: str | None = None,
        publishable_key: str | None = None,
        timeout_seconds: float = 8.0,
    ) -> None:
        configured_url = _setting(
            "ENGCALCS_SUPABASE_URL", "OPENCALCS_SUPABASE_URL", DEFAULT_SUPABASE_URL
        )
        self.supabase_url = (supabase_url or configured_url).rstrip("/")
        self.publishable_key = publishable_key or _setting(
            "ENGCALCS_SUPABASE_PUBLISHABLE_KEY",
            "OPENCALCS_SUPABASE_PUBLISHABLE_KEY",
            DEFAULT_SUPABASE_PUBLISHABLE_KEY,
        )
        self.timeout_seconds = timeout_seconds

    async def authenticate_request(
        self,
        request: Request,
        required_scopes: tuple[str, ...],
    ) -> AuthContext:
        api_key = (
            request.headers.get("x-engcalcs-key") or request.headers.get("x-opencalcs-key", "")
        ).strip()
        if api_key:
            return await self.verify_api_key(api_key, required_scopes)

        authorization = request.headers.get("authorization", "").strip()
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
            if is_api_key_token(token):
                return await self.verify_api_key(token, required_scopes)
            return await self.verify_user_token(token, required_scopes)

        raise HTTPException(
            status_code=401,
            detail="Authentication required. Supply a Supabase bearer token or EngCalcs API key.",
        )

    async def verify_api_key(
        self,
        api_key: str,
        required_scopes: tuple[str, ...] = (),
    ) -> AuthContext:
        url = f"{self.supabase_url}/functions/v1/engcalcs-key-verify"
        payload = {"required_scopes": list(required_scopes)}
        headers = {"x-engcalcs-key": api_key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 404:
                    legacy_url = f"{self.supabase_url}/functions/v1/opencalcs-key-verify"
                    legacy_headers = {**headers, "x-opencalcs-key": api_key}
                    response = await client.post(legacy_url, headers=legacy_headers, json=payload)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="API-key verifier unavailable.") from exc

        if response.status_code == 403:
            raise HTTPException(status_code=403, detail="Insufficient API-key scope.")
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired API key.")

        payload = response.json()
        scopes = tuple(str(scope) for scope in payload.get("scopes", []))
        return AuthContext(
            subject=f"api-key:{payload['api_key_id']}",
            auth_type="api_key",
            scopes=scopes,
            organisation_id=payload.get("organisation_id"),
            api_key_id=payload.get("api_key_id"),
        )

    async def verify_user_token(
        self,
        token: str,
        required_scopes: tuple[str, ...] = (),
    ) -> AuthContext:
        url = f"{self.supabase_url}/auth/v1/user"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    url,
                    headers={
                        "apikey": self.publishable_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=503, detail="Supabase Auth unavailable.") from exc

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired user token.")

        payload = response.json()
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user token.")

        missing = [scope for scope in required_scopes if scope not in USER_SCOPES]
        if missing:
            raise HTTPException(status_code=403, detail="Insufficient user scope.")

        return AuthContext(
            subject=f"user:{user_id}",
            auth_type="user",
            scopes=USER_SCOPES,
        )


OpenCalcsAuthenticator = EngCalcsAuthenticator


class AllowAllAuthenticator:
    """Explicit test/development authenticator; never selected automatically."""

    async def authenticate_request(
        self,
        request: Request,
        required_scopes: tuple[str, ...],
    ) -> AuthContext:
        return AuthContext(
            subject="test",
            auth_type="test",
            scopes=USER_SCOPES,
        )
