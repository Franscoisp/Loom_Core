#!/usr/bin/env bash
# Loom Core — one-line install for Linux/macOS (spec §14)
# curl -fsSL https://raw.githubusercontent.com/Franscoisp/Loom_Core/main/scripts/install.sh | bash
set -euo pipefail

REPO="https://github.com/Franscoisp/Loom_Core.git"
INSTALL_DIR="$HOME/loom-core"

echo "=== Loom Core Installer ==="

# Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3.11+ is required but not found on PATH." >&2
    exit 1
fi
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python $PYVER detected"

# clone / update
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Cloning Loom Core..."
    git clone "$REPO" "$INSTALL_DIR"
else
    echo "Updating existing install..."
    (cd "$INSTALL_DIR" && git pull)
fi

cd "$INSTALL_DIR"

# venv
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing loom-core + dev extras..."
pip install -q -e ".[dev]"

echo ""
echo "=== Running quality gates ==="
python -m pytest -q 2>&1 | tail -2
python -m ruff check . 2>&1 | tail -1 || true

echo ""
echo "=== Running loom doctor ==="
python -m loom_core.cli doctor

echo ""
echo "=== All done! ==="
echo "To start using Loom Core:"
echo "  cd $INSTALL_DIR"
echo "  source .venv/bin/activate"
echo "  loom version"
echo "  loom tui       (launch the TUI)"
echo "  loom --help    (see all commands)"
