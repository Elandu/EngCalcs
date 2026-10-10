# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
# Copyright (c) 2026 Elandu and contributors

"""Unified calculation registry assembled from installed plugins."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from engcalcs.plugins import PluginProtocol, discover_plugins
from engcalcs.provenance import (
    attach_calculation_provenance,
    plugin_provenance,
    runtime_provenance,
)


class CalculationRegistry:
    """Collection of calculations exposed by all installed engineering plugins."""

    def __init__(self, plugins: tuple[PluginProtocol, ...] | None = None) -> None:
        self.plugins = plugins if plugins is not None else discover_plugins()
        self._calculations: dict[str, Any] = {}
        self._plugins_by_calculation_id: dict[str, PluginProtocol] = {}
        for plugin in self.plugins:
            for calculation in plugin.calculations:
                if calculation.id in self._calculations:
                    raise ValueError(f"Duplicate calculation id: {calculation.id}")
                self._calculations[calculation.id] = calculation
                self._plugins_by_calculation_id[calculation.id] = plugin

    def list_calculations(self) -> list[dict[str, Any]]:
        """Return calculation descriptors in stable identifier order."""

        return [self.describe(calculation_id) for calculation_id in sorted(self._calculations)]

    def get(self, calculation_id: str) -> Any:
        """Return one calculation by stable identifier."""

        try:
            return self._calculations[calculation_id]
        except KeyError as exc:
            raise KeyError(f"Unknown calculation: {calculation_id}") from exc

    def get_plugin(self, calculation_id: str) -> PluginProtocol:
        """Return the plugin that owns a calculation."""

        try:
            return self._plugins_by_calculation_id[calculation_id]
        except KeyError as exc:
            raise KeyError(f"Unknown calculation: {calculation_id}") from exc

    def describe(self, calculation_id: str) -> dict[str, Any]:
        """Return a calculation descriptor with runtime and plugin provenance."""

        definition = self.get(calculation_id)
        descriptor = definition.descriptor()
        descriptor["plugin"] = plugin_provenance(self.get_plugin(calculation_id))
        descriptor["runtime"] = runtime_provenance()
        return descriptor

    def run(self, calculation_id: str, inputs: Mapping[str, Any]) -> dict[str, Any]:
        """Execute one registered calculation and attach immutable provenance."""

        definition = self.get(calculation_id)
        result = definition.run(inputs)
        standard = (
            definition.standard.descriptor()
            if getattr(definition, "standard", None) is not None
            else None
        )
        return attach_calculation_provenance(
            result,
            plugin=self.get_plugin(calculation_id),
            calculation_id=definition.id,
            calculation_version=str(getattr(definition, "version", "unknown")),
            standard=standard,
        )
