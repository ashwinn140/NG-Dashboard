#!/bin/sh
# Rebuild the deployed page from the current production sources.
set -e
cd "$(dirname "$0")"
python3 build_prod.py
