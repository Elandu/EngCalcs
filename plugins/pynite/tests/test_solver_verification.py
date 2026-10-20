"""Independent analytical checks for PyNite's 3D frame result mapping."""

from __future__ import annotations

import math

import pytest

from engcalcs_pynite.plugin import get_plugin

E = 200_000_000.0  # kPa = kN/m2
A = 0.01
IY = 2.0e-4
IZ = 1.0e-4
J = 3.0e-4
L = 5.0


def cantilever_inputs(
    *, nodes: list[dict] | None = None, members: list[dict] | None = None
) -> dict:
    node_rows = nodes or [
        {"id": "N1", "x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
        {"id": "N2", "x_m": L, "y_m": 0.0, "z_m": 0.0},
    ]
    member_rows = members or [
        {"id": "M1", "start_node": "N1", "end_node": "N2", "material": "Steel", "section": "S"}
    ]
    return {
        "analysis_type": "linear",
        "model": {
            "nodes": node_rows,
            "materials": [
                {
                    "id": "Steel",
                    "elastic_modulus_kpa": E,
                    "poisson_ratio": 0.3,
                    "density_tonnes_m3": 7.85,
                }
            ],
            "sections": [{"id": "S", "area_m2": A, "iy_m4": IY, "iz_m4": IZ, "j_m4": J}],
            "members": member_rows,
            "supports": [
                {
                    "node_id": "N1",
                    "dx": True,
                    "dy": True,
                    "dz": True,
                    "rx": True,
                    "ry": True,
                    "rz": True,
                }
            ],
            "load_cases": [{"id": "D", "name": "Dead"}],
            "node_loads": [],
            "member_distributed_loads": [],
            "load_combinations": [{"id": "Service", "factors": {"D": 1.0}}],
        },
    }


def results(inputs: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    output = get_plugin().calculations[0].run(inputs)
    nodes = {r["node_id"]: r for r in output["node_results"]}
    members = {r["member_id"]: r for r in output["member_results"]}
    return nodes, members


def test_3d_oriented_member_axial_response_matches_bar_solution() -> None:
    # The member lies along global +Y; the axial response must still use its true length.
    inputs = cantilever_inputs(
        nodes=[
            {"id": "N1", "x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
            {"id": "N2", "x_m": 0.0, "y_m": L, "z_m": 0.0},
        ]
    )
    inputs["model"]["supports"][0].update({"dx": True, "dy": True, "dz": True})
    inputs["model"]["supports"].append(
        {"node_id": "N2", "dx": True, "dy": False, "dz": True, "rx": True, "ry": True, "rz": True}
    )
    inputs["model"]["node_loads"] = [
        {"node_id": "N2", "load_case": "D", "direction": "FY", "value": 10.0}
    ]

    node, _ = results(inputs)

    assert node["N2"]["dy_m"] == pytest.approx(10.0 * L / (E * A), rel=1e-8)
    assert node["N1"]["reaction_fy_kn"] == pytest.approx(-10.0, abs=1e-8)


def test_member_roll_rotates_the_principal_bending_axis() -> None:
    inputs = cantilever_inputs()
    inputs["model"]["members"][0]["rotation_degrees"] = 90.0
    inputs["model"]["node_loads"] = [
        {"node_id": "N2", "load_case": "D", "direction": "FY", "value": -10.0}
    ]

    node, _ = results(inputs)

    # A 90-degree member roll puts this global-y load onto the Iy bending axis.
    assert node["N2"]["dy_m"] == pytest.approx(-10.0 * L**3 / (3.0 * E * IY), rel=1e-8)


def test_load_combination_superposes_case_results() -> None:
    inputs = cantilever_inputs()
    inputs["model"]["load_cases"] = [{"id": "D", "name": "Dead"}, {"id": "L", "name": "Live"}]
    inputs["model"]["node_loads"] = [
        {"node_id": "N2", "load_case": "D", "direction": "FY", "value": -2.0},
        {"node_id": "N2", "load_case": "L", "direction": "FY", "value": -3.0},
    ]
    inputs["model"]["load_combinations"] = [
        {"id": "DeadOnly", "factors": {"D": 1.0}},
        {"id": "Service", "factors": {"D": 1.0, "L": 2.0}},
    ]

    output = get_plugin().calculations[0].run(inputs)
    combo_node = next(
        r
        for r in output["node_results"]
        if r["node_id"] == "N2" and r["load_combination"] == "Service"
    )
    combo_member = next(r for r in output["member_results"] if r["load_combination"] == "Service")

    assert combo_node["dy_m"] == pytest.approx(-8.0 * L**3 / (3.0 * E * IZ), rel=1e-7)
    assert next(
        r
        for r in output["node_results"]
        if r["node_id"] == "N1" and r["load_combination"] == "Service"
    )["reaction_fy_kn"] == pytest.approx(8.0)
    assert combo_member["stations"][0]["moment_z_knm"] == pytest.approx(8.0 * L, abs=1e-7)


def test_partial_trapezoidal_distributed_load_has_correct_resultant_and_moment() -> None:
    inputs = cantilever_inputs()
    inputs["model"]["member_distributed_loads"] = [
        {
            "member_id": "M1",
            "load_case": "D",
            "direction": "Fy",
            "start_kn_m": -1.0,
            "end_kn_m": -3.0,
            "start_m": 1.0,
            "end_m": 3.0,
        }
    ]

    node, _ = results(inputs)

    assert node["N1"]["reaction_fy_kn"] == pytest.approx(4.0, abs=1e-7)
    # Integral x*q(x) from 1 m to 3 m is -26/3 kN m.
    assert node["N1"]["reaction_mz_knm"] == pytest.approx(26.0 / 3.0, abs=1e-7)


def test_compression_sensitive_p_delta_matches_beam_column_and_equilibrium() -> None:
    n = 8
    nodes = [{"id": f"N{i}", "x_m": i * L / n, "y_m": 0.0, "z_m": 0.0} for i in range(n + 1)]
    members = [
        {
            "id": f"M{i}",
            "start_node": f"N{i - 1}",
            "end_node": f"N{i}",
            "material": "Steel",
            "section": "S",
        }
        for i in range(1, n + 1)
    ]
    inputs = cantilever_inputs(nodes=nodes, members=members)
    inputs["model"]["supports"][0]["node_id"] = "N0"
    inputs["analysis_type"] = "p_delta"
    inputs["model"]["node_loads"] = [
        {"node_id": f"N{n}", "load_case": "D", "direction": "FY", "value": -1.0},
        {"node_id": f"N{n}", "load_case": "D", "direction": "FX", "value": -150.0},
    ]
    k = math.sqrt(150.0 / (E * IZ))
    expected_delta = -(math.tan(k * L) / k - L) / 150.0

    node, _ = results(inputs)

    assert node[f"N{n}"]["dy_m"] == pytest.approx(expected_delta, rel=1e-4)
    assert node["N0"]["reaction_fy_kn"] == pytest.approx(1.0, rel=1e-3)
    assert node["N0"]["reaction_fx_kn"] == pytest.approx(150.0, rel=1e-6)
