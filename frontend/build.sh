#!/bin/sh
# Rebuilds app/web/dashboard.html from the pieces in this folder. Needs only Python 3.
set -e
cd "$(dirname "$0")"
python3 merge_build.py
python3 build_prod.py
