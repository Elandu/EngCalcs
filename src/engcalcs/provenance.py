# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
# Copyright (c) 2026 Elandu and contributors

"""Runtime and plugin provenance helpers for EngCalcs."""

from __future__ import annotations

import json
import os
from importlib.metadata import PackageNotFoundError, distribution
from typing import Any

from engcalcs import __version__

SOURCE_URL = "https://github.com/Elandu/EngCalcs"
LICENSE_ID = "LicenseRef-EngCalcs-Proprietary"


def distribution_revision(
    distribution_name: str,
    *,
    environment_variable: str | None = None,
) -> str:
    """Return a deployed/package VCS revision when available."""

    if environment_variable:
        configured = os.environ.get(environment_variable, "").strip()
        if not configured and environment_variable.startswith("ENGCALCS_"):
            legacy_name = environment_variable.replace("ENGCALCS_", "OPENCALCS_", 1)
            configured = os.environ.get(legacy_name, "").strip()
        if configured:
            return configured

    if distribution_name == "engcalcs":
        render_revision = os.environ.get("RENDER_GIT_COMMIT", "").strip()
        if render_revision:
            return render_revision

    try:
        installed = distribution(distribution_name)
    except PackageNotFoundError:
        return "unknown"

    direct_url_text = installed.read_text("direct_url.json")
    if not direct_url_text:
        return "unknown"

    try:
        direct_url = json.loads(direct_url_text)
    except json.JSONDecodeError:
        return "unknown"

    vcs_info = direct_url.get("vcs_info")
    if not isinstance(vcs_info, dict):
        return "unknown"

    commit_id = vcs_info.get("commit_id")
    return str(commit_id) if commit_id else "unknown"


def runtime_provenance() -> dict[str, str]:
    """Return immutable-identifying metadata for this EngCalcs runtime."""

    return {
        "name": "EngCalcs",
        "version": __version__,
        "revision": distribution_revision(
            "engcalcs",
            environment_variable="ENGCALCS_SOURCE_REVISION",
        ),
        "license": LICENSE_ID,
        "source": SOURCE_URL,
    }


def plugin_provenance(plugin: Any) -> dict[str, Any]:
    """Return provenance metadata from a calculation plugin with safe fallbacks."""

    descriptor = plugin.descriptor()
    provenance: dict[str, Any] = {
        "id": plugin.id,
        "name": plugin.name,
        "version": plugin.version,
    }
    for key in ("revision", "license", "source"):
        value = descriptor.get(key)
        if value:
            provenance[key] = value
    return provenance


def calculation_provenance(
    *,
    plugin: Any,
    calculation_id: str,
    calculation_version: str,
    standard: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return runtime + engine provenance for a calculation result."""

    return {
        "runtime": runtime_provenance(),
        "engine": plugin_provenance(plugin),
        "calculation": {
            "id": calculation_id,
            "version": calculation_version,
        },
        "standard": standard,
    }


def attach_calculation_provenance(
    result: dict[str, Any],
    *,
    plugin: Any,
    calculation_id: str,
    calculation_version: str,
    standard: dict[str, Any] | None,
) -> dict[str, Any]:
    """Add reserved provenance metadata without mutating the engine result."""

    enriched = dict(result)
    enriched["_provenance"] = calculation_provenance(
        plugin=plugin,
        calculation_id=calculation_id,
        calculation_version=calculation_version,
        standard=standard,
    )
    return enriched
