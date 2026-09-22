# OpenCalcs

OpenCalcs is the host platform for modular engineering calculation packages.

The application owns calculation discovery, execution, persistence, project workflows and the user interface. Engineering formulae remain in independently versioned packages such as OpenWind-AU.

## Architecture

- `src/opencalcs/plugins.py` discovers installed calculation packages through the `opencalcs.plugins` Python entry-point group.
- `src/opencalcs/registry.py` combines those plugins into one calculation registry.
- `src/opencalcs/api.py` exposes a single API for listing and running calculations.
- `web/` is reserved for the React/Next.js application.

OpenWind-AU exposes itself through:

```toml
[project.entry-points."opencalcs.plugins"]
openwind_au = "openwind_au.plugin:get_plugin"
```

## Development

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pip install "git+https://github.com/Elandu/OpenWind-AU.git@bc054f23d2645eb9dfe44b1b4b504a94ebec01db"
uvicorn opencalcs.api:app --reload
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

OpenCalcs is the primary public integration layer. Calculation modules remain independently
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

### OpenCalcs MCP

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
OpenCalcs REST / MCP
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


## Licence and provenance

OpenCalcs core is licensed under `AGPL-3.0-only`. See `LICENSE` and `NOTICE`.

Canonical source: https://github.com/Elandu/OpenCalcs

Substantive Python source files carry SPDX licence and copyright headers. The runtime
injects provenance automatically into calculation descriptors and results, including:

- OpenCalcs runtime version and source revision;
- OpenCalcs licence and canonical source URL;
- calculation plugin/engine ID, version, revision, licence and source URL;
- calculation definition ID/version; and
- standard metadata where supplied by the engineering module.

The public metadata endpoint is:

```text
GET /api/v1/about
```

This endpoint does not require authentication and provides the source/licence identity of
the running OpenCalcs service and its installed engineering plugins.

Calculation results retain their normal engineering output fields and add the reserved
`_provenance` object. This metadata is also persisted with saved calculation runs by the
OpenCalcs SaaS layer.
