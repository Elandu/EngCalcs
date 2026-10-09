from __future__ import annotations

import pytest
from engcalcs.api import create_app
from engcalcs.auth import AllowAllAuthenticator
from engcalcs.registry import CalculationRegistry
from fastapi.testclient import TestClient

from engcalcs_pynite.plugin import CALCULATION_ID, get_plugin


@pytest.fixture
def simple_beam_inputs() -> dict:
    return {
        "analysis_type": "linear",
        "model": {
            "nodes": [
                {"id": "N1", "x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
                {"id": "N2", "x_m": 6.0, "y_m": 0.0, "z_m": 0.0},
            ],
            "materials": [
                {
                    "id": "Steel",
                    "elastic_modulus_kpa": 200_000_000.0,
                    "poisson_ratio": 0.3,
                    "density_tonnes_m3": 7.85,
                }
            ],
            "sections": [
                {
                    "id": "DemoSection",
                    "area_m2": 0.0023,
                    "iy_m4": 0.0000067,
                    "iz_m4": 0.000084,
                    "j_m4": 0.00000026,
                }
            ],
            "members": [
                {
                    "id": "M1",
                    "start_node": "N1",
                    "end_node": "N2",
                    "material": "Steel",
                    "section": "DemoSection",
                }
            ],
            "supports": [
                {
                    "node_id": "N1",
                    "dx": True,
                    "dy": True,
                    "dz": True,
                    "rx": True,
                    "ry": True,
                    "rz": False,
                },
                {
                    "node_id": "N2",
                    "dx": False,
                    "dy": True,
                    "dz": True,
                    "rx": True,
                    "ry": True,
                    "rz": False,
                },
            ],
            "load_cases": [{"id": "D", "name": "Dead"}],
            "node_loads": [],
            "member_distributed_loads": [
                {
                    "member_id": "M1",
                    "load_case": "D",
                    "direction": "FY",
                    "start_kn_m": -2.0,
                    "end_kn_m": -2.0,
                }
            ],
            "load_combinations": [{"id": "Service", "factors": {"D": 1.0}}],
        },
    }


def test_plugin_is_discoverable_and_describes_the_frame_calculation() -> None:
    plugin = get_plugin()

    assert plugin.id == "structural.pynite"
    assert plugin.calculations[0].id == CALCULATION_ID
    descriptor = plugin.calculations[0].descriptor()
    assert descriptor["category"] == "structural-analysis"
    assert descriptor["input_schema"]["required"] == ["model"]


def test_linear_analysis_returns_expected_simply_supported_beam_results(
    simple_beam_inputs: dict,
) -> None:
    result = get_plugin().calculations[0].run(simple_beam_inputs)

    reactions = {row["node_id"]: row for row in result["node_results"]}
    assert reactions["N1"]["reaction_fy_kn"] == pytest.approx(6.0, abs=1e-5)
    assert reactions["N2"]["reaction_fy_kn"] == pytest.approx(6.0, abs=1e-5)

    member = result["member_results"][0]
    midspan = member["stations"][len(member["stations"]) // 2]
    assert abs(midspan["moment_z_knm"]) == pytest.approx(9.0, rel=1e-4)
    assert len(member["stations"]) == 9
    assert "capacity checks" in result["limitations"][0]


def test_p_delta_analysis_returns_frame_results(simple_beam_inputs: dict) -> None:
    simple_beam_inputs["analysis_type"] = "p_delta"

    result = get_plugin().calculations[0].run(simple_beam_inputs)

    assert result["analysis_type"] == "p_delta"
    assert result["member_results"]


def test_invalid_member_reference_is_rejected_before_solver_execution(
    simple_beam_inputs: dict,
) -> None:
    simple_beam_inputs["model"]["members"][0]["start_node"] = "missing"

    with pytest.raises(ValueError, match="unknown end node"):
        get_plugin().calculations[0].run(simple_beam_inputs)


def test_non_finite_input_is_rejected(simple_beam_inputs: dict) -> None:
    simple_beam_inputs["model"]["nodes"][0]["x_m"] = float("nan")

    with pytest.raises(ValueError, match="finite numbers"):
        get_plugin().calculations[0].run(simple_beam_inputs)


def test_unrepresentably_large_number_is_rejected(simple_beam_inputs: dict) -> None:
    simple_beam_inputs["model"]["nodes"][0]["x_m"] = 10**400

    with pytest.raises(ValueError, match="finite numbers"):
        get_plugin().calculations[0].run(simple_beam_inputs)


def test_unrestrained_frame_does_not_return_apparent_success(simple_beam_inputs: dict) -> None:
    simple_beam_inputs["model"]["supports"] = []

    with pytest.raises(ValueError):
        get_plugin().calculations[0].run(simple_beam_inputs)


def test_engcalcs_registry_discovers_and_runs_pynite(simple_beam_inputs: dict) -> None:
    registry = CalculationRegistry()

    assert "structural.pynite" in {plugin.id for plugin in registry.plugins}
    assert CALCULATION_ID in {item["id"] for item in registry.list_calculations()}

    result = registry.run(CALCULATION_ID, simple_beam_inputs)

    assert result["solver"]["name"] == "PyNiteFEA"
    assert result["member_results"]
    assert result["_provenance"]["engine"]["id"] == "structural.pynite"


def test_engcalcs_api_exposes_and_runs_pynite(simple_beam_inputs: dict) -> None:
    client = TestClient(create_app(authenticator=AllowAllAuthenticator()))

    definition = client.get(f"/api/v1/calculations/{CALCULATION_ID}")
    assert definition.status_code == 200
    assert definition.json()["plugin"]["id"] == "structural.pynite"

    response = client.post(
        f"/api/v1/calculations/{CALCULATION_ID}/run",
        json={"inputs": simple_beam_inputs},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["solver"]["name"] == "PyNiteFEA"
    assert result["_provenance"]["engine"]["id"] == "structural.pynite"
