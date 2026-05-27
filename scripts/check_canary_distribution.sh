#!/bin/sh
set -e

BASE_URL=${BASE_URL:-http://127.0.0.1:8010}
N=${N:-30}

echo "Checking canary distribution via ${BASE_URL}/health"
echo "Requests: ${N}"
echo ""

for i in $(seq 1 "$N"); do
  curl -s "${BASE_URL}/health"
  echo ""
done
