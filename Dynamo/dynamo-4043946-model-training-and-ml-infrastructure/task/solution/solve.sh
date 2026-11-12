#!/bin/bash
set -euo pipefail
cp /solution/trainer_fixed.py /app/trainer.py
chmod +x /app/trainer.py
rm -rf /app/out
mkdir -p /app/out
python3 /app/trainer.py --config /app/config.json --out /app/out
