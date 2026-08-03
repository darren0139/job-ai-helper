#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
python scripts/run_project_checks.py --mode full --ci
