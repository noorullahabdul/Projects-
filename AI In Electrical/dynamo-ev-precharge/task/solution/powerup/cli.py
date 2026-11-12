from __future__ import annotations

import argparse
import sys

from .evaluate import inspect_cases
from .io import FatalInputError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="powerup-inspector")
    parser.add_argument("--index", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        count, ok, faults, destination = inspect_cases(args.index, args.out)
    except FatalInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"cases={count} ok={ok} faults={faults} out={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
