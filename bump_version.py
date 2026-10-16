#!/usr/bin/env python
"""Bump [project].version in pyproject.toml - the single source of truth for the version.

    python bump_version.py              # 0.4.1 -> 0.4.2   (default: patch)
    python bump_version.py --part minor # 0.4.1 -> 0.5.0
    python bump_version.py --set 1.0.0  # set it explicitly

The "publish" job in .github/workflows/python-package.yml runs this after every
successful upload to PyPI, so the tree always holds the next version to be released
(pushing to main publishes whatever version pyproject.toml currently holds). No other
file needs to be edited - automonkey.__version__ and the built artifacts both read this
value.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

PYPROJECT = pathlib.Path(__file__).resolve().parent / "pyproject.toml"
VERSION_LINE = re.compile(r'(?m)^version\s*=\s*"(\d+\.\d+\.\d+)"')
PARTS = ("major", "minor", "patch")


def read_version(text: str) -> str:
    """Return the [project].version value, or exit with a useful message."""
    match = VERSION_LINE.search(text)
    if match is None:
        sys.exit(f'error: no `version = "x.y.z"` line found in {PYPROJECT}')
    return match.group(1)


def bumped(version: str, part: str) -> str:
    """Increase one component of X.Y.Z and zero the ones to its right."""
    numbers = [int(piece) for piece in version.split(".")]
    index = PARTS.index(part)
    numbers[index] += 1
    for rest in range(index + 1, len(numbers)):
        numbers[rest] = 0
    return ".".join(str(number) for number in numbers)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump the version in pyproject.toml.")
    parser.add_argument("--part", choices=PARTS, default="patch", help="which component to increase (default: patch)")
    parser.add_argument("--set", dest="explicit", metavar="X.Y.Z", help="set this version instead of bumping")
    args = parser.parse_args()

    text = PYPROJECT.read_text(encoding="utf-8")
    current = read_version(text)

    if args.explicit is not None:
        if not re.fullmatch(r"\d+\.\d+\.\d+", args.explicit):
            sys.exit(f"error: --set expects X.Y.Z, got {args.explicit!r}")
        new = args.explicit
    else:
        new = bumped(current, args.part)

    PYPROJECT.write_text(VERSION_LINE.sub(f'version = "{new}"', text, count=1), encoding="utf-8")
    print(f"{current} -> {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())