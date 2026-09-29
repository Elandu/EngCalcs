"""Compare the OpenCalcs PyNite path and Stabileo against beam theory.

Usage:
  python benchmarks/compare_frame_solvers.py [--stabileo-wasm PATH] [--json PATH]

The Stabileo WASM adapter is built from benchmarks/stabileo_adapter.rs against a
specified Stabileo engine revision. No production solver selection is changed.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "pynite" / "src"))
from opencalcs_pynite.plugin import get_plugin  # noqa: E402

E_KPA = 200_000_000.0
E_MPA = E_KPA / 1000.0
A_M2 = 0.01
IY_M4 = 2.0e-4
IZ_M4 = 1.0e-4
J_M4 = 3.0e-4
NU = 0.3
L_M = 5.0


def make_case(name: str) -> tuple[dict, dict, dict]:
    """Return PyNite input, Stabileo input, and analytical target metrics."""
    n = 2 if name == "simply_supported_udl_y" else 8 if name == "p_delta_cantilever" else 1
    nodes = [(i + 1, i * L_M / n) for i in range(n + 1)]
    simple = name == "simply_supported_udl_y"
    pdelta = name == "p_delta_cantilever"
    pynite_nodes = [{"id": f"N{i}", "x_m": x, "y_m": 0.0, "z_m": 0.0} for i, x in nodes]
    pynite_members = [
        {
            "id": f"M{i}",
            "start_node": f"N{i}",
            "end_node": f"N{i + 1}",
            "material": "steel",
            "section": "section",
        }
        for i in range(1, n + 1)
    ]
    fixed = {"dx": True, "dy": True, "dz": True, "rx": True, "ry": True, "rz": True}
    pinned = {**fixed, "rz": False}
    roller = {**pinned, "dx": False}
    support1 = pinned if simple else fixed
    pynite_supports = [{"node_id": "N1", **support1}]
    if simple:
        pynite_supports.append({"node_id": f"N{n + 1}", **roller})

    p_loads = []
    s_loads = []

    def tip(direction: str, force: float) -> None:
        p_loads.append(
            {"node_id": f"N{n + 1}", "load_case": "L", "direction": direction, "value": force}
        )
        s_loads.append(
            {
                "type": "nodal",
                "data": {
                    "nodeId": n + 1,
                    "fx": force if direction == "FX" else 0.0,
                    "fy": force if direction == "FY" else 0.0,
                    "fz": force if direction == "FZ" else 0.0,
                    "mx": 0.0,
                    "my": 0.0,
                    "mz": 0.0,
                },
            }
        )

    targets: dict[str, float]
    if name == "cantilever_tip_y":
        tip("FY", -10.0)
        targets = {
            "tip_uy_m": -10 * L_M**3 / (3 * E_KPA * IZ_M4),
            "root_reaction_y_kn": 10.0,
            "root_moment_z_knm": 10 * L_M,
        }
    elif name == "cantilever_tip_z":
        tip("FZ", -10.0)
        targets = {
            "tip_uz_m": -10 * L_M**3 / (3 * E_KPA * IY_M4),
            "root_reaction_z_kn": 10.0,
            "root_moment_y_knm": -10 * L_M,
        }
    elif name == "axial_tip_x":
        tip("FX", 10.0)
        targets = {"tip_ux_m": 10 * L_M / (E_KPA * A_M2), "root_reaction_x_kn": -10.0}
    elif simple:
        p_dist = [
            {
                "member_id": f"M{i}",
                "load_case": "L",
                "direction": "Fy",
                "start_kn_m": -2.0,
                "end_kn_m": -2.0,
            }
            for i in range(1, n + 1)
        ]
        s_loads.extend(
            {
                "type": "distributed",
                "data": {
                    "elementId": i,
                    "qYI": -2.0,
                    "qYJ": -2.0,
                    "qZI": 0.0,
                    "qZJ": 0.0,
                },
            }
            for i in range(1, n + 1)
        )
        targets = {
            "mid_uy_m": -5 * 2 * L_M**4 / (384 * E_KPA * IZ_M4),
            "root_reaction_y_kn": 2 * L_M / 2,
            "end_reaction_y_kn": 2 * L_M / 2,
            "mid_moment_z_knm": 2 * L_M**2 / 8,
        }
    elif pdelta:
        tip("FY", -1.0)
        tip("FX", -150.0)
        k = math.sqrt(150.0 / (E_KPA * IZ_M4))
        beam_column_delta = (math.tan(k * L_M) / k - L_M) / 150.0
        targets = {
            "tip_uy_m": -beam_column_delta,
            "root_reaction_y_kn": 1.0,
            "root_reaction_x_kn": 150.0,
        }
        p_dist = []
    else:
        raise ValueError(name)
    if not simple and not pdelta:
        p_dist = []

    pynite = {
        "analysis_type": "p_delta" if pdelta else "linear",
        "model": {
            "nodes": pynite_nodes,
            "materials": [
                {
                    "id": "steel",
                    "elastic_modulus_kpa": E_KPA,
                    "poisson_ratio": NU,
                    "density_tonnes_m3": 7.85,
                }
            ],
            "sections": [
                {"id": "section", "area_m2": A_M2, "iy_m4": IY_M4, "iz_m4": IZ_M4, "j_m4": J_M4}
            ],
            "members": pynite_members,
            "supports": pynite_supports,
            "load_cases": [{"id": "L", "name": "Benchmark"}],
            "node_loads": p_loads,
            "member_distributed_loads": p_dist,
            "load_combinations": [{"id": "Bench", "factors": {"L": 1.0}}],
        },
    }
    stabileo = {
        "solver": "pdelta_3d" if pdelta else "linear_3d",
        "input": {
            "nodes": {str(i): {"id": i, "x": x, "y": 0.0, "z": 0.0} for i, x in nodes},
            "materials": {"1": {"id": 1, "e": E_MPA, "nu": NU}},
            "sections": {"1": {"id": 1, "a": A_M2, "iy": IY_M4, "iz": IZ_M4, "j": J_M4}},
            "elements": {
                str(i): {
                    "id": i,
                    "type": "frame",
                    "nodeI": i,
                    "nodeJ": i + 1,
                    "materialId": 1,
                    "sectionId": 1,
                    "localYx": 0.0,
                    "localYy": 1.0,
                    "localYz": 0.0,
                }
                for i in range(1, n + 1)
            },
            "supports": {
                "1": {
                    "nodeId": 1,
                    "rx": support1["dx"],
                    "ry": support1["dy"],
                    "rz": support1["dz"],
                    "rrx": support1["rx"],
                    "rry": support1["ry"],
                    "rrz": support1["rz"],
                }
            },
            "loads": s_loads,
        },
    }
    if simple:
        stabileo["input"]["supports"]["2"] = {
            "nodeId": n + 1,
            "rx": roller["dx"],
            "ry": roller["dy"],
            "rz": roller["dz"],
            "rrx": roller["rx"],
            "rry": roller["ry"],
            "rrz": roller["rz"],
        }
    return pynite, stabileo, targets


def extract_pynite(result: dict, name: str) -> dict[str, float]:
    rows = {x["node_id"]: x for x in result["node_results"]}
    root, end = rows["N1"], rows[f"N{len(rows)}"]
    values = {
        "tip_ux_m": end["dx_m"],
        "tip_uy_m": end["dy_m"],
        "tip_uz_m": end["dz_m"],
        "root_reaction_x_kn": root["reaction_fx_kn"],
        "root_reaction_y_kn": root["reaction_fy_kn"],
        "root_reaction_z_kn": root["reaction_fz_kn"],
        "root_moment_y_knm": root["reaction_my_knm"],
        "root_moment_z_knm": root["reaction_mz_knm"],
        "end_reaction_y_kn": end["reaction_fy_kn"],
    }
    if name == "simply_supported_udl_y":
        values["mid_uy_m"] = rows["N2"]["dy_m"]
        # PyNite reports the left-element end action with the opposite sign
        # from the sagging BMD ordinate used by the analytical formula.
        values["mid_moment_z_knm"] = abs(
            result["member_results"][0]["stations"][-1]["moment_z_knm"]
        )
    return values


def extract_stabileo(result: dict, name: str) -> dict[str, float]:
    if name == "p_delta_cantilever":
        if not result.get("converged") or not result.get("isStable"):
            raise ValueError("Stabileo P-Delta result is unconverged or unstable")
        result = result["results"]
    rows = {x["nodeId"]: x for x in result["displacements"]}
    reactions = {x["nodeId"]: x for x in result["reactions"]}
    root, end = reactions[1], rows[max(rows)]
    values = {
        "tip_ux_m": end["ux"],
        "tip_uy_m": end["uy"],
        "tip_uz_m": end["uz"],
        "root_reaction_x_kn": root["fx"],
        "root_reaction_y_kn": root["fy"],
        "root_reaction_z_kn": root["fz"],
        "root_moment_y_knm": root["my"],
        "root_moment_z_knm": root["mz"],
        "end_reaction_y_kn": reactions.get(max(rows), {}).get("fy", 0.0),
    }
    if name == "simply_supported_udl_y":
        values["mid_uy_m"] = rows[2]["uy"]
        element = next(x for x in result["elementForces"] if x["elementId"] == 1)
        values["mid_moment_z_knm"] = abs(element["mzEnd"])
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stabileo-wasm", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    cases = [
        "cantilever_tip_y",
        "cantilever_tip_z",
        "axial_tip_x",
        "simply_supported_udl_y",
        "p_delta_cantilever",
    ]
    report = {
        "units": "kN, m, kPa, kN/m, kN m",
        "stabileo_revision": "7d87e551b765c88956df95b375e0ef0befda53f7",
        "relative_tolerances": {"linear": 1e-6, "p_delta": 1e-3},
        "cases": [],
    }
    failed = False
    for name in cases:
        p_input, s_input, targets = make_case(name)
        item: dict = {"case": name, "targets": targets, "solvers": {}}
        for solver in ("pynite", "stabileo"):
            if solver == "stabileo" and not args.stabileo_wasm:
                continue
            try:
                if solver == "pynite":
                    raw = get_plugin().calculations[0].run(p_input)
                    values = extract_pynite(raw, name)
                    version = raw["solver"]["version"]
                else:
                    bridge = Path(__file__).with_name("stabileo_wasm_runner.mjs")
                    proc = subprocess.run(
                        ["node", str(bridge), str(args.stabileo_wasm)],
                        input=json.dumps(s_input),
                        text=True,
                        capture_output=True,
                        check=True,
                        timeout=60,
                    )
                    raw = json.loads(proc.stdout)
                    if "error" in raw:
                        raise RuntimeError(raw["error"])
                    values = extract_stabileo(raw, name)
                    version = "local WASM build"
                tolerance = 1e-3 if name == "p_delta_cantilever" else 1e-6
                metrics = {
                    key: {
                        "actual": values[key],
                        "expected": expected,
                        "relative_error": abs(values[key] - expected) / abs(expected),
                        "pass": abs(values[key] - expected) <= tolerance * abs(expected),
                    }
                    for key, expected in targets.items()
                }
                item["solvers"][solver] = {
                    "version": version,
                    "metrics": metrics,
                    "pass": all(x["pass"] for x in metrics.values()),
                }
                failed |= not item["solvers"][solver]["pass"]
            except Exception as exc:  # Surface every solver failure in the report.
                detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
                item["solvers"][solver] = {
                    "error": f"{type(exc).__name__}: {detail}",
                    "pass": False,
                }
                failed = True
        report["cases"].append(item)
    output = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
