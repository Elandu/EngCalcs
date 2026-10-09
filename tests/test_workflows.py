from __future__ import annotations

import asyncio
import json

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import StreamingResponse
from starlette.routing import Route

from engcalcs import workflows


def test_embedded_wind_workflow_respects_openwind_host_policy(monkeypatch) -> None:
    # OpenWind is an optional host plugin; this integration runs when installed.
    security = pytest.importorskip("openwind_au.http_security")
    observed = {}

    async def stream(request):
        observed["host"] = request.headers["host"]
        observed["input"] = await request.json()
        event = {"stage": "workflow", "data": {"workflow": {"fixture": "aggregated"}}}
        return StreamingResponse(
            iter([json.dumps(event) + "\n"]),
            media_type="application/x-ndjson",
        )

    monkeypatch.delenv("OPENWIND_TRUSTED_HOSTS", raising=False)
    app = Starlette(
        routes=[Route("/api/wind-workflow/stream", stream, methods=["POST"])],
        middleware=[
            Middleware(
                TrustedHostMiddleware,
                allowed_hosts=security.configured_trusted_hosts(production=False),
            )
        ],
    )
    monkeypatch.setattr(workflows, "_openwind_app", lambda: app)
    inputs = {"latitude": -33.0, "longitude": 151.0}
    result = asyncio.run(workflows.run_openwind_site_workflow(inputs))
    assert observed == {"host": "localhost", "input": inputs}
    assert result["result"] == {"fixture": "aggregated"}
    assert result["workflow_id"] == "au.wind.site_assessment"
    assert result["plugin"]["id"] == "au.openwind"
