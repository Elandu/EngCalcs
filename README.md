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
# The deployment manifest installs seven pinned engineering modules, including PyNite.
python -m pip install -r requirements-render.txt
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
GET  /api/v1/modules
GET  /api/v1/connections?calculation_id=<id>
```

The original unversioned `/api/...` routes are retained as compatibility aliases.

### EngCalcs MCP

The top-level MCP server uses the same installed plugin registry as the REST API and exposes:

```text
list_plugins
list_calculations
describe_calculation
run_calculation
list_engineering_modules
list_calculation_connections
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

## Engineering module integration

The pinned Python deployment includes the wind engine (AS/NZS 1170.2 and AS 4055),
structural actions (AS/NZS 1170.0/1), frame analysis (PyNite),
selected AS 3600 and AS 4100 section checks, F-grade AS 1720 timber strength
checks, and AS/NZS 3500.3 stormwater functions.

The host publishes the installed module list, exact plugin versions and
calculation descriptors through REST and MCP. It also advertises **connection
contracts**, which distinguish:

- `direct`: a required source output and target input have compatible JSON
  types and matching explicit units, e.g. an AS 3500 roof catchment area
  flowing into the AS 3500 roof-flow calculation.
- `reviewed_import`: values can be carried through a dedicated validation
  process after the engineer confirms load cases, member identifiers, axes and
  other assumptions (e.g. wind actions to frame analysis).
- `adapter_required`: a meaningful engineering conversion or selection is
  needed before transfer. A frame force diagram must not be silently used as
  an AS 3600, AS 4100 or AS 1720 design action.

The endpoints are **metadata only**. They neither execute calculations nor
approve/transfer design values. Every dependency still requires professional
review and saved run provenance. A declared connection contract is not an
independent certification of a calculation module. Source validation is
documented by each owning module's own test corpus.

Integration CI executes the pinned AS plugins through the one registry and
asserts that REST and MCP describe the same module and link status.

The parent MCP owns discovery and generic execution. Domain modules may additionally expose
specialist MCP tools that do not fit the common calculation contract. Those module-specific
surfaces should remain namespaced and share the same underlying calculation code rather than
reimplementing formulae.

The `plugins/pynite` package registers the PyNite frame solver as a versioned EngCalcs
calculation engine. It is installed separately from the host so the host can keep its own
dependencies and provenance boundary.


## Licence and provenance

The EngCalcs host and its PyNite adapter in this revision are proprietary;
see `LICENSE`, `NOTICE`, and `LICENSING.md`. Versions previously released
under AGPL-3.0-only retain their original rights. Third-party packages, including
PyNite, continue under their own licences and attribution obligations.

Provenance returned by `GET /api/v1/about` and calculation results identifies
the **actual runtime and plugin licence**. Legacy `opencalcs` import paths,
entry points, and environment variables remain available for compatibility.
