# EngCalcs PyNite plugin

This package registers a PyNite-backed 3D elastic frame calculation with the EngCalcs plugin
host. The initial workflow supports nodes, frame members, material and section properties, nodal
and distributed member loads, supports, load cases, combinations, linear analysis, and P-Delta
analysis.

The calculation uses a consistent SI input set: kN, m, kPa, kN/m, and kN·m. It is not a design-code
capacity checker. Plates and shells, buckling analysis, and connection design are outside this
plugin's current model contract.

Install in a development EngCalcs environment with:

```powershell
python -m pip install -e .
python -m pip install -e .\plugins\pynite
```

PyNite is distributed under MIT. This proprietary adapter is covered by the EngCalcs licence. Historic AGPL-licensed revisions retain their previous grants. PyNite remains third-party MIT-licensed software.
