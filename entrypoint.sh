#!/bin/sh
# Starts as root only to make the mounted volume writable, then runs the app as a normal user.
# (Railway mounts volumes owned by root. With this script you do not need the RAILWAY_RUN_UID setting.)
DIR="${UPLOAD_DIR:-/data/uploads}"
mkdir -p "$DIR" 2>/dev/null
if [ "$(id -u)" = "0" ]; then
  chown -R appuser "$DIR" 2>/dev/null
  chown appuser "$(dirname "$DIR")" 2>/dev/null
  exec su -m -s /bin/sh -c "exec uvicorn app.server:app_factory --factory --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'" appuser
fi
exec uvicorn app.server:app_factory --factory --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
