# homebrew-tap

[![tests](https://github.com/SimonTarara62/homebrew-tap/actions/workflows/tests.yml/badge.svg)](https://github.com/SimonTarara62/homebrew-tap/actions/workflows/tests.yml)

Homebrew tap for [`capctl`](https://github.com/SimonTarara62/capitalcom-cli) —
the unofficial Capital.com Open API command-line client.

> Unofficial. Not affiliated with, endorsed by, or sponsored by Capital.com.

## Install

```bash
brew install SimonTarara62/tap/capctl
```

(`brew tap SimonTarara62/tap` first is optional; the one-liner taps implicitly.)

## Maintenance

- The formula installs `capitalcom-cli` from PyPI sdists with pinned, hashed
  dependency `resource` blocks.
- **Version bumps are automatic:** a workflow in the main repo
  (`.github/workflows/homebrew-bump.yml`) updates `Formula/capctl.rb`'s
  `url`/`sha256` on each `v*` tag.
- **When dependencies change** (a new/removed/upgraded runtime dependency),
  regenerate the resource blocks:

  ```bash
  python3 scripts/generate_resources.py <version>
  ```

  Requires network access; creates a throwaway virtualenv to resolve the pinned
  set and queries the PyPI JSON API for each sdist.
