#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m dclink_lab demo --out outputs/demo
printf '%s\n' 'Open outputs/demo/report.html in your browser.'
