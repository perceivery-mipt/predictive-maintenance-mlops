#!/bin/sh
set -e

cp infra/nginx/nginx-canary-100.conf infra/nginx/nginx.active.conf
docker compose -f infra/docker-compose.canary.yml restart canary-gateway

echo "Traffic switched to 100% canary."
