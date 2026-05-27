#!/usr/bin/env python3
"""
Build and publish aura-web to PyPI.

Usage:
    python3 build_to_pypi.py              # build + publish (asks for token)
    python3 build_to_pypi.py --build      # build only, skip upload
    python3 build_to_pypi.py --check      # validate packages without uploading
    python3 build_to_pypi.py --test       # publish to TestPyPI instead

Token can also be set via environment variable:
    PYPI_TOKEN=pypi-xxx python3 build_to_pypi.py
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ─── Config ──────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
DIST = ROOT / "dist"

PYPI_REPO   = "https://upload.pypi.org/legacy/"
TESTPYPI_REPO = "https://test.pypi.org/legacy/"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"\n❌  Command failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    return result


def step(msg: str) -> None:
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {msg}")
    print(f"{'─' * width}")


# ─── Steps ───────────────────────────────────────────────────────────────────

def clean() -> None:
    step("🧹  Cleaning dist/")
    if DIST.exists():
        shutil.rmtree(DIST)
        print("   Removed dist/")
    else:
        print("   dist/ already clean")


def build() -> None:
    step("📦  Building wheel + sdist")
    run([sys.executable, "-m", "build"], cwd=ROOT)
    artifacts = list(DIST.glob("*"))
    print(f"\n   Built {len(artifacts)} artifacts:")
    for f in artifacts:
        size_kb = f.stat().st_size / 1024
        print(f"   • {f.name}  ({size_kb:.1f} KB)")


def check() -> None:
    step("🔍  Validating packages (twine check)")
    run([sys.executable, "-m", "twine", "check"] + list(DIST.glob("*")), cwd=ROOT)
    print("\n   ✅  All packages passed validation")


def upload(token: str, repo_url: str, test: bool = False) -> None:
    label = "TestPyPI" if test else "PyPI"
    step(f"🚀  Uploading to {label}")

    run([
        sys.executable, "-m", "twine", "upload",
        "--repository-url", repo_url,
        "--username", "__token__",
        "--password", token,
        "--non-interactive",
    ] + list(DIST.glob("*")), cwd=ROOT)

    pkg_name = _get_package_name()
    if test:
        print(f"\n   ✅  Published to TestPyPI!")
        print(f"   🔗  https://test.pypi.org/project/{pkg_name}/")
        print(f"\n   Test install:")
        print(f"   pip install --index-url https://test.pypi.org/simple/ {pkg_name}")
    else:
        print(f"\n   ✅  Published to PyPI!")
        print(f"   🔗  https://pypi.org/project/{pkg_name}/")
        print(f"\n   Install:")
        print(f"   pip install {pkg_name}")


def _get_package_name() -> str:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["name"]


def _get_token(args: argparse.Namespace) -> str:
    # 1. CLI argument
    if args.token:
        return args.token
    # 2. Environment variable
    token = os.environ.get("PYPI_TOKEN", "")
    if token:
        print("   (using token from PYPI_TOKEN env var)")
        return token
    # 3. Interactive prompt
    import getpass
    print()
    token = getpass.getpass("   PyPI API token (pypi-...): ").strip()
    if not token:
        print("❌  No token provided")
        sys.exit(1)
    return token


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and publish aura-web to PyPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--build",  action="store_true", help="Build only, skip upload")
    parser.add_argument("--check",  action="store_true", help="Build + validate, skip upload")
    parser.add_argument("--test",   action="store_true", help="Publish to TestPyPI")
    parser.add_argument("--token",  metavar="TOKEN",     help="PyPI API token")
    parser.add_argument("--skip-clean", action="store_true", help="Keep existing dist/")
    args = parser.parse_args()

    print("\n🌟  Aura-Web — PyPI Publisher")

    if not args.skip_clean:
        clean()

    build()
    check()

    if args.build or args.check:
        print("\n   Done (upload skipped)")
        return

    token = _get_token(args)
    repo_url = TESTPYPI_REPO if args.test else PYPI_REPO
    upload(token, repo_url, test=args.test)


if __name__ == "__main__":
    main()
