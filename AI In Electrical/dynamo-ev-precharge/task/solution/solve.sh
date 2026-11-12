#!/bin/sh
set -eu
rm -rf /app/powerup /app/result
cp -R /solution/powerup /app/powerup
mkdir -p /app/result
cd /app
python3 -m powerup.cli --index /app/input/index.json --out /app/result
