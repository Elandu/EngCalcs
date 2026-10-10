"""Guard the deployed engineering module catalogue against floating Git references."""

import re
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "requirements-render.txt"
EXPECTED_MODULES = {
    "EngCalcs-Wind": "openwind-au",
    "EngCalcs-AS1170": "engcalcs-as1170",
    "EngCalcs-AS1720": "opencalcs-as1720",
    "EngCalcs-AS3500": "opencalcs-as3500",
    "EngCalcs-AS3600": "opencalcs-as3600",
    "EngCalcs-AS4100": "opencalcs-as4100",
}
MODULE_PIN = re.compile(
    r"git\+https://github\.com/Elandu/(?P<repo>EngCalcs-[A-Za-z0-9]+)\.git"
    r"@(?P<sha>[0-9a-f]{40})#egg=(?P<distribution>[A-Za-z0-9_.-]+)"
)


def test_deployed_modules_use_immutable_commit_pins() -> None:
    requirements = [
        line.strip()
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    vcs_requirements = [line for line in requirements if line.startswith("git+")]
    assert len(vcs_requirements) == len(EXPECTED_MODULES)
    found = {}
    for requirement in vcs_requirements:
        match = MODULE_PIN.fullmatch(requirement)
        assert match is not None, f"Floating or unexpected module reference: {requirement}"
        repo = match.group("repo")
        assert repo not in found, f"Duplicate engineering module: {repo}"
        found[repo] = match.group("distribution")
    assert found == EXPECTED_MODULES
