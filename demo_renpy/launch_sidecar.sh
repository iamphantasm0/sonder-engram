#!/usr/bin/env bash
#
# Convenient launcher for the Sonder sidecar (for the Ren'Py demo).
#
# Usage:
#   cd demo_renpy
#   ./launch_sidecar.sh
#
# It will:
#   - Load .env from the project root if present
#   - Start the sonder memory HTTP sidecar on 127.0.0.1:8765
#
# Then separately open the Ren'Py launcher and launch your project
# that contains the copied game/script.rpy + game/sonder.rpy files.

set -e

# Resolve directory of this script, then go to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Working from: $REPO_ROOT"

# Load environment variables from .env (if it exists)
if [ -f ".env" ]; then
    echo "==> Loading .env"
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
else
    echo "==> No .env found in repo root (using environment or defaults)"
fi

echo "==> Starting Sonder sidecar..."
echo "    URL: http://127.0.0.1:${SONDER_PORT:-8765}"
echo ""
echo "    IMPORTANT: Keep this running!"
echo "    In another terminal / Ren'Py launcher:"
echo "      1. Open Ren'Py"
echo "      2. Create or open a project"
echo "      3. Copy demo_renpy/game/*.rpy into its game/ folder"
echo "      4. Launch the project"
echo ""
echo "    Press Ctrl+C here to stop the sidecar."
echo ""

# Prefer the installed console script if available (best when you did "pip install -e .")
if command -v sonder-sidecar >/dev/null 2>&1; then
    echo "==> Using 'sonder-sidecar' command"
    exec sonder-sidecar --host 127.0.0.1 --port "${SONDER_PORT:-8765}"
fi

# Fall back to running the module directly.
# Prefer project's .venv if present (common when working in this repo)
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
    echo "==> Found local .venv, using .venv/bin/python"
elif [ -x ".venv/bin/python3" ]; then
    PY=".venv/bin/python3"
    echo "==> Found local .venv, using .venv/bin/python3"
else
    # Many systems only have 'python3', not a bare 'python'
    PY=$(command -v python3 || command -v python || true)
fi

if [ -z "$PY" ]; then
    echo "ERROR: Could not find 'python3' or 'python' in your PATH." >&2
    echo "Please install Python or activate the virtual environment that has sonder-engram." >&2
    echo "Tip: python -m pip install -e '.[fastembed]'" >&2
    exit 1
fi

echo "==> Using $PY -m sonder_engram.service"
exec "$PY" -m sonder_engram.service --host 127.0.0.1 --port "${SONDER_PORT:-8765}"
