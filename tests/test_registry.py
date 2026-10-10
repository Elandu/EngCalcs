from __future__ import annotations

from dataclasses import dataclass

import pytest

from engcalcs.registry import CalculationRegistry


@dataclass(frozen=True)
class FakeCalculation:
    id: str
    version: str = "1"
    standard = None

    def descriptor(self):
        return {"id": self.id}

    def run(self, inputs):
        return {"value": inputs["value"] * 2}


@dataclass(frozen=True)
class FakePlugin:
    id: str
    name: str
    version: str
    calculations: tuple[FakeCalculation, ...]

    def descriptor(self):
        return {"id": self.id, "name": self.name, "version": self.version}


def test_registry_lists_and_runs_calculations(monkeypatch) -> None:
    monkeypatch.setenv("ENGCALCS_SOURCE_REVISION", "runtime-test-revision")
    registry = CalculationRegistry(
        plugins=(FakePlugin("test.plugin", "Test", "1", (FakeCalculation("test.double"),)),)
    )

    descriptor = registry.list_calculations()[0]
    assert descriptor["id"] == "test.double"
    assert descriptor["plugin"] == {
        "id": "test.plugin",
        "name": "Test",
        "version": "1",
    }
    assert descriptor["runtime"]["name"] == "EngCalcs"
    assert descriptor["runtime"]["revision"] == "runtime-test-revision"
    assert descriptor["runtime"]["license"] == "LicenseRef-EngCalcs-Proprietary"
    assert descriptor["runtime"]["source"] == "https://github.com/Elandu/EngCalcs"

    result = registry.run("test.double", {"value": 3})
    assert result["value"] == 6
    assert result["_provenance"]["runtime"]["revision"] == "runtime-test-revision"
    assert result["_provenance"]["engine"]["id"] == "test.plugin"
    assert result["_provenance"]["calculation"] == {
        "id": "test.double",
        "version": "1",
    }


def test_registry_rejects_duplicate_ids() -> None:
    calculation = FakeCalculation("test.duplicate")
    with pytest.raises(ValueError, match="Duplicate calculation id"):
        CalculationRegistry(
            plugins=(
                FakePlugin("one", "One", "1", (calculation,)),
                FakePlugin("two", "Two", "1", (calculation,)),
            )
        )
