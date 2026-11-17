"""Publish AutoMonkey to PyPI from this machine. There is no GitHub Actions job any more
(CI and releases are local since 17.11.2026); this script does what its "publish" job did.

    python publish_pypi.py            # release the version in pyproject.toml, then bump it
    python publish_pypi.py --dry-run  # build and check everything, but don't upload or bump

1. Reads [project].version from pyproject.toml.
2. Stops if that version is already on PyPI (bump it first: python bump_version.py).
3. Builds the sdist and the wheel into a clean dist/ (python -m build).
4. Uploads them with twine. That needs a PyPI API token for the project AutoMonkey
   (user __token__) in ~/.pypirc, the keyring, or TWINE_USERNAME / TWINE_PASSWORD.
5. Bumps the patch version (bump_version.py), so the tree holds the next release.
Then commit pyproject.toml ("Bump version to X.Y.Z") and push.

Release only a committed tree, after the checks: the tests of what changed and
`flake8 . --select=E9,F63,F7,F82` (both need requirements_dev.txt: build, twine, flake8,
pytest).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import bump_version

ROOT = Path(__file__).resolve().parent


def on_pypi(version: str) -> bool:
    """True if AutoMonkey `version` has already been uploaded to PyPI."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/AutoMonkey/{version}/json", timeout=20):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Release AutoMonkey to PyPI from this machine.")
    parser.add_argument("--dry-run", action="store_true", help="build and check, but don't upload or bump")
    args = parser.parse_args()

    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty and not args.dry_run:
        print("Uncommitted changes: commit (and push) first, so the release is what main holds.\n" + dirty)
        return 1

    version = bump_version.read_version((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if on_pypi(version):
        print(f"AutoMonkey {version} is already on PyPI: bump the version first (python bump_version.py).")
        return 1

    for name in ("dist", "build", "AutoMonkey.egg-info"):
        shutil.rmtree(ROOT / name, ignore_errors=True)
    subprocess.run([sys.executable, "-m", "build"], cwd=ROOT, check=True)
    files = sorted(str(p) for p in (ROOT / "dist").iterdir())
    subprocess.run([sys.executable, "-m", "twine", "check", *files], cwd=ROOT, check=True)
    if args.dry_run:
        print(f"Dry run: AutoMonkey {version} built and checked ({len(files)} files in dist/); "
              "not uploaded, version not bumped.")
        return 0

    subprocess.run([sys.executable, "-m", "twine", "upload", "--repository", "pypi", *files], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "bump_version.py")], cwd=ROOT, check=True)
    print(f"Released AutoMonkey {version}. Commit pyproject.toml (\"Bump version to ...\") and push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
