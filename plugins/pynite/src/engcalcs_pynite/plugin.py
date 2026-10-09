# SPDX-License-Identifier: AGPL-3.0-only

"""EngCalcs plugin wrapping PyNite's 3D elastic frame solver."""

from __future__ import annotations

import contextlib
import io
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from jsonschema import Draft202012Validator, ValidationError
from Pynite import FEModel3D

PLUGIN_VERSION = "0.1.0"
CALCULATION_ID = "structural.pynite.frame_analysis"
STATION_COUNT = 9
MAX_NODES = 150
MAX_MEMBERS = 200
MAX_LOADS = 500
MAX_COMBINATIONS = 20

ID_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "maxLength": 40,
    "pattern": r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,39}$",
}
NUMBER_SCHEMA = {"type": "number"}

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["model"],
    "properties": {
        "analysis_type": {
            "type": "string",
            "enum": ["linear", "p_delta"],
            "default": "linear",
        },
        "model": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "nodes",
                "materials",
                "sections",
                "members",
                "supports",
                "load_cases",
                "load_combinations",
            ],
            "properties": {
                "nodes": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": MAX_NODES,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "x_m", "y_m", "z_m"],
                        "properties": {
                            "id": ID_SCHEMA,
                            "x_m": NUMBER_SCHEMA,
                            "y_m": NUMBER_SCHEMA,
                            "z_m": NUMBER_SCHEMA,
                        },
                    },
                },
                "materials": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 50,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "id",
                            "elastic_modulus_kpa",
                            "poisson_ratio",
                            "density_tonnes_m3",
                        ],
                        "properties": {
                            "id": ID_SCHEMA,
                            "elastic_modulus_kpa": {
                                "type": "number",
                                "exclusiveMinimum": 0,
                            },
                            "poisson_ratio": {
                                "type": "number",
                                "minimum": -0.99,
                                "maximum": 0.49,
                            },
                            "density_tonnes_m3": {"type": "number", "minimum": 0},
                        },
                    },
                },
                "sections": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 100,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "area_m2", "iy_m4", "iz_m4", "j_m4"],
                        "properties": {
                            "id": ID_SCHEMA,
                            "area_m2": {"type": "number", "exclusiveMinimum": 0},
                            "iy_m4": {"type": "number", "exclusiveMinimum": 0},
                            "iz_m4": {"type": "number", "exclusiveMinimum": 0},
                            "j_m4": {"type": "number", "exclusiveMinimum": 0},
                        },
                    },
                },
                "members": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_MEMBERS,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "id",
                            "start_node",
                            "end_node",
                            "material",
                            "section",
                        ],
                        "properties": {
                            "id": ID_SCHEMA,
                            "start_node": ID_SCHEMA,
                            "end_node": ID_SCHEMA,
                            "material": ID_SCHEMA,
                            "section": ID_SCHEMA,
                            "rotation_degrees": {"type": "number"},
                        },
                    },
                },
                "supports": {
                    "type": "array",
                    "maxItems": MAX_NODES,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["node_id", "dx", "dy", "dz", "rx", "ry", "rz"],
                        "properties": {
                            "node_id": ID_SCHEMA,
                            **{
                                dof: {"type": "boolean"}
                                for dof in ("dx", "dy", "dz", "rx", "ry", "rz")
                            },
                        },
                    },
                },
                "load_cases": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 20,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "name"],
                        "properties": {
                            "id": ID_SCHEMA,
                            "name": {"type": "string", "maxLength": 80},
                        },
                    },
                },
                "node_loads": {
                    "type": "array",
                    "maxItems": MAX_LOADS,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["node_id", "load_case", "direction", "value"],
                        "properties": {
                            "node_id": ID_SCHEMA,
                            "load_case": ID_SCHEMA,
                            "direction": {"enum": ["FX", "FY", "FZ", "MX", "MY", "MZ"]},
                            "value": NUMBER_SCHEMA,
                        },
                    },
                },
                "member_distributed_loads": {
                    "type": "array",
                    "maxItems": MAX_LOADS,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "member_id",
                            "load_case",
                            "direction",
                            "start_kn_m",
                            "end_kn_m",
                        ],
                        "properties": {
                            "member_id": ID_SCHEMA,
                            "load_case": ID_SCHEMA,
                            "direction": {"enum": ["Fx", "Fy", "Fz", "FX", "FY", "FZ"]},
                            "start_kn_m": NUMBER_SCHEMA,
                            "end_kn_m": NUMBER_SCHEMA,
                            "start_m": {"type": "number", "minimum": 0},
                            "end_m": {"type": "number", "exclusiveMinimum": 0},
                        },
                    },
                },
                "load_combinations": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_COMBINATIONS,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "factors"],
                        "properties": {
                            "id": ID_SCHEMA,
                            "factors": {
                                "type": "object",
                                "minProperties": 1,
                                "additionalProperties": NUMBER_SCHEMA,
                            },
                        },
                    },
                },
            },
        },
    },
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "solver",
        "analysis_type",
        "load_combinations",
        "node_results",
        "member_results",
        "warnings",
        "limitations",
    ],
    "properties": {
        "solver": {"type": "object"},
        "analysis_type": {"type": "string"},
        "load_combinations": {"type": "array", "items": {"type": "string"}},
        "node_results": {"type": "array", "items": {"type": "object"}},
        "member_results": {"type": "array", "items": {"type": "object"}},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}


def _is_finite_tree(value: Any, path: str = "inputs") -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"{path} must contain only finite numbers.")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _is_finite_tree(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _is_finite_tree(child, f"{path}[{index}]")


def _unique_by_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row["id"]
        if identifier in indexed:
            raise ValueError(f"{label} IDs must be unique; {identifier!r} appears more than once.")
        indexed[identifier] = row
    return indexed


def _validate_references(
    model: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    nodes = _unique_by_id(model["nodes"], "Node")
    materials = _unique_by_id(model["materials"], "Material")
    sections = _unique_by_id(model["sections"], "Section")
    members = _unique_by_id(model["members"], "Member")
    cases = _unique_by_id(model["load_cases"], "Load case")
    combinations = _unique_by_id(model["load_combinations"], "Load combination")
    support_nodes = [support["node_id"] for support in model["supports"]]
    if len(set(support_nodes)) != len(support_nodes):
        raise ValueError("Each node can have only one support definition.")
    for support in model["supports"]:
        if support["node_id"] not in nodes:
            raise ValueError(f"Support refers to unknown node {support['node_id']!r}.")

    for member in members.values():
        if member["start_node"] not in nodes or member["end_node"] not in nodes:
            raise ValueError(f"Member {member['id']!r} refers to an unknown end node.")
        if member["start_node"] == member["end_node"]:
            raise ValueError(f"Member {member['id']!r} must connect two different nodes.")
        if member["material"] not in materials or member["section"] not in sections:
            raise ValueError(f"Member {member['id']!r} refers to an unknown material or section.")
        start = nodes[member["start_node"]]
        end = nodes[member["end_node"]]
        length = math.dist(
            (start["x_m"], start["y_m"], start["z_m"]),
            (end["x_m"], end["y_m"], end["z_m"]),
        )
        if length <= 1e-9:
            raise ValueError(f"Member {member['id']!r} has zero length.")

    for load in model.get("node_loads", []):
        if load["node_id"] not in nodes:
            raise ValueError(f"Nodal load refers to unknown node {load['node_id']!r}.")
        if load["load_case"] not in cases:
            raise ValueError(f"Nodal load refers to unknown load case {load['load_case']!r}.")
    for load in model.get("member_distributed_loads", []):
        if load["member_id"] not in members:
            raise ValueError(f"Distributed load refers to unknown member {load['member_id']!r}.")
        if load["load_case"] not in cases:
            raise ValueError(f"Distributed load refers to unknown load case {load['load_case']!r}.")
        member = members[load["member_id"]]
        start = nodes[member["start_node"]]
        end = nodes[member["end_node"]]
        length = math.dist(
            (start["x_m"], start["y_m"], start["z_m"]),
            (end["x_m"], end["y_m"], end["z_m"]),
        )
        x1 = load.get("start_m", 0.0)
        x2 = load.get("end_m", length)
        if x1 >= x2 or x2 > length + 1e-9:
            raise ValueError(
                f"Distributed load on {load['member_id']!r} must lie within the member length."
            )

    for combo in combinations.values():
        for case_id, factor in combo["factors"].items():
            if case_id not in cases:
                raise ValueError(
                    f"Combination {combo['id']!r} refers to unknown load case {case_id!r}."
                )
            if not math.isfinite(float(factor)):
                raise ValueError(f"Combination {combo['id']!r} has a non-finite factor.")

    return members, nodes


def _number(values: Mapping[str, Any], key: str) -> float:
    value = values.get(key, 0.0)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PyNite returned an invalid result for {key}.") from exc
    if not math.isfinite(result):
        raise ValueError(f"PyNite returned a non-finite result for {key}.")
    return result


def _station_row(values: Any, result_name: str) -> Any:
    dimensions = getattr(values, "ndim", 1)
    if dimensions == 2 and values.shape[0] == 2:
        # PyNite returns a 2×N array: station coordinates, then the requested results.
        values = values[1]
    elif dimensions != 1:
        raise ValueError(f"PyNite returned an unexpected array shape for {result_name}.")
    if len(values) != STATION_COUNT:
        raise ValueError(f"PyNite returned an incomplete station array for {result_name}.")
    return values


def _run_analysis(inputs: Mapping[str, Any]) -> dict[str, Any]:
    _is_finite_tree(inputs)
    model_data = dict(inputs["model"])
    members_data, nodes_data = _validate_references(model_data)
    model = FEModel3D()

    for node in model_data["nodes"]:
        model.add_node(node["id"], node["x_m"], node["y_m"], node["z_m"])
    for material in model_data["materials"]:
        elastic_modulus = material["elastic_modulus_kpa"]
        poisson_ratio = material["poisson_ratio"]
        shear_modulus = elastic_modulus / (2.0 * (1.0 + poisson_ratio))
        model.add_material(
            material["id"],
            elastic_modulus,
            shear_modulus,
            poisson_ratio,
            material["density_tonnes_m3"],
        )
    for section in model_data["sections"]:
        model.add_section(
            section["id"],
            section["area_m2"],
            section["iy_m4"],
            section["iz_m4"],
            section["j_m4"],
        )
    for member in model_data["members"]:
        model.add_member(
            member["id"],
            member["start_node"],
            member["end_node"],
            member["material"],
            member["section"],
            rotation=member.get("rotation_degrees", 0.0),
        )
    for support in model_data["supports"]:
        model.def_support(
            support["node_id"],
            support_DX=support["dx"],
            support_DY=support["dy"],
            support_DZ=support["dz"],
            support_RX=support["rx"],
            support_RY=support["ry"],
            support_RZ=support["rz"],
        )
    for load in model_data.get("node_loads", []):
        model.add_node_load(load["node_id"], load["direction"], load["value"], load["load_case"])
    for load in model_data.get("member_distributed_loads", []):
        model.add_member_dist_load(
            load["member_id"],
            load["direction"],
            load["start_kn_m"],
            load["end_kn_m"],
            x1=load.get("start_m"),
            x2=load.get("end_m"),
            case=load["load_case"],
        )
    for combination in model_data["load_combinations"]:
        model.add_load_combo(combination["id"], combination["factors"])

    analysis_type = inputs.get("analysis_type", "linear")
    solver_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(solver_output), contextlib.redirect_stderr(solver_output):
            if analysis_type == "p_delta":
                model.analyze_PDelta(log=False, check_stability=True)
            else:
                model.analyze_linear(log=False, check_stability=True, check_statics=True)
    except Exception as exc:
        detail = str(exc).strip()
        if len(detail) > 500:
            detail = detail[:497] + "..."
        raise ValueError(
            f"PyNite {analysis_type} analysis failed: {type(exc).__name__}: {detail}"
        ) from exc

    captured = solver_output.getvalue().strip()
    if "unstable" in captured.lower() or "singular stiffness" in captured.lower():
        raise ValueError(
            "PyNite reported an unstable frame; check supports and member connectivity."
        )

    combo_ids = [combo["id"] for combo in model_data["load_combinations"]]
    node_results: list[dict[str, Any]] = []
    for combo_id in combo_ids:
        for node_id in nodes_data:
            node = model.nodes[node_id]
            if combo_id not in node.DX:
                raise ValueError(
                    f"PyNite returned no displacement results for {node_id!r} in {combo_id!r}; "
                    "the frame may be unstable."
                )
            node_results.append(
                {
                    "load_combination": combo_id,
                    "node_id": node_id,
                    "dx_m": _number(node.DX, combo_id),
                    "dy_m": _number(node.DY, combo_id),
                    "dz_m": _number(node.DZ, combo_id),
                    "rx_rad": _number(node.RX, combo_id),
                    "ry_rad": _number(node.RY, combo_id),
                    "rz_rad": _number(node.RZ, combo_id),
                    "reaction_fx_kn": _number(node.RxnFX, combo_id),
                    "reaction_fy_kn": _number(node.RxnFY, combo_id),
                    "reaction_fz_kn": _number(node.RxnFZ, combo_id),
                    "reaction_mx_knm": _number(node.RxnMX, combo_id),
                    "reaction_my_knm": _number(node.RxnMY, combo_id),
                    "reaction_mz_knm": _number(node.RxnMZ, combo_id),
                }
            )

    member_results: list[dict[str, Any]] = []
    for combo_id in combo_ids:
        for member_id, member_data in members_data.items():
            member = model.members[member_id]
            start = nodes_data[member_data["start_node"]]
            end = nodes_data[member_data["end_node"]]
            length = math.dist(
                (start["x_m"], start["y_m"], start["z_m"]),
                (end["x_m"], end["y_m"], end["z_m"]),
            )
            arrays = {
                "axial_kn": member.axial_array(STATION_COUNT, combo_name=combo_id),
                "shear_y_kn": member.shear_array("Fy", STATION_COUNT, combo_name=combo_id),
                "shear_z_kn": member.shear_array("Fz", STATION_COUNT, combo_name=combo_id),
                "moment_y_knm": member.moment_array("My", STATION_COUNT, combo_name=combo_id),
                "moment_z_knm": member.moment_array("Mz", STATION_COUNT, combo_name=combo_id),
                "deflection_x_m": member.deflection_array("dx", STATION_COUNT, combo_name=combo_id),
                "deflection_y_m": member.deflection_array("dy", STATION_COUNT, combo_name=combo_id),
                "deflection_z_m": member.deflection_array("dz", STATION_COUNT, combo_name=combo_id),
            }
            arrays = {
                result_name: _station_row(values, result_name)
                for result_name, values in arrays.items()
            }
            stations = []
            for index in range(STATION_COUNT):
                sample: dict[str, Any] = {"x_m": length * index / (STATION_COUNT - 1)}
                for result_name, values in arrays.items():
                    sample[result_name] = _number({"value": values[index]}, "value")
                stations.append(sample)
            member_results.append(
                {
                    "load_combination": combo_id,
                    "member_id": member_id,
                    "length_m": length,
                    "stations": stations,
                }
            )

    warnings = [line.strip() for line in captured.splitlines() if line.strip()][:20]
    return {
        "solver": {"name": "PyNiteFEA", "version": _pynite_version()},
        "analysis_type": analysis_type,
        "load_combinations": combo_ids,
        "node_results": node_results,
        "member_results": member_results,
        "warnings": warnings,
        "limitations": [
            (
                "Elastic frame-member analysis only; this calculation does not perform "
                "design-code capacity checks."
            ),
            (
                "Plate and shell elements, buckling, and connection design are not included "
                "in this model workflow."
            ),
            "Use consistent SI input units: kN, m, kPa, kN/m, and kN·m.",
            (
                "Review model stability, restraints, load directions, and results "
                "independently before engineering use."
            ),
        ],
    }


def _pynite_version() -> str:
    try:
        return version("PyniteFEA")
    except PackageNotFoundError:
        return "unknown"


@dataclass(frozen=True)
class PyniteFrameAnalysis:
    id: str = CALCULATION_ID
    name: str = "PyNite frame analysis"
    description: str = (
        "Analyse a three-dimensional elastic frame model with PyNite and return node, reaction, "
        "and member force results."
    )
    discipline: str = "structural"
    category: str = "structural-analysis"
    jurisdiction: str = "general"
    version: str = "1"
    input_schema: dict[str, Any] = field(default_factory=lambda: INPUT_SCHEMA)
    output_schema: dict[str, Any] = field(default_factory=lambda: OUTPUT_SCHEMA)
    standard: None = None

    def run(self, inputs: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(inputs, Mapping):
            raise ValueError("Calculation inputs must be an object.")
        try:
            Draft202012Validator(self.input_schema).validate(dict(inputs))
        except ValidationError as exc:
            path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
            raise ValueError(f"Invalid calculation input at {path}: {exc.message}") from exc
        try:
            return _run_analysis(inputs)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(
                f"PyNite could not assemble this model: {type(exc).__name__}: {exc}"
            ) from exc

    def descriptor(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "discipline": self.discipline,
            "category": self.category,
            "jurisdiction": self.jurisdiction,
            "version": self.version,
            "standard": None,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


@dataclass(frozen=True)
class PynitePlugin:
    id: str = "structural.pynite"
    name: str = "PyNite Structural Analysis"
    version: str = PLUGIN_VERSION
    revision: str | None = None
    license: str | None = "AGPL-3.0-only"
    source: str | None = "https://github.com/Elandu/OpenCalcs/tree/main/plugins/pynite"
    calculations: tuple[PyniteFrameAnalysis, ...] = (PyniteFrameAnalysis(),)

    def descriptor(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "revision": self.revision,
            "license": self.license,
            "source": self.source,
            "calculations": [calculation.descriptor() for calculation in self.calculations],
        }


def get_plugin() -> PynitePlugin:
    """Return the PyNite calculation plugin without starting a server."""

    return PynitePlugin()
