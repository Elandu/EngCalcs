# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Elandu and contributors

"""Specialist engineering workflows hosted through OpenCalcs."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import httpx

from opencalcs.provenance import plugin_provenance, runtime_provenance


@lru_cache(maxsize=1)
def _openwind_app():
    try:
        from openwind_au.api import create_app
    except ImportError as exc:
        raise RuntimeError("OpenWind-AU is not installed in this OpenCalcs runtime.") from exc
    return create_app()


async def run_openwind_site_workflow(inputs: dict[str, Any]) -> dict[str, Any]:
    """Run the existing OpenWind streamed workflow once and aggregate its stages."""

    try:
        from openwind_au.plugin import get_plugin
    except ImportError as exc:
        raise RuntimeError("OpenWind-AU is not installed in this OpenCalcs runtime.") from exc

    openwind_plugin = get_plugin()

    transport = httpx.ASGITransport(app=_openwind_app())
    stages: dict[str, Any] = {}
    events: list[dict[str, Any]] = []

    async with (
        httpx.AsyncClient(
            transport=transport,
            # This is an in-process ASGI call. Use the host allowed by OpenWind's
            # default policy and the documented production allowlist.
            base_url="http://localhost",
            timeout=120.0,
        ) as client,
        client.stream(
            "POST",
            "/api/wind-workflow/stream",
            json=inputs,
        ) as response,
    ):
        if response.status_code >= 400:
            detail = await response.aread()
            raise ValueError(
                f"OpenWind workflow failed ({response.status_code}): "
                f"{detail.decode(errors='replace')[:500]}"
            )

        async for line in response.aiter_lines():
            if not line.strip():
                continue
            event = json.loads(line)
            events.append(event)
            stage = str(event.get("stage", "unknown"))
            data = event.get("data")
            if data is not None:
                stages[stage] = data
            if stage == "error":
                status_code = int((data or {}).get("status_code", 500))
                message = str(event.get("label", "OpenWind workflow failed."))
                if status_code in {400, 422}:
                    raise ValueError(message)
                raise RuntimeError(message)

    workflow_stage = stages.get("workflow", {})
    workflow = workflow_stage.get("workflow") if isinstance(workflow_stage, dict) else None
    if not isinstance(workflow, dict):
        raise RuntimeError("OpenWind workflow completed without a workflow result.")

    return {
        "workflow_id": "au.wind.site_assessment",
        "runtime": runtime_provenance(),
        "plugin": plugin_provenance(openwind_plugin),
        "standard": {
            "name": "AS/NZS 1170.2",
            "edition": "2021",
        },
        "inputs": inputs,
        "stages": stages,
        "events": [
            {
                "stage": event.get("stage"),
                "percent": event.get("percent"),
                "label": event.get("label"),
            }
            for event in events
        ],
        "result": workflow,
    }
