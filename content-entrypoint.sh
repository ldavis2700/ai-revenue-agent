#!/bin/sh
set -eu
# Railway mounts new volumes as root. Only initialize the dedicated application dir.
mkdir -p /data/content
chown 10001:10001 /data/content
exec setpriv --reuid=10001 --regid=10001 --init-groups python3 /app/content_worker.py "$@"
