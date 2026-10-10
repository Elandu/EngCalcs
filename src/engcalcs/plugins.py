# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary
# Copyright (c) 2026 Elandu and contributors

"""Discovery of installed engineering calculation plugins."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import Any, Protocol


class PluginProtocol(Protocol):
    id: str
    name: str
    version: str
    calculations: tuple[Any, ...]

    def descriptor(self) -> dict[str, Any]: ...


def discover_plugins() -> tuple[PluginProtocol, ...]:
    """Load installed packages registered in the EngCalcs plugin group."""

    selected = {}
    for group in ("engcalcs.plugins", "opencalcs.plugins"):
        for entry_point in entry_points(group=group):
            selected.setdefault(entry_point.name, entry_point)

    discovered = [entry_point.load()() for entry_point in selected.values()]
    return tuple(sorted(discovered, key=lambda plugin: plugin.id))
