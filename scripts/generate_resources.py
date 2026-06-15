#!/usr/bin/env python3
"""Generate Formula/capctl.rb for a given capitalcom-cli version.

Mirrors `brew update-python-resources` without needing Homebrew installed:

1. Resolve the full pinned runtime dependency set for capitalcom-cli==<version>
   by installing it into a throwaway virtualenv and reading `pip freeze`.
2. For each distribution (including capitalcom-cli itself) fetch the **sdist**
   URL + sha256 from the PyPI JSON API.
3. Render the entire Formula/capctl.rb from a template.

Usage:
    python3 scripts/generate_resources.py 0.6.2
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.request
import venv
from pathlib import Path

PKG = "capitalcom-cli"
ROOT = Path(__file__).resolve().parent.parent
FORMULA = ROOT / "Formula" / "capctl.rb"


def pypi_sdist(name: str, version: str) -> tuple[str, str]:
    """Return (url, sha256) of the sdist for name==version from PyPI."""
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url) as resp:  # noqa: S310 (trusted host)
        data = json.load(resp)
    for f in data["urls"]:
        if f["packagetype"] == "sdist":
            return f["url"], f["digests"]["sha256"]
    raise SystemExit(f"no sdist published for {name}=={version}")


def resolve_pins(version: str) -> dict[str, str]:
    """Install capitalcom-cli==version into a temp venv; return {name: version}."""
    with tempfile.TemporaryDirectory() as tmp:
        env_dir = Path(tmp) / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / "bin" / "python"
        subprocess.run(
            [str(py), "-m", "pip", "install", "-q", f"{PKG}=={version}"], check=True
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
class Capctl < Formula
  include Language::Python::Virtualenv

  desc "Unofficial command-line client for the Capital.com Open API"
  homepage "https://github.com/SimonTarara62/capitalcom-cli"
  url "{top_url}"
  sha256 "{top_sha}"
  license "Apache-2.0"

  depends_on "python@3.12"

{resources}
  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{{bin}}/capctl --version")
  end
end
'''


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: generate_resources.py <version>")
    version = sys.argv[1]

    pins = resolve_pins(version)
    pins.pop(PKG, None)  # the package itself is the top-level url, not a resource
    top_url, top_sha = pypi_sdist(PKG, version)

    blocks = [render_resource(name, pins[name]) for name in sorted(pins, key=str.lower)]
    resources = "\n".join(blocks)

    FORMULA.parent.mkdir(parents=True, exist_ok=True)
    FORMULA.write_text(
        TEMPLATE.format(top_url=top_url, top_sha=top_sha, resources=resources),
        encoding="utf-8",
    )
    print(f"wrote {FORMULA} ({len(blocks)} resources) for {PKG}=={version}")


if __name__ == "__main__":
    main()
