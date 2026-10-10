from __future__ import annotations

from dataclasses import dataclass

import engcalcs.mcp_server as mcp_server
from engcalcs.registry import CalculationRegistry


@dataclass(frozen=True)
class FakeCalculation:
    id: str = "test.double"
    version: str = "1"
    standard = None

    def descriptor(self):
        return {
            "id": self.id,
            "name": "Double",
            "category": "test",
            "input_schema": {"type": "object"},
        }

    def run(self, inputs):
        return {"value": inputs["value"] * 2}


@dataclass(frozen=True)
class FakePlugin:
    id: str = "test.plugin"
    name: str = "Test"
    version: str = "1"
    calculations: tuple = (FakeCalculation(),)

    def descriptor(self):
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "calculations": [item.descriptor() for item in self.calculations],
        }


def test_mcp_catalog_and_execution_use_shared_registry(monkeypatch) -> None:
    monkeypatch.setenv("ENGCALCS_SOURCE_REVISION", "runtime-test-revision")
    registry = CalculationRegistry(plugins=(FakePlugin(),))
    monkeypatch.setattr(mcp_server, "runtime", registry)

    calculations = mcp_server.list_calculations()
    assert calculations[0]["id"] == "test.double"
    assert calculations[0]["plugin"]["id"] == "test.plugin"
    assert calculations[0]["runtime"]["revision"] == "runtime-test-revision"

    result = mcp_server.run_calculation("test.double", {"value": 5})
    assert result["calculation"]["plugin"]["id"] == "test.plugin"
    assert result["result"]["value"] == 10
    assert result["provenance"]["runtime"]["revision"] == "runtime-test-revision"
    assert result["provenance"]["engine"]["id"] == "test.plugin"


def test_mcp_module_and_link_discovery_remains_read_only(monkeypatch) -> None:
    registry = CalculationRegistry(plugins=(FakePlugin(),))
    monkeypatch.setattr(mcp_server, "runtime", registry)
    modules = mcp_server.list_engineering_modules()
    links = mcp_server.list_calculation_connections()
    assert all(not module["installed"] for module in modules)
    assert all(not link["automated_transfer_allowed"] for link in links)
    assert mcp_server.list_calculation_connections("test.double") == []
