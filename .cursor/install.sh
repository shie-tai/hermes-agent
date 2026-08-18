#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for hermes-agent.
#
# Python is the backbone (the `hermes` agent, CLI, gateway, tests). Node is
# used by the first-class TUI (`hermes --tui`), the web dashboard, and the
# Electron desktop app. This script prepares both so a fresh agent can run
# the suite (scripts/run_tests.sh probes .venv first) and build every UI.
#
# Safe to run repeatedly: it only creates the venv when missing and lets uv /
# npm converge already-installed dependencies.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "▶ hermes-agent install: $(pwd)"

# ── Python: uv + a 3.11 venv (matches .python-version) + editable extras ─────
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "▶ installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "▶ uv $(uv --version)"

# .venv lives in the repo root because scripts/run_tests.sh probes it first.
if [ ! -x .venv/bin/python ]; then
  echo "▶ creating .venv (Python 3.11)"
  uv venv .venv --python 3.11
fi

# shellcheck disable=SC1091
source .venv/bin/activate
echo "▶ installing hermes-agent editable with [all,dev] extras"
uv pip install -e ".[all,dev]"

# ── Node: version pinned by .nvmrc (currently 26) + workspace deps ───────────
# /exec-daemon/node can shadow nvm on PATH, so resolve the nvm node bin
# explicitly and prepend it before invoking npm.
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  echo "▶ installing Node from .nvmrc ($(cat .nvmrc))"
  nvm install >/dev/null
  nvm use >/dev/null
  node_bin="$(dirname "$(nvm which current)")"
  export PATH="$node_bin:$PATH"
  echo "▶ node $(node --version) / npm $(npm --version)"
  echo "▶ installing JS workspace dependencies (ui-tui, web, apps/*, tests-js)"
  npm install
else
  echo "⚠ nvm not found at $NVM_DIR — skipping Node workspace install" >&2
fi

echo "✅ hermes-agent install complete"
