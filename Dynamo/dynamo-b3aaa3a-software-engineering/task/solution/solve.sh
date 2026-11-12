#!/bin/bash
set -euo pipefail

cp /solution/buckvalidate/__init__.py /app/buckvalidate/__init__.py
cp /solution/buckvalidate/raw.py /app/buckvalidate/raw.py
cp /solution/buckvalidate/metrics.py /app/buckvalidate/metrics.py
cp /solution/buckvalidate/cli.py /app/buckvalidate/cli.py

python3 -m buckvalidate.cli \
  --manifest /app/data/cases.csv \
  --requirements /app/data/requirements.json \
  --output-dir /app/output
