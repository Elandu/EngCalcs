"""Build the isolated raw-JSON WASM adapter against the reviewed Stabileo revision."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

PINNED_REVISION = "7d87e551b765c88956df95b375e0ef0befda53f7"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stabileo-source", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--cargo", default="cargo")
    args = parser.parse_args()
    source = args.stabileo_source.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != PINNED_REVISION:
        raise SystemExit(f"Expected {PINNED_REVISION}, found {revision}")
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True):
        raise SystemExit("Stabileo checkout must be clean for a reproducible benchmark")
    build = args.build_dir.resolve()
    if build.exists() and any(build.iterdir()):
        raise SystemExit("Use an empty build directory; previous builds are preserved")
    (build / "src").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("stabileo_adapter.rs"), build / "src" / "lib.rs")
    engine_path = json.dumps((source / "engine").as_posix())
    (build / "Cargo.toml").write_text(
        '[package]\nname = "engcalcs-solver-benchmarks"\nversion = "0.1.0"\nedition = "2021"\n'
        '[lib]\ncrate-type = ["cdylib"]\n[dependencies]\n'
        f"dedaliano-engine = {{ path = {engine_path}, default-features = false }}\n"
        'serde_json = "=1.0.151"\n',
        encoding="utf-8",
    )
    shutil.copyfile(Path(__file__).with_name("stabileo-adapter.lock"), build / "Cargo.lock")
    subprocess.run(
        [
            args.cargo,
            "build",
            "--manifest-path",
            str(build / "Cargo.toml"),
            "--locked",
            "--target",
            "wasm32-unknown-unknown",
            "--release",
        ],
        check=True,
    )
    print(build / "target/wasm32-unknown-unknown/release/engcalcs_solver_benchmarks.wasm")


if __name__ == "__main__":
    main()
