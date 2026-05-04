#!/usr/bin/env bash
# build_binary.sh — produce a single-file `concordance` executable.
#
# Result: dist/concordance (or concordance.exe on Windows) — one file,
# no Python install required on the target machine. Bundles the engine
# + sympy/numpy/scipy + the verifier layer + CLI.
#
# Usage:
#   bash scripts/build_binary.sh         # build for current platform
#   bash scripts/build_binary.sh --gui   # build a windowed app (no console)
#
# Requires: Python 3.10+, pip, PyInstaller (installed automatically).
#
# Cross-compiling is not supported by PyInstaller — to ship binaries
# for Linux/macOS/Windows, run this on each target platform (or use
# the GitHub Actions release workflow which does it for you).

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Determine extension by platform.
EXT=""
case "$(uname -s)" in
  MINGW*|CYGWIN*|MSYS*) EXT=".exe" ;;
esac

# Console vs GUI mode.
CONSOLE_FLAG="--console"
if [ "${1:-}" = "--gui" ]; then
  CONSOLE_FLAG="--noconsole"
fi

echo ">> Installing PyInstaller + project (editable)..."
python -m pip install --upgrade pip
pip install -e . pyinstaller

echo ">> Cleaning prior build artifacts..."
rm -rf build/ dist/concordance*

echo ">> Building one-file binary..."
pyinstaller \
  --onefile \
  --name "concordance${EXT}" \
  --collect-all concordance_engine \
  --hidden-import concordance_engine.cli \
  ${CONSOLE_FLAG} \
  src/concordance_engine/cli.py

echo ">> Smoke-testing the binary..."
./dist/concordance${EXT} --help > /dev/null

SIZE_BYTES=$(stat -c%s "./dist/concordance${EXT}" 2>/dev/null || stat -f%z "./dist/concordance${EXT}")
SIZE_MB=$(echo "scale=1; $SIZE_BYTES / 1048576" | bc 2>/dev/null || echo "$SIZE_BYTES bytes")

echo ""
echo "============================================================"
echo "  Done.  dist/concordance${EXT}  (${SIZE_MB} MB)"
echo ""
echo "  Drop this file on any compatible host — no Python install"
echo "  required. Run with: ./dist/concordance${EXT} --help"
echo "============================================================"
