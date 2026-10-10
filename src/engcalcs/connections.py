# SPDX-License-Identifier: AGPL-3.0-only
"""Engineering module catalogue and explicitly reviewed cross-module contracts.

A connection is a *design workflow contract*, not a calculation and not a
permission to execute a solver. Only 'direct' contracts with verified schemas
are eligible for ordinary saved JSON-Pointer links. No design actions are
silently extracted from frame diagrams or re-factored between standards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODULES: tuple[dict[str, str], ...] = (
    {
        "id": "au.openwind",
        "name": "AS/NZS 1170.2 / AS 4055 wind",
        "scope": "Wind site and housing actions",
    },
    {
        "id": "structural.as1170",
        "name": "AS/NZS 1170.0 / 1170.1",
        "scope": "Structural actions and combinations",
    },
    {
        "id": "structural.pynite",
        "name": "3D frame analysis",
        "scope": "Elastic member and node results",
    },
    {
        "id": "structural.as3600",
        "name": "AS 3600 section mechanics",
        "scope": "Nominal concrete section mechanics only",
    },
    {
        "id": "structural.as4100",
        "name": "AS 4100 axial sections",
        "scope": "Steel axial section capacities only",
    },
    {
        "id": "structural.as1720",
        "name": "AS 1720.1 strength",
        "scope": "Selected F-grade timber checks",
    },
    {
        "id": "stormwater.as3500",
        "name": "AS/NZS 3500.3 stormwater",
        "scope": "Selected drainage calculations",
    },
)


@dataclass(frozen=True)
class ConnectionContract:
    id: str
    source: str
    target: str
    mode: str
    reason: str
    output_path: str | None = None
    input_path: str | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        if self.mode not in ("direct", "reviewed_import", "adapter_required"):
            raise ValueError(f"Invalid engineering link mode: {self.mode}")
        if self.mode == "direct" and (not self.output_path or not self.input_path):
            raise ValueError("Direct links require exact output and input paths")


CONNECTIONS: tuple[ConnectionContract, ...] = (
    ConnectionContract(
        "as4055-classification-to-surface-loads",
        "au.wind.as4055.classify_housing_site",
        "au.wind.as4055.housing_surface_loads",
        "direct",
        (
            "The complete classified-site record is consumed unchanged; eligibility "
            "and load inputs still require engineering review."
        ),
        "/classification",
        "/classification",
    ),
    ConnectionContract(
        "as3500-roof-area-to-roof-flow",
        "stormwater.as3500.roof_catchment",
        "stormwater.as3500.roof_flow",
        "direct",
        (
            "Transfers verified roof catchment area; the designer must supply design "
            "rainfall intensity separately."
        ),
        "/results/catchment_area_m2",
        "/catchment_area_m2",
        "m2",
    ),
    ConnectionContract(
        "as3500-pervious-coefficient-to-design-flow",
        "stormwater.as3500.pervious_runoff_coefficient",
        "stormwater.as3500.design_flow",
        "reviewed_import",
        (
            "Select the correct subcatchment, area and rainfall event; each "
            "coefficient belongs to a reviewed catchment row."
        ),
        "/results/runoff_coefficient",
        "/catchments/0/runoff_coefficient",
    ),
    ConnectionContract(
        "wind-loads-to-frame",
        "au.wind.frame_loads",
        "structural.pynite.frame_analysis",
        "reviewed_import",
        (
            "Requires frame member mapping, matching geometry, axes, load cases and "
            "pressure provenance; use the dedicated Wind-to-Frame import validation."
        ),
        "/member_distributed_loads",
        "/model/member_distributed_loads",
        "kN/m",
    ),
    ConnectionContract(
        "as1170-actions-to-frame",
        "structural.as1170.part1.floor_action",
        "structural.pynite.frame_analysis",
        "adapter_required",
        (
            "Imposed floor actions require tributary geometry, load orientation and "
            "case assignment before applying to structural members."
        ),
    ),
    ConnectionContract(
        "as1170-combination-review",
        "structural.as1170.part0.combinations",
        "structural.pynite.frame_analysis",
        "adapter_required",
        (
            "AS/NZS 1170.0 combines signed action effects, while frame solvers "
            "combine applied load cases; an engineer must resolve action-to-load-case "
            "mapping."
        ),
    ),
    ConnectionContract(
        "frame-actions-to-as1170-combinations",
        "structural.pynite.frame_analysis",
        "structural.as1170.part0.combinations",
        "adapter_required",
        (
            "Identify member, combination, action direction, sign and independent "
            "G/Q/W effects; do not map a force diagram automatically."
        ),
    ),
    ConnectionContract(
        "frame-to-concrete-section",
        "structural.pynite.frame_analysis",
        "structural.as3600.section_analysis",
        "adapter_required",
        (
            "Review governing axial force and bending orientation; the concrete "
            "module reports nominal mechanics, not AS 3600 design capacity."
        ),
    ),
    ConnectionContract(
        "frame-to-steel-section",
        "structural.pynite.frame_analysis",
        "structural.as4100.section_analysis",
        "adapter_required",
        (
            "Determine factored tension/compression design actions, member axis, load "
            "combination and sign; section axial capacity excludes member buckling."
        ),
    ),
    ConnectionContract(
        "frame-to-timber-beam",
        "structural.pynite.frame_analysis",
        "structural.as1720.beam_design",
        "adapter_required",
        (
            "Choose governing major/minor bending and shear, load duration and "
            "restraint; no automatic frame envelope is an AS 1720 member design."
        ),
    ),
    ConnectionContract(
        "frame-to-timber-column",
        "structural.pynite.frame_analysis",
        "structural.as1720.column_design",
        "adapter_required",
        (
            "Determine compression demand and member stability, restraint and "
            "effective length assumptions."
        ),
    ),
    ConnectionContract(
        "frame-to-timber-tension",
        "structural.pynite.frame_analysis",
        "structural.as1720.tension_design",
        "adapter_required",
        (
            "Select factored tension action and verify timber material, net area and "
            "connection exclusions."
        ),
    ),
)


def _field_schema(document: Any, pointer: str | None) -> dict[str, Any] | None:
    if not isinstance(document, dict) or not pointer or not pointer.startswith("/"):
        return None
    current = document
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if current.get("type") == "array":
            if not part.isdigit() or part.startswith("0") and part != "0":
                return None
            current = current.get("items")
        else:
            current = current.get("properties", {}).get(part)
        if not isinstance(current, dict):
            return None
    return current


def _schema_check(
    contract: ConnectionContract, source: dict[str, Any], target: dict[str, Any]
) -> tuple[bool, str]:
    if contract.mode != "direct":
        return False, "Explicit engineering review or a dedicated adapter is required."
    src = _field_schema(source.get("output_schema"), contract.output_path)
    dst = _field_schema(target.get("input_schema"), contract.input_path)
    if src is None or dst is None:
        return False, "A declared source output or destination input schema is missing."
    # A direct output path must exist in *every* valid source result, not just
    # be declared as an optional field. Reject unresolved references instead
    # of guessing that a missing output will be present at runtime.
    schema = source.get("output_schema")
    for component in (contract.output_path or "").strip("/").split("/"):
        if not isinstance(schema, dict):
            return False, "The source schema cannot prove this output path."
        if schema.get("type") == "array":
            if not component.isdecimal() or "minItems" not in schema:
                return False, "Array index availability is not proven."
            if int(component) >= schema["minItems"]:
                return False, "Array index is not guaranteed by the declared schema."
            schema = schema.get("items")
        else:
            if component.replace("~1", "/").replace("~0", "~") not in schema.get("required", []):
                return False, "The linked source field is not a required output."
            schema = schema.get("properties", {}).get(
                component.replace("~1", "/").replace("~0", "~")
            )
    src_type, dst_type = src.get("type"), dst.get("type")
    if src_type is None or dst_type is None or src_type != dst_type:
        return False, "Source and destination JSON types do not match."
    source_unit, target_unit = src.get("unit"), dst.get("unit")
    if src_type in {"integer", "number"} and (not source_unit or not target_unit):
        return False, "Numerical links require explicit source and destination units."
    if contract.unit:
        if source_unit != contract.unit or target_unit != contract.unit:
            return False, f"Both endpoints must explicitly declare unit {contract.unit}."
    elif source_unit != target_unit:
        return False, "Source and destination unit declarations differ."
    return True, "Schema paths and declared units are compatible."


def module_catalogue(registry: Any) -> list[dict[str, Any]]:
    plugins = {plugin.id: plugin for plugin in registry.plugins}
    entries = []
    for module in MODULES:
        plugin = plugins.get(module["id"])
        entries.append(
            {
                **module,
                "installed": plugin is not None,
                "version": str(plugin.version) if plugin is not None else None,
                "calculation_ids": sorted(calc.id for calc in plugin.calculations)
                if plugin
                else [],
            }
        )
    return entries


def connection_catalogue(
    registry: Any,
    *,
    calculation_id: str | None = None,
) -> list[dict[str, Any]]:
    descriptors = {descriptor["id"]: descriptor for descriptor in registry.list_calculations()}
    result = []
    for contract in CONNECTIONS:
        if calculation_id and calculation_id not in (contract.source, contract.target):
            continue
        source, target = descriptors.get(contract.source), descriptors.get(contract.target)
        installed = source is not None and target is not None
        compatible, detail = (
            _schema_check(contract, source, target)
            if installed
            else (False, "A required engineering module is not installed.")
        )
        result.append(
            {
                "id": contract.id,
                "source_calculation_id": contract.source,
                "target_calculation_id": contract.target,
                "mode": contract.mode,
                "source_output_path": contract.output_path,
                "target_input_path": contract.input_path,
                "unit": contract.unit,
                "installed": installed,
                "direct_link_ready": installed and compatible,
                "requires_engineer_review": True,
                "requires_adapter": contract.mode == "adapter_required",
                "automated_transfer_allowed": installed and compatible,
                "reason": contract.reason,
                "verification": detail,
            }
        )
    return result
