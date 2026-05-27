#!/bin/sh
set -e

cp infra/nginx/nginx-canary-50-50.conf infra/nginx/nginx.active.conf
docker compose -f infra/docker-compose.canary.yml restart canary-gateway

echo "Traffic switched to canary mode 50/50."
