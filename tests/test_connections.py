from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from engcalcs.connections import CONNECTIONS, connection_catalogue, module_catalogue


@dataclass
class Calc:
    id: str
    input_schema: dict
    output_schema: dict

    def descriptor(self) -> dict:
        return {
            "id": self.id,
            "input_schema": deepcopy(self.input_schema),
            "output_schema": deepcopy(self.output_schema),
        }


@dataclass
class Plugin:
    id: str
    version: str
    calculations: tuple[Calc, ...]


class FakeRegistry:
    def __init__(self, *plugins: Plugin) -> None:
        self.plugins = plugins

    def list_calculations(self) -> list[dict]:
        return [calculation.descriptor() for p in self.plugins for calculation in p.calculations]


def roof_modules(unit: str = "m2", required: bool = True) -> FakeRegistry:
    source = Calc(
        "stormwater.as3500.roof_catchment", {},
        {
            "type": "object",
            "required": ["results"],
            "properties": {
                "results": {
                    "type": "object",
                    "required": ["catchment_area_m2"] if required else [],
                    "properties": {
                        "catchment_area_m2": {"type": "number", "unit": "m2"}
                    },
                },
            },
        },
    )
    destination = Calc(
        "stormwater.as3500.roof_flow",
        {
            "type": "object",
            "properties": {
                "catchment_area_m2": {"type": "number", "unit": unit},
            },
        },
        {},
    )
    return FakeRegistry(Plugin("stormwater.as3500", "0.2.0", (source, destination)))


def test_engineering_module_catalogue_is_accurate_about_missing_packages() -> None:
    catalogue = module_catalogue(FakeRegistry())
    assert len(catalogue) == 7
    assert {item["id"] for item in catalogue} == {
        "au.openwind", "structural.as1170", "structural.pynite",
        "structural.as3600", "structural.as4100", "structural.as1720",
        "stormwater.as3500",
    }
    assert all(item["installed"] is False for item in catalogue)
    assert all(item["calculation_ids"] == [] for item in catalogue)

    installed = module_catalogue(roof_modules())
    stormwater = next(row for row in installed if row["id"] == "stormwater.as3500")
    assert stormwater["installed"] is True
    assert stormwater["version"] == "0.2.0"
    assert stormwater["calculation_ids"] == [
        "stormwater.as3500.roof_catchment", "stormwater.as3500.roof_flow",
    ]


def test_only_verified_units_and_guaranteed_fields_enable_direct_roof_link() -> None:
    entry = next(row for row in connection_catalogue(roof_modules())
                 if row["id"] == "as3500-roof-area-to-roof-flow")
    assert entry["mode"] == "direct"
    assert entry["installed"] is True
    assert entry["direct_link_ready"] is True
    assert entry["automated_transfer_allowed"] is True
    assert entry["requires_engineer_review"] is True
    assert entry["source_output_path"] == "/results/catchment_area_m2"
    assert entry["target_input_path"] == "/catchment_area_m2"
    assert entry["unit"] == "m2"

    mismatch = next(row for row in connection_catalogue(roof_modules(unit="cm2"))
                    if row["id"] == "as3500-roof-area-to-roof-flow")
    assert mismatch["direct_link_ready"] is False
    assert "unit" in mismatch["verification"].lower()

    optional = next(row for row in connection_catalogue(roof_modules(required=False))
                    if row["id"] == "as3500-roof-area-to-roof-flow")
    assert optional["direct_link_ready"] is False
    assert "required" in optional["verification"].lower()


def test_frame_design_links_are_never_implicitly_executable() -> None:
    expected = {
        "frame-to-concrete-section",
        "frame-to-steel-section",
        "frame-to-timber-beam",
        "frame-to-timber-column",
        "frame-to-timber-tension",
        "as1170-actions-to-frame",
        "as1170-combination-review",
        "frame-actions-to-as1170-combinations",
    }
    contracts = {item.id: item for item in CONNECTIONS}
    for contract_id in expected:
        assert contracts[contract_id].mode == "adapter_required"
    for item in connection_catalogue(FakeRegistry()):
        assert item["requires_engineer_review"] is True
        assert item["automated_transfer_allowed"] is False


def test_calculation_filter_preserves_only_relevant_contracts() -> None:
    all_conns = connection_catalogue(roof_modules())
    filtered = connection_catalogue(
        roof_modules(), calculation_id="stormwater.as3500.roof_flow"
    )
    assert 0 < len(filtered) < len(all_conns)
    assert all(item["target_calculation_id"] == "stormwater.as3500.roof_flow" or
               item["source_calculation_id"] == "stormwater.as3500.roof_flow"
               for item in filtered)
