# EngCalcs licence transition (prospective)

EngCalcs was previously made available under AGPL-3.0-only. This revision is
licensed as proprietary software to the extent the publisher owns or otherwise
controls the relevant rights. Earlier AGPL grants to recipients remain valid;
relicensing new revisions cannot retrospectively remove their permissions.

Third-party dependencies (including PyNiteFEA), incorporated MIT materials,
licenced engineering standards and data are governed by their own rights.
All required attributions must be preserved. The underlying solver's licence
is independent of the proprietary EngCalcs adapter licence.

The host and plugin runtime emit provenance metadata through REST/MCP; their
licence identifiers must match the shipped software. If a release installs
historical AGPL-licensed plugins, those plugins remain under AGPL until their
corresponding deployable revisions are lawfully relicensed.

**Repository privacy:** the source is currently hosted in a public repository.
Making it private requires a separate GitHub administrator setting change;
changing `LICENSE` alone does not prevent copying of already public code.

## Private-module deployment dependency

The Render deployment installs six pinned GitHub-hosted engine modules from
`requirements-render.txt` using `git+https://github.com/Elandu/...` URLs.
Changing these module repositories from public to private **before** a tested
read-only cross-repository installation credential is available will break
fresh deploys, even when the EngCalcs host repository itself remains connected
to Render. GitHub Actions CI has the same independent repository-access issue.

Before switching repository visibility:

1. Configure a narrowly scoped GitHub App installation or fine-grained token
   with read-only repository Contents access to all six private modules.
2. Make it available securely to the Render **build** environment and GitHub
   Actions jobs that install those pinned GitHub dependencies, never via a URL
   in committed source or printed installation logs.
3. Validate a staging build and module/plugin discovery with that credential;
   confirm `GET /api/v1/about` reports the intended installed versions and
   licences and that ordinary calculations still work.
4. Verify Vercel retains access to EngCalcs-UI when that repository is private.
5. Make repositories private only after these checks, then rotate any temporary
   credentials and confirm no public build artefacts expose source or secrets.

Changing privacy settings also does not remove forks/clones of historical
AGPL-licensed versions or rewrite existing rights. Owner approval and a legal
chain-of-title review remain necessary for third-party contributions or copied
materials. Do not modify the engineering formulas to conceal their origins.
