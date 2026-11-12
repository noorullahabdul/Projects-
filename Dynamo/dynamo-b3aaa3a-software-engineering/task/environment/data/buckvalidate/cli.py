"""Command-line entry point for the buck waveform validator."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate ngspice buck-converter traces")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    build_parser().parse_args()
    raise NotImplementedError("implement the validation workflow")


if __name__ == "__main__":
    raise SystemExit(main())
