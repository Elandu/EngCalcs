from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from opencalcs.api import create_app
from opencalcs.auth import AllowAllAuthenticator
from opencalcs.registry import CalculationRegistry


@dataclass(frozen=True)
class FakeCalculation:
    id: str = "test.double"
    version: str = "1"
    standard = None

    def descriptor(self):
        return {"id": self.id, "name": "Double"}

    def run(self, inputs):
        return {"value": inputs["value"] * 2}


@dataclass(frozen=True)
class FakePlugin:
    id: str = "test.plugin"
    name: str = "Test"
    version: str = "1"
    calculations: tuple = (FakeCalculation(),)

    def descriptor(self):
        return {"id": self.id, "name": self.name, "version": self.version}


def test_api_lists_and_runs_calculation(monkeypatch) -> None:
    monkeypatch.setenv("OPENCALCS_SOURCE_REVISION", "runtime-test-revision")
    app = create_app(
        CalculationRegistry(plugins=(FakePlugin(),)),
        authenticator=AllowAllAuthenticator(),
    )
    client = TestClient(app)

    catalogue = client.get("/api/calculations").json()
    versioned_catalogue = client.get("/api/v1/calculations").json()
    assert catalogue == versioned_catalogue
    assert catalogue[0]["id"] == "test.double"
    assert catalogue[0]["plugin"]["id"] == "test.plugin"
    assert catalogue[0]["runtime"]["revision"] == "runtime-test-revision"

    response = client.post("/api/calculations/test.double/run", json={"inputs": {"value": 4}})
    versioned_response = client.post(
        "/api/v1/calculations/test.double/run",
        json={"inputs": {"value": 4}},
    )
    assert response.status_code == 200
    assert versioned_response.status_code == 200
    assert response.json()["value"] == 8
    assert versioned_response.json()["value"] == 8
    assert response.json()["_provenance"]["runtime"]["revision"] == "runtime-test-revision"
    assert response.json()["_provenance"]["engine"]["id"] == "test.plugin"


def test_about_exposes_source_and_licence_metadata(monkeypatch) -> None:
    monkeypatch.setenv("OPENCALCS_SOURCE_REVISION", "runtime-test-revision")
    app = create_app(
        CalculationRegistry(plugins=(FakePlugin(),)),
        authenticator=AllowAllAuthenticator(),
    )
    client = TestClient(app)

    response = client.get("/api/v1/about")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runtime"]["name"] == "OpenCalcs"
    assert payload["runtime"]["revision"] == "runtime-test-revision"
    assert payload["runtime"]["license"] == "AGPL-3.0-only"
    assert payload["runtime"]["source"] == "https://github.com/Elandu/OpenCalcs"
    assert payload["plugins"][0]["id"] == "test.plugin"
