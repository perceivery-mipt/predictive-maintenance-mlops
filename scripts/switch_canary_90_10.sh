#!/bin/sh
set -e

cp infra/nginx/nginx-canary-90-10.conf infra/nginx/nginx.active.conf
docker compose -f infra/docker-compose.canary.yml restart canary-gateway

echo "Traffic switched to canary mode 90/10: stable=90%, canary=10%."
