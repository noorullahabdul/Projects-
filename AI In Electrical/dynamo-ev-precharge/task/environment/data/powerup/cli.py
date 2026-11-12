"""Command-line entry point."""

import argparse
import sys

from .evaluate import inspect_cases


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        inspect_cases(args.index, args.out)
    except Exception as exc:  # starting scaffold intentionally incomplete
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
