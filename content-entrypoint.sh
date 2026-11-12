#!/bin/sh
set -eu
# Railway mounts new volumes as root. Only initialize the dedicated application dir.
mkdir -p /data/content
chown 10001:10001 /data/content
if [ "${APEX_REVENUE_WORKER_ENABLED:-false}" = "true" ] && [ "$#" -eq 0 ]; then
    mkdir -p /data/revenue
    chown 10001:10001 /data/revenue
    export REVENUE_DB_PATH=/data/revenue/revenue_agent.db
    exec setpriv --reuid=10001 --regid=10001 --init-groups python3 /app/runtime_supervisor.py
fi
exec setpriv --reuid=10001 --regid=10001 --init-groups python3 /app/content_worker.py "$@"
