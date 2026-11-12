"""Verify a newly extracted delivery snapshot before editing its files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    manifest = root / "BUNDLE_MANIFEST.json"
    if not manifest.is_file():
        print("No delivery manifest. This may be a Git checkout rather than the original ZIP.")
        return 2
    data = json.loads(manifest.read_text(encoding="utf-8"))
    errors = []
    for item in data["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(item["path"] + ": missing or invalid path")
            continue
        if path.stat().st_size != item["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(item["path"] + ": changed bytes")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"PASS: {len(data['files'])} delivered files match their SHA-256 checksums.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
