#!/bin/sh
set -eu
exec python3 -m buckvalidate.cli \
  --manifest /app/data/cases.csv \
  --requirements /app/data/requirements.json \
  --output-dir /app/output
