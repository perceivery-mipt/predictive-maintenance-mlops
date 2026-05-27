#!/bin/sh
set -e

cp infra/nginx/nginx-rollback.conf infra/nginx/nginx.active.conf
docker compose -f infra/docker-compose.canary.yml restart canary-gateway

echo "Rollback completed: traffic switched back to 100% stable."
