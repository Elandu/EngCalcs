from __future__ import annotations

import asyncio
from importlib import import_module

from engcalcs.auth import EngCalcsAuthenticator, is_api_key_token
from engcalcs.plugins import discover_plugins


def test_previous_python_imports_are_aliases() -> None:
    assert import_module("opencalcs.api") is import_module("engcalcs.api")
    assert import_module("opencalcs.auth").OpenCalcsAuthenticator is EngCalcsAuthenticator


def test_legacy_environment_names_and_key_prefixes(monkeypatch) -> None:
    monkeypatch.delenv("ENGCALCS_SUPABASE_URL", raising=False)
    monkeypatch.setenv("OPENCALCS_SUPABASE_URL", "https://legacy.example")
    assert EngCalcsAuthenticator().supabase_url == "https://legacy.example"
    assert is_api_key_token("eng_live_example")
    assert is_api_key_token("oc_live_example")
    assert not is_api_key_token("other_example")


def test_key_verifier_falls_back_to_previous_function_name(monkeypatch) -> None:
    requests = []

    class Response:
        def __init__(self, status_code: int):
            self.status_code = status_code

        def json(self):
            return {
                "api_key_id": "key-1",
                "scopes": ["calculations:read"],
                "organisation_id": "org-1",
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers, json):
            requests.append((url, headers, json))
            return Response(404 if len(requests) == 1 else 200)

    monkeypatch.setattr("engcalcs.auth.httpx.AsyncClient", lambda **_kwargs: Client())
    context = asyncio.run(
        EngCalcsAuthenticator(supabase_url="https://supabase.example").verify_api_key(
            "eng_live_example"
        )
    )

    assert context.api_key_id == "key-1"
    assert requests[0][0].endswith("/functions/v1/engcalcs-key-verify")
    assert requests[1][0].endswith("/functions/v1/opencalcs-key-verify")
    assert requests[1][1]["x-opencalcs-key"] == "eng_live_example"


def test_plugin_discovery_prefers_new_group_and_deduplicates(monkeypatch) -> None:
    loaded = []

    class Plugin:
        def __init__(self, name: str):
            self.id = name
            self.name = name
            self.version = "1"
            self.calculations = ()

        def descriptor(self):
            return {}

    class EntryPoint:
        name = "sample"

        def __init__(self, source: str):
            self.source = source

        def load(self):
            return lambda: loaded.append(self.source) or Plugin(self.source)

    groups = {
        "engcalcs.plugins": [EntryPoint("current")],
        "opencalcs.plugins": [EntryPoint("legacy")],
    }
    monkeypatch.setattr("engcalcs.plugins.entry_points", lambda *, group: groups[group])

    plugins = discover_plugins()
    assert [plugin.id for plugin in plugins] == ["current"]
    assert loaded == ["current"]
