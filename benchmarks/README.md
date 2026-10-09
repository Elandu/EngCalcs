# Frame solver comparison

This is an isolated engine pilot. Production remains PyNite.

## Result of the 2026-09-28 run

Stabileo revision: `7d87e551b765c88956df95b375e0ef0befda53f7`.
PyNite: 3.2.0 through the actual EngCalcs plugin.
Stabileo: actual Rust engine compiled to WASM; direct linear/P-Delta solver functions.

| Analytical fixture | PyNite | Stabileo |
| --- | --- | --- |
| Cantilever, tip load in local y | Pass | Pass |
| Cantilever, tip load in local z | Pass | Pass |
| Axial bar | Pass | Pass |
| Simply supported beam, uniform load | Pass | Pass |
| Compressed cantilever, P-Delta | Pass | **Fail: reaction equilibrium** |

The P-Delta model uses an 8-element, 5 m cantilever with E = 200,000,000 kPa,
Iz = 0.0001 m4, compression 150 kN and transverse tip force -1 kN. The analytical
beam-column deflection is `-(tan(kL)/k - L)/P`, k = sqrt(P/EI): -2.2524166845 mm.
Both engines match deflection closely. The transverse root reaction must be +1 kN.
PyNite returns 0.9999990948 kN; Stabileo returns 1.0120687687 kN (1.2069% excess).

The ledger deliberately retains this failure. Linear tolerance is 1e-6 relative;
P-Delta tolerance is 1e-3 relative (0.1%, allowing discretization). Tolerances were
set before reading the Stabileo numerical result. No tolerance was relaxed to pass it.
The benchmark exits nonzero until all selected solvers meet those tolerances.

This evidence supports retaining PyNite. It does not establish complete solver validation:
rotated members, portal frames, combinations, partial/trapezoidal loads, releases,
mechanisms, torsion, and convergence-failure behavior still require a wider qualification
suite before a production solver migration.

## Reproduce

1. Install the EngCalcs PyNite plugin dependencies in a Python environment.
2. Clone Stabileo and check out the exact revision above with a clean working tree.
3. Install Rust with its host linker and the `wasm32-unknown-unknown` target. This run used
   Rust 1.98.1 and a Windows GNU host toolchain. Use a local writable build directory.
4. Run `python benchmarks/build_stabileo_adapter.py --stabileo-source PATH --build-dir EMPTY_PATH`.
5. Run `python benchmarks/compare_frame_solvers.py --stabileo-wasm PATH_TO_WASM --json results.json`.

The builder checks the pinned source revision and uses the saved dependency lockfile.
The adapter consumes JSON through raw WASM memory and starts a fresh WASM instance per
fixture. Any JS-dependent WASM import fails explicitly if invoked. No solver callback or
numerical value is mocked. P-Delta results must report converged and stable before their
values are compared. Every subprocess has a timeout.

The saved `solver-comparison-20260928.json` records metric-level observations, including
the failure. The earlier `pynite-baseline-20260928.json` is the PyNite-only baseline.

On 2026-09-29 the documented builder was rerun in an empty directory using the pinned
source and lockfile. The build succeeded, and all five models reproduced the same metric
values and the same Stabileo P-Delta equilibrium failure. This checks the reproduction
procedure; it does not resolve that failure.

The PyNite-only comparison was also repeated in a fresh combined EngCalcs/OpenWind
environment on 2026-09-29. All five analytical fixtures passed with PyNite 3.2.0.
The host/plugin test suite passed 16 tests, including a regression that the in-process
OpenWind workflow uses the `localhost` host accepted by its default host policy.
