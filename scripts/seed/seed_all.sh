#!/usr/bin/env bash
# seed_all.sh — Run all domain seed waves in sequence for a fresh Concordance node
# Usage: bash scripts/seed/seed_all.sh [--delay N] [--dry-run] [--url URL]
#
# Waves:
#   Wave 1  (409 seeds, 17 domains) — core STEM + theology
#   Wave 2  (480 seeds, 23 domains) — natural sciences + technical domains
#   Wave 3  (227 seeds, 14 domains) — thin domain patches + correct domain keys
#   Wave 4  (215 seeds, 11 domains) — architecture/ecology/law/materials/nuclear/
#                                       oceanography/OR/philosophy/rhetoric/thermo
#   Wave 5  (100 seeds,  5 domains) — acoustics/document_validation/optics/
#                                       photography/witness
#
# Total: ~1,431 seeds across all 60 verifier domains.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DELAY="${DELAY:-1.2}"
DRY_RUN=""
URL=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --delay)    DELAY="$2"; shift 2 ;;
        --dry-run)  DRY_RUN="--dry-run"; shift ;;
        --url)      export CONCORDANCE_API="$2"; shift 2 ;;
        *)          echo "Unknown arg: $1"; exit 1 ;;
    esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Concordance domain seed runner"
echo " API: ${CONCORDANCE_API:-http://localhost:8000}"
echo " Delay: ${DELAY}s per seed"
echo " Dry run: ${DRY_RUN:-no}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

for wave in 1 2 3 4 5; do
    script="$SCRIPT_DIR/seed_domains${wave:+ }$([ "$wave" -eq 1 ] && echo "seed_domains.py" || echo "seed_domains_wave${wave}.py")"
    # Fix: proper script name selection
    if   [ "$wave" -eq 1 ]; then script="$SCRIPT_DIR/seed_domains.py"
    else                          script="$SCRIPT_DIR/seed_domains_wave${wave}.py"
    fi

    if [ ! -f "$script" ]; then
        echo "⚠  Wave $wave script not found: $script"
        continue
    fi

    echo "┌─ Wave $wave ─────────────────────────────────────────────"
    python3 "$script" --delay "$DELAY" $DRY_RUN
    echo "└──────────────────────────────────────────────────────"
    echo
done

echo "All waves complete."

# Show final journal count
if command -v curl &>/dev/null; then
    HEALTH=$(curl -s "${CONCORDANCE_API:-http://localhost:8000}/health" 2>/dev/null)
    TOTAL=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['modules']['journal']['total_entries'])" 2>/dev/null || echo "?")
    echo "Journal entries total: $TOTAL"
fi
