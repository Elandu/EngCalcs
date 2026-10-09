# EngCalcs

EngCalcs is the host platform for modular engineering calculation packages.

The application owns calculation discovery, execution, persistence, and project workflows. The frontend is maintained separately in EngCalcs-UI and consumes this API. Engineering formulae remain in independently versioned packages such as OpenWind-AU.

## Architecture

- `src/engcalcs/plugins.py` discovers installed calculation packages through the `engcalcs.plugins` Python entry-point group.
- `src/engcalcs/registry.py` combines those plugins into one calculation registry.
- `src/engcalcs/api.py` exposes a single API for listing and running calculations.
- EngCalcs-UI is the separately maintained frontend for identity, projects, and calculation workflows.

The Python distribution and import namespace are now `engcalcs`. Compatibility imports, the `opencalcs-mcp` command, the `opencalcs.plugins` entry-point group, and legacy `OPENCALCS_*` environment variables remain available for existing integrations.

OpenWind-AU exposes itself through:

```toml
[project.entry-points."engcalcs.plugins"]
openwind_au = "openwind_au.plugin:get_plugin"
```

## Development

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pip install -e ./plugins/pynite
python -m pip install "git+https://github.com/Elandu/OpenWind-AU.git@bc054f23d2645eb9dfe44b1b4b504a94ebec01db"
python -m pip install "git+https://github.com/Elandu/OpenCalcs-AS3600.git@engcalcs-rebrand"
python -m pip install "git+https://github.com/Elandu/OpenCalcs-AS4100.git@engcalcs-rebrand"
uvicorn engcalcs.api:app --reload
```

Then browse the API at `http://127.0.0.1:8000/docs`.

## Initial API

```text
GET  /health/live
GET  /api/plugins
GET  /api/calculations
GET  /api/calculations/{calculation_id}
POST /api/calculations/{calculation_id}/run
```


## API and MCP surfaces

EngCalcs is the primary public integration layer. Calculation modules remain independently
versioned and may retain their own specialist APIs/MCP servers for compatibility and
domain-specific workflows.

### REST API

New integrations should use the versioned endpoints:

```text
GET  /api/v1/plugins
GET  /api/v1/calculations
GET  /api/v1/calculations/{calculation_id}
POST /api/v1/calculations/{calculation_id}/run
```

The original unversioned `/api/...` routes are retained as compatibility aliases.

### EngCalcs MCP

The top-level MCP server uses the same installed plugin registry as the REST API and exposes:

```text
list_plugins
list_calculations
describe_calculation
run_calculation
```

A calculation is addressed by its stable identifier, for example
`au.wind.regional_wind_speed`. The response includes the owning plugin and its exact version,
so callers do not need to know where the calculation is implemented.

The intended hierarchy is:

```text
EngCalcs REST / MCP
       |
       +-- OpenWind-AU
       |     +-- calculation definitions
       |     +-- specialist wind evidence/workflow tools
       |     +-- legacy/direct OpenWind MCP retained
       |
       +-- future OpenLoads-AU
       +-- future OpenSteel-AU
       +-- future OpenConcrete-AU
```

The parent MCP owns discovery and generic execution. Domain modules may additionally expose
specialist MCP tools that do not fit the common calculation contract. Those module-specific
surfaces should remain namespaced and share the same underlying calculation code rather than
reimplementing formulae.

The `plugins/pynite` package registers the PyNite frame solver as a versioned EngCalcs
calculation engine. It is installed separately from the host so the host can keep its own
dependencies and provenance boundary.


## Licence and provenance

EngCalcs core is licensed under `AGPL-3.0-only`. See `LICENSE` and `NOTICE`.

Canonical source: https://github.com/Elandu/OpenCalcs

Substantive Python source files carry SPDX licence and copyright headers. The runtime
injects provenance automatically into calculation descriptors and results, including:

- EngCalcs runtime version and source revision;
- EngCalcs licence and canonical source URL;
- calculation plugin/engine ID, version, revision, licence and source URL;
- calculation definition ID/version; and
- standard metadata where supplied by the engineering module.

The public metadata endpoint is:

```text
GET /api/v1/about
```

This endpoint does not require authentication and provides the source/licence identity of
the running EngCalcs service and its installed engineering plugins.

Calculation results retain their normal engineering output fields and add the reserved
`_provenance` object. This metadata is also persisted with saved calculation runs by the
EngCalcs SaaS layer.
