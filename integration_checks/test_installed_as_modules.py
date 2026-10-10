"""Installation-level regression for all modules in requirements-render.txt.

Run ONLY in the integration CI job after requirements-render is installed.
This is deliberately not part of the host-only test matrix.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from engcalcs.api import create_app
from engcalcs.auth import AllowAllAuthenticator
from engcalcs.connections import connection_catalogue, module_catalogue
from engcalcs.registry import CalculationRegistry


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PLUGINS = {
    "au.openwind",
    "structural.as1170",
    "structural.pynite",
    "structural.as3600",
    "structural.as4100",
    "structural.as1720",
    "stormwater.as3500",
}


def test_all_standard_plugins_are_discoverable_via_shared_runtime() -> None:
    registry = CalculationRegistry()
    assert {plugin.id for plugin in registry.plugins} == EXPECTED_PLUGINS
    modules = module_catalogue(registry)
    assert len(modules) == len(EXPECTED_PLUGINS)
    assert all(module["installed"] for module in modules)
    assert all(module["version"] and module["calculation_ids"] for module in modules)
    assert len(registry.list_calculations()) >= 40


def test_as1170_timber_and_stormwater_execute_with_versioned_results() -> None:
    registry = CalculationRegistry()
    weight = registry.run(
        "structural.as1170.part1.self_weight",
        {"unit_weight_kn_m3": 25, "thickness_m": 0.12, "area_m2": 10},
    )
    assert weight["permanent_action_kpa"] == pytest.approx(3)
    assert weight["permanent_action_kn"] == pytest.approx(30)
    assert weight["_provenance"]["engine"]["id"] == "structural.as1170"

    example = json.loads((ROOT / "tests/fixtures/as1720_f17_beam.json").read_text())
    timber = registry.run("structural.as1720.beam_design", example)
    assert timber["full_standard_compliance"] is False
    assert all(check["satisfied"] for check in timber["checks"])
    assert timber["_provenance"]["engine"]["id"] == "structural.as1720"

    roof = registry.run(
        "stormwater.as3500.roof_catchment",
        {"plan_area_m2": 100, "roof_slope_degrees": 0,
         "wind_exposure": "freely_exposed"},
    )
    assert roof["results"]["catchment_area_m2"] == pytest.approx(100)
    assert roof["_provenance"]["engine"]["id"] == "stormwater.as3500"
    flow = registry.run(
        "stormwater.as3500.roof_flow",
        {"catchment_area_m2": roof["results"]["catchment_area_m2"],
         "design_rainfall_intensity_mm_per_hour": 100},
    )
    assert flow["results"]["design_flow_lps"] == pytest.approx(100 / 36)


def test_only_direct_stormwater_and_housing_links_are_eligible() -> None:
    registry = CalculationRegistry()
    contracts = {item["id"]: item for item in connection_catalogue(registry)}
    assert contracts["as3500-roof-area-to-roof-flow"]["direct_link_ready"] is True
    assert contracts["as4055-classification-to-surface-loads"]["direct_link_ready"] is True
    assert contracts["wind-loads-to-frame"]["direct_link_ready"] is False
    assert contracts["frame-to-steel-section"]["requires_adapter"] is True
    assert contracts["frame-to-concrete-section"]["requires_adapter"] is True
    assert all(contract["requires_engineer_review"] for contract in contracts.values())


def test_rest_and_mcp_use_same_module_connection_registry(monkeypatch) -> None:
    import engcalcs.mcp_server as mcp_server

    registry = CalculationRegistry()
    client = TestClient(create_app(registry, authenticator=AllowAllAuthenticator()))
    rest_modules = client.get("/api/v1/modules")
    rest_links = client.get("/api/v1/connections")
    assert rest_modules.status_code == rest_links.status_code == 200
    monkeypatch.setattr(mcp_server, "runtime", registry)
    assert rest_modules.json() == mcp_server.list_engineering_modules()
    assert rest_links.json() == mcp_server.list_calculation_connections()
    assert client.get("/api/v1/connections", params={
        "calculation_id": "stormwater.as3500.roof_catchment",
    }).json() == mcp_server.list_calculation_connections(
        "stormwater.as3500.roof_catchment"
    )
