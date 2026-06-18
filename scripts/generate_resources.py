#!/usr/bin/env python3
"""Generate a Homebrew formula for a Python package on PyPI.

Mirrors `brew update-python-resources` without needing Homebrew installed:

1. Resolve the full pinned runtime dependency set for <pkg>==<version> by
   installing it into a throwaway virtualenv and reading `pip freeze`.
2. For each distribution (including the top-level pkg) fetch the **sdist**
   URL + sha256 from the PyPI JSON API.
3. Render the per-package Formula/<basename>.rb from the registered template.

Add a package by extending the `PACKAGES` dict below with its formula
metadata; the script handles dependency resolution + rendering generically.

Usage:
    python3 scripts/generate_resources.py capitalcom-cli 0.6.2
    python3 scripts/generate_resources.py fundamentals-mcp 0.1.0
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request
import venv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class PackageConfig:
    pypi_name: str
    formula_class: str         # Ruby class name (CamelCase) inside the .rb file
    formula_basename: str      # Filename under Formula/ (without .rb)
    description: str           # `desc "..."` in the formula
    homepage: str              # `homepage "..."` in the formula
    test_body: str             # Body of the `test do ... end` block
    extra_depends_on: list[str]  # additional `depends_on "..."` lines beyond python+rust


PACKAGES: dict[str, PackageConfig] = {
    "capitalcom-cli": PackageConfig(
        pypi_name="capitalcom-cli",
        formula_class="Capctl",
        formula_basename="capctl",
        description="Unofficial command-line client for the Capital.com Open API",
        homepage="https://github.com/SimonTarara62/capitalcom-cli",
        test_body='    assert_match version.to_s, shell_output("#{bin}/capctl --version")',
        extra_depends_on=[],
    ),
    "fundamentals-mcp": PackageConfig(
        pypi_name="fundamentals-mcp",
        formula_class="FundamentalsMcp",
        formula_basename="fundamentals-mcp",
        description="Unofficial MCP server for read-only fundamentals, macro & news data",
        homepage="https://github.com/SimonTarara62/fundamentals-mcp",
        # `doctor` returns 0 with no keys set (server is credential-free); use it
        # as the smoke test so we don't need to spawn the FastMCP stdio loop.
        test_body=(
            '    output = shell_output("#{bin}/fundamentals-mcp doctor")\n'
            '    assert_match "Configuration loaded", output'
        ),
        extra_depends_on=[],
    ),
}


def pypi_sdist(name: str, version: str) -> tuple[str, str]:
    """Return (url, sha256) of the sdist for name==version from PyPI."""
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url) as resp:  # noqa: S310 (trusted host)
        data = json.load(resp)
    for f in data["urls"]:
        if f["packagetype"] == "sdist":
            return f["url"], f["digests"]["sha256"]
    raise SystemExit(f"no sdist published for {name}=={version}")


def resolve_pins(pkg: str, version: str) -> dict[str, str]:
    """Install pkg==version into a temp venv; return {name: version}."""
    with tempfile.TemporaryDirectory() as tmp:
        env_dir = Path(tmp) / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / "bin" / "python"
        subprocess.run(
            [str(py), "-m", "pip", "install", "-q", f"{pkg}=={version}"], check=True
        )
        frozen = subprocess.run(
            [str(py), "-m", "pip", "freeze"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    pins: dict[str, str] = {}
    for line in frozen.splitlines():
        line = line.strip()
        if "==" in line and not line.startswith("-e"):
            name, ver = line.split("==", 1)
            pins[name.strip()] = ver.strip()
    return pins


def render_resource(name: str, version: str) -> str:
    url, sha = pypi_sdist(name, version)
    return (
        f'  resource "{name}" do\n'
        f'    url "{url}"\n'
        f'    sha256 "{sha}"\n'
        f"  end\n"
    )


TEMPLATE = '''\
class {formula_class} < Formula
  include Language::Python::Virtualenv

  desc "{description}"
  homepage "{homepage}"
  url "{top_url}"
  sha256 "{top_sha}"
  license "Apache-2.0"

  depends_on "python@3.12"
  depends_on "rust" => :build  # pydantic-core builds from a Rust sdist
{extra_depends_on}
{resources}
  def install
    virtualenv_install_with_resources
  end

  test do
{test_body}
  end
end
'''


def main() -> None:
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(
            "generate_resources.py must run on Python 3.12 to match the formula's "
            f"depends_on 'python@3.12' (got "
            f"{sys.version_info.major}.{sys.version_info.minor})"
        )
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: generate_resources.py <pypi-name> <version>\n"
            f"registered packages: {sorted(PACKAGES)}"
        )
    pkg_name, version = sys.argv[1], sys.argv[2]
    cfg = PACKAGES.get(pkg_name)
    if cfg is None:
        raise SystemExit(
            f"unknown package '{pkg_name}'. Registered: {sorted(PACKAGES)}. "
            "Add a PackageConfig entry to PACKAGES."
        )

    formula_path = ROOT / "Formula" / f"{cfg.formula_basename}.rb"

    pins = resolve_pins(cfg.pypi_name, version)
    pins.pop(cfg.pypi_name, None)
    top_url, top_sha = pypi_sdist(cfg.pypi_name, version)

    blocks = [render_resource(name, pins[name]) for name in sorted(pins, key=str.lower)]
    resources = "\n".join(blocks)
    extra_depends = (
        "".join(f'  depends_on "{d}"\n' for d in cfg.extra_depends_on)
        if cfg.extra_depends_on
        else ""
    )

    formula_path.parent.mkdir(parents=True, exist_ok=True)
    formula_path.write_text(
        TEMPLATE.format(
            formula_class=cfg.formula_class,
            description=cfg.description,
            homepage=cfg.homepage,
            top_url=top_url,
            top_sha=top_sha,
            extra_depends_on=extra_depends,
            resources=resources,
            test_body=cfg.test_body,
        ),
        encoding="utf-8",
    )
    print(f"wrote {formula_path} ({len(blocks)} resources) for {cfg.pypi_name}=={version}")


if __name__ == "__main__":
    main()
