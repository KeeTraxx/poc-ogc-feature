#!/usr/bin/env python3
"""
Build meteoswiss-<PARAMETER>.geojson for all CSV files in the data directory.

Usage:
    python build_all_geojson.py [--data <data_dir>] [--out <output_dir>]
"""

import argparse
import json
import sys
from pathlib import Path

from build_geojson import build_geojson, extract_parameter_name

DEFAULT_DATA_DIR = Path(__file__).parent / "data"
DEFAULT_OUT_DIR = Path(__file__).parent.parent / "data"


def main():
    parser = argparse.ArgumentParser(description="Build GeoJSON for all meteoswiss parameters")
    parser.add_argument("--data", default=str(DEFAULT_DATA_DIR),
                        help=f"Directory with data CSVs (default: {DEFAULT_DATA_DIR})")
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR),
                        help=f"Output directory (default: {DEFAULT_OUT_DIR})")
    args = parser.parse_args()

    data_dir = Path(args.data)
    if not data_dir.is_dir():
        print(f"Error: data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {data_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {len(csv_files)} files -> {out_dir}\n")
    ok, failed = 0, []
    for csv_path in csv_files:
        param = extract_parameter_name(csv_path)
        try:
            out_path = build_geojson(csv_path, out_dir)
            n = len(json.loads(out_path.read_text())["features"])
            print(f"  {param:15s}  {n:4d} features  -> {out_path.name}")
            ok += 1
        except Exception as e:
            print(f"  {param:15s}  ERROR: {e}", file=sys.stderr)
            failed.append(param)

    print(f"\nDone: {ok} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed:", ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
