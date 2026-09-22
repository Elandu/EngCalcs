# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Elandu and contributors

"""OpenCalcs host API."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict

from opencalcs import __version__
from opencalcs.auth import (
    CALCULATIONS_READ,
    CALCULATIONS_RUN,
    AuthContext,
    Authenticator,
    OpenCalcsAuthenticator,
)
from opencalcs.provenance import plugin_provenance, runtime_provenance
from opencalcs.registry import CalculationRegistry
from opencalcs.reports import build_wind_calculation_pack
from opencalcs.workflows import run_openwind_site_workflow


class CalculationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    inputs: dict[str, Any]


class WindCalculationPackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    payload: dict[str, Any]


def create_app(
    registry: CalculationRegistry | None = None,
    authenticator: Authenticator | None = None,
) -> FastAPI:
    """Create the OpenCalcs API with explicit shared authentication."""

    runtime = registry or CalculationRegistry()
    auth = authenticator or OpenCalcsAuthenticator()
    app = FastAPI(title="OpenCalcs", version=__version__)

    async def require_read(request: Request) -> AuthContext:
        return await auth.authenticate_request(request, (CALCULATIONS_READ,))

    async def require_run(request: Request) -> AuthContext:
        return await auth.authenticate_request(request, (CALCULATIONS_RUN,))

    def calculation_descriptor(calculation_id: str) -> dict[str, Any]:
        return runtime.describe(calculation_id)

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/about")
    def about() -> dict[str, Any]:
        return {
            "runtime": runtime_provenance(),
            "plugins": [plugin_provenance(plugin) for plugin in runtime.plugins],
        }

    @app.get("/api/v1/plugins")
    @app.get("/api/plugins")
    def plugins(_auth: AuthContext = Depends(require_read)) -> list[dict[str, Any]]:
        return [
            {
                **plugin.descriptor(),
                "provenance": plugin_provenance(plugin),
                "runtime": runtime_provenance(),
            }
            for plugin in runtime.plugins
        ]

    @app.get("/api/v1/calculations")
    @app.get("/api/calculations")
    def calculations(_auth: AuthContext = Depends(require_read)) -> list[dict[str, Any]]:
        return runtime.list_calculations()

    @app.get("/api/v1/calculations/{calculation_id}")
    @app.get("/api/calculations/{calculation_id}")
    def calculation(
        calculation_id: str,
        _auth: AuthContext = Depends(require_read),
    ) -> dict[str, Any]:
        try:
            return calculation_descriptor(calculation_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/v1/calculations/{calculation_id}/run")
    @app.post("/api/calculations/{calculation_id}/run")
    def run_calculation(
        calculation_id: str,
        request: CalculationRunRequest,
        _auth: AuthContext = Depends(require_run),
    ) -> dict[str, Any]:
        try:
            return runtime.run(calculation_id, request.inputs)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/reports/wind/calculation-pack")
    def wind_calculation_pack(
        request: WindCalculationPackRequest,
        _auth: AuthContext = Depends(require_run),
    ) -> Response:
        """Render an issued Wind calculation pack from reviewed immutable records."""

        pdf = build_wind_calculation_pack(request.payload)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="wind-calculation-pack.pdf"'},
        )

    @app.post("/api/v1/workflows/wind/site")
    async def wind_site_workflow(
        inputs: dict[str, Any],
        _auth: AuthContext = Depends(require_run),
    ) -> dict[str, Any]:
        """Run the full OpenWind site workflow through the installed module."""

        try:
            return await run_openwind_site_workflow(inputs)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    return app


app = create_app()
