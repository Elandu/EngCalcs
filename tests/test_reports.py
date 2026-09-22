from __future__ import annotations

from opencalcs.reports import build_wind_calculation_pack


def sample_payload() -> dict:
    stages = []
    stage_results = {
        "site": {
            "site": {
                "address": "88 Example Street, Parramatta NSW",
                "latitude": -33.815,
                "longitude": 151.003,
                "elevation_m": 28.4,
            }
        },
        "wind_region": {
            "wind_region_assessment": {
                "wind_region": "A2",
                "confidence": "high",
                "distance_to_boundary_m": 48200,
            },
            "regional_wind_speed_assessment": {
                "regional_wind_speed_mps": 45.0,
            },
        },
        "terrain": {
            "mzcat_assessment": [
                {"direction": "N", "mzcat": 1.03},
                {"direction": "E", "mzcat": 1.01},
                {"direction": "S", "mzcat": 1.02},
                {"direction": "W", "mzcat": 1.00},
            ],
            "directions": [{}, {}, {}, {}, {}, {}, {}, {}],
            "warnings": [],
        },
        "shielding": {
            "variables": [
                {"direction": "N", "final_value": 0.95},
                {"direction": "E", "final_value": 0.96},
                {"direction": "S", "final_value": 1.0},
                {"direction": "W", "final_value": 0.98},
            ],
            "obstruction_summary": {"total_obstructions": 24},
        },
        "topography": {
            "variables": [
                {"direction": "N", "final_value": 1.0},
                {"direction": "E", "final_value": 1.0},
                {"direction": "S", "final_value": 1.05},
                {"direction": "W", "final_value": 1.0},
            ],
        },
        "design": {
            "governing_vsitb": 47.3,
            "governing_direction": "S",
            "governing_vdes_mps": 48.0,
            "governing_vdes_faces": ["front"],
            "warnings": [],
        },
    }
    labels = {
        "site": "Site and location",
        "wind_region": "Wind region and regional speed",
        "terrain": "Terrain and Mz,cat",
        "shielding": "Shielding",
        "topography": "Topography",
        "design": "Design wind speed",
    }
    for index, stage_key in enumerate(stage_results, start=1):
        stages.append(
            {
                "stage_key": stage_key,
                "title": labels[stage_key],
                "run": {
                    "id": f"00000000-0000-0000-0000-00000000000{index}",
                    "run_sequence": 2 if stage_key in {"shielding", "design"} else 1,
                    "result_json": stage_results[stage_key],
                },
                "review": {
                    "status": "approved",
                    "reviewer": "reviewer-user-id",
                    "reviewed_at": "2026-09-22T00:00:00Z",
                },
            }
        )

    return {
        "project": {
            "project_number": "24017",
            "name": "Example Warehouse",
            "address": "88 Example Street, Parramatta NSW",
        },
        "workflow_instance_id": "11111111-2222-3333-4444-555555555555",
        "design_inputs": {
            "annual_exceedance_probability": "1/500",
            "structure_class": "building",
            "building_height_m": 10.0,
            "average_roof_height_m": 8.0,
            "structure_orientation_deg": 0.0,
        },
        "stages": stages,
        "overrides": [
            {
                "variable": "Ms",
                "direction": "N",
                "override_value": 0.95,
                "reason": "Reviewed surrounding shielding from site imagery.",
            }
        ],
        "runtime": {
            "name": "OpenCalcs",
            "version": "0.1.0",
            "revision": "runtime-revision",
            "license": "AGPL-3.0-only",
            "source": "https://github.com/Elandu/OpenCalcs",
        },
        "engine": {
            "name": "OpenWind-AU",
            "version": "0.8.0",
            "revision": "engine-revision",
            "source": "https://github.com/Elandu/OpenWind-AU",
        },
        "issue": {
            "revision": 1,
            "issued_at": "2026-09-22T00:15:00Z",
            "issued_by": "issuer-user-id",
        },
    }


def test_wind_calculation_pack_is_pdf() -> None:
    pdf = build_wind_calculation_pack(sample_payload())

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5_000
    assert b"OpenCalcs" in pdf
