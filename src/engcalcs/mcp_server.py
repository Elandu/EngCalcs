# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
# Copyright (c) 2026 Elandu and contributors

"""Model Context Protocol server for the EngCalcs calculation registry."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from typing import Any

from fastapi import HTTPException
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

from engcalcs import __version__
from engcalcs.auth import (
    CALCULATIONS_READ,
    CALCULATIONS_RUN,
    MCP_CONNECT,
    EngCalcsAuthenticator,
    is_api_key_token,
)
from engcalcs.connections import connection_catalogue, module_catalogue
from engcalcs.provenance import plugin_provenance, runtime_provenance
from engcalcs.registry import CalculationRegistry
from engcalcs.workflows import run_openwind_site_workflow

MCP_TRANSPORTS = ("stdio", "streamable-http")


def _setting(name: str, legacy_name: str, default: str) -> str:
    return os.environ.get(name) or os.environ.get(legacy_name) or default


MCP_RESOURCE_URL = _setting(
    "ENGCALCS_MCP_RESOURCE_URL",
    "OPENCALCS_MCP_RESOURCE_URL",
    "https://opencalcs-mcp.onrender.com/mcp",
)
SUPABASE_ISSUER_URL = _setting(
    "ENGCALCS_AUTH_ISSUER_URL",
    "OPENCALCS_AUTH_ISSUER_URL",
    "https://amfmmkonklwcohbsdiic.supabase.co/auth/v1",
)
runtime = CalculationRegistry()
_authenticator = EngCalcsAuthenticator()


class EngCalcsTokenVerifier(TokenVerifier):
    """Accept Supabase user tokens or organisation-scoped EngCalcs API keys."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            if is_api_key_token(token):
                context = await _authenticator.verify_api_key(token)
            else:
                context = await _authenticator.verify_user_token(token)
        except HTTPException:
            return None

        return AccessToken(
            token=token,
            client_id=context.organisation_id or context.subject,
            scopes=list(context.scopes),
            resource=MCP_RESOURCE_URL,
            subject=context.subject,
        )


mcp = FastMCP(
    "EngCalcs",
    instructions=(
        "Discover and execute versioned engineering calculations exposed by installed "
        "EngCalcs plugins. Calculation outputs must be treated as engineering calculation "
        "records and reviewed by an appropriately qualified engineer where required."
    ),
    stateless_http=True,
    json_response=True,
    token_verifier=EngCalcsTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(SUPABASE_ISSUER_URL),
        resource_server_url=AnyHttpUrl(MCP_RESOURCE_URL),
        required_scopes=[MCP_CONNECT],
        validate_token_resource=False,
    ),
)
mcp._mcp_server.version = __version__


def _require_scope(scope: str) -> None:
    """Require a scope for HTTP MCP calls; stdio remains a trusted local transport."""

    access_token = get_access_token()
    if access_token is None:
        return
    if scope not in access_token.scopes:
        raise PermissionError(f"Missing required scope: {scope}")


def _descriptor(calculation_id: str) -> dict[str, Any]:
    return runtime.describe(calculation_id)


@mcp.tool()
def list_plugins() -> list[dict[str, Any]]:
    """List installed engineering calculation plugins and their versions."""

    _require_scope(CALCULATIONS_READ)
    return [
        {
            **plugin.descriptor(),
            "provenance": plugin_provenance(plugin),
            "runtime": runtime_provenance(),
        }
        for plugin in runtime.plugins
    ]


@mcp.tool()
def list_calculations(
    plugin_id: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """List calculations available through EngCalcs, optionally filtered."""

    _require_scope(CALCULATIONS_READ)
    calculations = runtime.list_calculations()
    if plugin_id is not None:
        calculations = [
            item for item in calculations if item.get("plugin", {}).get("id") == plugin_id
        ]
    if category is not None:
        calculations = [
            item
            for item in calculations
            if str(item.get("category", "")).casefold() == category.casefold()
        ]
    return calculations


@mcp.tool()
def list_engineering_modules() -> list[dict[str, Any]]:
    """List supported AS modules, declared calculation scope and installed versions."""

    _require_scope(CALCULATIONS_READ)
    return module_catalogue(runtime)


@mcp.tool()
def list_calculation_connections(
    calculation_id: str | None = None,
) -> list[dict[str, Any]]:
    """Show compatible direct links and engineering review/adapter requirements.

    Catalogue entries are advisory. Calling this tool does not calculate,
    transfer, accept or approve a design input.
    """

    _require_scope(CALCULATIONS_READ)
    return connection_catalogue(runtime, calculation_id=calculation_id)


@mcp.tool()
def describe_calculation(calculation_id: str) -> dict[str, Any]:
    """Return schema, standard references, version and plugin provenance."""

    _require_scope(CALCULATIONS_READ)
    return _descriptor(calculation_id)


@mcp.tool()
def run_calculation(
    calculation_id: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Execute one registered calculation by its stable EngCalcs identifier."""

    _require_scope(CALCULATIONS_RUN)
    definition = _descriptor(calculation_id)
    result = runtime.run(calculation_id, inputs)
    return {
        "calculation": definition,
        "inputs": inputs,
        "result": result,
        "provenance": result.get("_provenance"),
    }


@mcp.tool()
async def run_wind_site_assessment(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run the full OpenWind site workflow through the EngCalcs orchestration layer."""

    _require_scope(CALCULATIONS_RUN)
    return await run_openwind_site_workflow(inputs)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the EngCalcs MCP server over stdio or Streamable HTTP."""

    parser = argparse.ArgumentParser(
        prog="engcalcs-mcp",
        description="Run the EngCalcs MCP calculation registry.",
    )
    parser.add_argument(
        "--transport",
        choices=MCP_TRANSPORTS,
        default=_setting("ENGCALCS_MCP_TRANSPORT", "OPENCALCS_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument(
        "--host",
        default=_setting("ENGCALCS_MCP_HOST", "OPENCALCS_MCP_HOST", "127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(_setting("ENGCALCS_MCP_PORT", "OPENCALCS_MCP_PORT", "8001")),
    )
    args = parser.parse_args(argv)

    mcp.settings.host = args.host
    mcp.settings.port = args.port

    if args.transport == "streamable-http":
        allowed_hosts = [
            item.strip()
            for item in _setting(
                "ENGCALCS_MCP_ALLOWED_HOSTS", "OPENCALCS_MCP_ALLOWED_HOSTS", ""
            ).split(",")
            if item.strip()
        ]
        allowed_origins = [
            item.strip()
            for item in _setting(
                "ENGCALCS_MCP_ALLOWED_ORIGINS", "OPENCALCS_MCP_ALLOWED_ORIGINS", ""
            ).split(",")
            if item.strip()
        ]
        if args.host in {"0.0.0.0", "::"} and not allowed_hosts:
            parser.error(
                "ENGCALCS_MCP_ALLOWED_HOSTS (or legacy OPENCALCS_MCP_ALLOWED_HOSTS) is "
                "required for wildcard HTTP binds."
            )
        if args.host not in {"0.0.0.0", "::"} and args.host not in allowed_hosts:
            allowed_hosts.append(args.host)
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )

    mcp.run(transport=args.transport)
    return 0


OpenCalcsTokenVerifier = EngCalcsTokenVerifier


if __name__ == "__main__":
    raise SystemExit(main())
