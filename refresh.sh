#!/usr/bin/env bash
set -uo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

# Load .env so per-source URL overrides (e.g. NATURE_OUTDOORS_GEOJSON) are
# available to the adapters. .env may not exist on first run; that is fine.
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi

if [[ ! -d .venv ]]; then
  echo "creating local virtualenv (.venv)"
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# No third-party deps at the moment: every adapter uses stdlib. Keep this
# block here so future adapters that need requests/bs4/etc. plug in cleanly.
if [[ -f requirements.txt ]]; then
  pip install -q -r requirements.txt
fi

ADAPTERS=(
  outdoors_fi
  laavu_org
  saunas_sheet
  waterfalls
  beaches
  water_sensors
  algae
  air_quality
  water_levels
  breweries
  archaeology
  heritage
  sacred_sites
  uusimaa_classics
  caves
  crags
  geo_sites
  local_beaches
  bucket_list
)

failed=()
for a in "${ADAPTERS[@]}"; do
  echo "---"
  if ! (cd adapters && "$PYTHON" "${a}.py"); then
    failed+=("$a")
  fi
done

echo "==="
if (( ${#failed[@]} > 0 )); then
  echo "FAILED: ${failed[*]}"
  echo "(other adapters succeeded; their layers were written)"
  exit 1
fi

echo "all adapters succeeded. Run 'bash deploy.sh' to ship the new data."
