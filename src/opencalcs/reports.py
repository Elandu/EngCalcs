# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (c) 2026 Elandu and contributors

"""Issued engineering calculation-pack PDF generation."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from opencalcs.provenance import runtime_provenance

_STAGE_ORDER = ("site", "wind_region", "terrain", "shielding", "topography", "design")
_STAGE_LABELS = {
    "site": "Site and location",
    "wind_region": "Wind region and regional speed",
    "terrain": "Terrain and Mz,cat",
    "shielding": "Shielding",
    "topography": "Topography",
    "design": "Design wind speed",
}


def _text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _first(mapping: Any, *keys: str) -> Any:
    value = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _kv_table(rows: list[tuple[str, Any]], widths: tuple[float, float] = (55 * mm, 115 * mm)):
    data = [
        [
            Paragraph(str(label), _styles()["TableLabel"]),
            Paragraph(_text(value), _styles()["Body"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDE5E0")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F6F3")),
            ]
        )
    )
    return table


def _styles():
    styles = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "CalcTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#163128"),
            spaceAfter=4 * mm,
        ),
        "H1": ParagraphStyle(
            "CalcH1",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=colors.HexColor("#163128"),
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        ),
        "H2": ParagraphStyle(
            "CalcH2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#315E4D"),
            spaceBefore=2 * mm,
            spaceAfter=1.5 * mm,
        ),
        "Body": ParagraphStyle(
            "CalcBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#28362F"),
        ),
        "Small": ParagraphStyle(
            "CalcSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#66766F"),
        ),
        "TableLabel": ParagraphStyle(
            "CalcTableLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.8,
            leading=10,
            textColor=colors.HexColor("#485D54"),
        ),
        "Right": ParagraphStyle(
            "CalcRight",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#66766F"),
        ),
    }


def _stage_summary(stage_key: str, run: dict[str, Any]) -> list[tuple[str, Any]]:
    result = run.get("result_json") or {}
    if stage_key == "site":
        return [
            (
                "Address",
                _first(result, "site", "address") or _first(result, "site", "display_name"),
            ),
            ("Latitude", _first(result, "site", "latitude")),
            ("Longitude", _first(result, "site", "longitude")),
            ("Site RL", _first(result, "site", "elevation_m")),
        ]
    if stage_key == "wind_region":
        return [
            ("Wind region", _first(result, "wind_region_assessment", "wind_region")),
            (
                "Regional wind speed VR",
                _first(result, "regional_wind_speed_assessment", "regional_wind_speed_mps")
                or _first(result, "regional_wind_speed_assessment", "vr_mps"),
            ),
            ("Region confidence", _first(result, "wind_region_assessment", "confidence")),
            (
                "Boundary distance",
                _first(result, "wind_region_assessment", "distance_to_boundary_m"),
            ),
        ]
    if stage_key in {"terrain", "shielding", "topography"}:
        variables = result.get("variables") if isinstance(result, dict) else None
        if not isinstance(variables, list) and stage_key == "terrain":
            variables = _first(result, "mzcat_assessment")
        rows: list[tuple[str, Any]] = []
        if isinstance(variables, list):
            values = []
            for item in variables:
                if not isinstance(item, dict):
                    continue
                direction = item.get("direction") or item.get("wind_direction") or "-"
                value = (
                    item.get("final_value")
                    or item.get("recommended_value")
                    or item.get("mzcat")
                    or item.get("value")
                )
                if value is not None:
                    values.append(f"{direction}: {_text(value)}")
            if values:
                rows.append(("Directional adopted values", ", ".join(values)))
        if stage_key == "shielding":
            rows.append(
                (
                    "Obstructions reviewed",
                    _first(result, "obstruction_summary", "total_obstructions"),
                )
            )
        rows.append(
            (
                "Warnings",
                "; ".join(result.get("warnings", [])) if isinstance(result, dict) else "-",
            )
        )
        return rows
    if stage_key == "design":
        return [
            ("Governing Vsit,b", result.get("governing_vsitb")),
            ("Governing direction", result.get("governing_direction")),
            ("Governing Vdes,theta", result.get("governing_vdes_mps")),
            ("Governing faces", ", ".join(result.get("governing_vdes_faces", []))),
            ("Warnings", "; ".join(result.get("warnings", []))),
        ]
    return [("Result", result)]


def build_wind_calculation_pack(payload: dict[str, Any]) -> bytes:
    """Build a project-level issued Wind calculation pack."""

    styles = _styles()
    buffer = BytesIO()
    project = payload.get("project") or {}
    issue = payload.get("issue") or {}
    stages = payload.get("stages") or []
    overrides = payload.get("overrides") or []
    runtime = payload.get("runtime") or runtime_provenance()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=19 * mm,
        bottomMargin=18 * mm,
        title=f"{project.get('project_number') or 'Project'} - Wind Calculation Pack",
        author="OpenCalcs",
    )

    story: list[Any] = [
        Paragraph("OpenCalcs", styles["Small"]),
        Paragraph("Wind Calculation Pack", styles["Title"]),
        _kv_table(
            [
                ("Project", project.get("name")),
                ("Project number", project.get("project_number")),
                ("Site address", project.get("address")),
                ("Issue revision", issue.get("revision")),
                ("Issued at", issue.get("issued_at")),
                ("Issued by", issue.get("issued_by")),
                ("Workflow instance", payload.get("workflow_instance_id")),
            ]
        ),
        Spacer(1, 5 * mm),
        Paragraph("Design basis", styles["H1"]),
    ]

    design_inputs = payload.get("design_inputs") or {}
    story.append(
        _kv_table(
            [
                ("Standard", "AS/NZS 1170.2:2021"),
                (
                    "Annual exceedance probability",
                    design_inputs.get("annual_exceedance_probability"),
                ),
                ("Structure class", design_inputs.get("structure_class")),
                ("Overall building height", design_inputs.get("building_height_m")),
                ("Average roof height", design_inputs.get("average_roof_height_m")),
                ("Structure orientation beta", design_inputs.get("structure_orientation_deg")),
            ]
        )
    )

    story.extend(
        [
            Spacer(1, 4 * mm),
            Paragraph("Reviewed calculation stages", styles["H1"]),
        ]
    )

    stage_by_key = {
        item.get("stage_key"): item
        for item in stages
        if isinstance(item, dict) and item.get("stage_key")
    }

    for stage_key in _STAGE_ORDER:
        stage = stage_by_key.get(stage_key)
        if not stage:
            continue
        run = stage.get("run") or {}
        review = stage.get("review") or {}
        stage_block = [
            Paragraph(_STAGE_LABELS[stage_key], styles["H2"]),
            _kv_table(
                [
                    ("Run sequence", run.get("run_sequence")),
                    ("Run ID", run.get("id")),
                    ("Review status", review.get("status")),
                    ("Reviewer", review.get("reviewer")),
                    ("Reviewed at", review.get("reviewed_at")),
                ]
            ),
            Spacer(1, 1.5 * mm),
            _kv_table(_stage_summary(stage_key, run)),
            Spacer(1, 3 * mm),
        ]
        story.append(KeepTogether(stage_block))

    if overrides:
        story.extend(
            [
                Paragraph("Engineering overrides", styles["H1"]),
                Paragraph(
                    "The following engineer-entered overrides were applied and are "
                    "retained in the immutable calculation history.",
                    styles["Body"],
                ),
                Spacer(1, 2 * mm),
            ]
        )
        override_data = [["Variable", "Direction", "Adopted", "Reason"]]
        for override in overrides:
            override_data.append(
                [
                    _text(override.get("variable")),
                    _text(override.get("direction")),
                    _text(override.get("override_value")),
                    _text(override.get("reason")),
                ]
            )
        override_table = Table(
            override_data,
            colWidths=[28 * mm, 25 * mm, 30 * mm, 87 * mm],
            repeatRows=1,
            hAlign="LEFT",
        )
        override_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163128")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6DFDA")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([override_table, Spacer(1, 4 * mm)])

    story.extend(
        [
            Paragraph("Software provenance", styles["H1"]),
            _kv_table(
                [
                    ("OpenCalcs version", runtime.get("version")),
                    ("OpenCalcs revision", runtime.get("revision")),
                    ("OpenCalcs source", runtime.get("source")),
                    ("OpenCalcs licence", runtime.get("license")),
                    ("Engine", _first(payload, "engine", "name")),
                    ("Engine version", _first(payload, "engine", "version")),
                    ("Engine revision", _first(payload, "engine", "revision")),
                    ("Engine source", _first(payload, "engine", "source")),
                ]
            ),
            Spacer(1, 4 * mm),
            Paragraph(
                "This calculation pack records the reviewed calculation state and "
                "software provenance at the time of issue. "
                "Subsequent project changes do not alter this issued revision.",
                styles["Small"],
            ),
        ]
    )

    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D7E0DB"))
        canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
        canvas.setFillColor(colors.HexColor("#6C7C75"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 8.5 * mm, "OpenCalcs - issued calculation record")
        canvas.drawRightString(
            192 * mm,
            8.5 * mm,
            f"Page {document.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
