#!/usr/bin/env python3
"""
Build a meteoswiss-<PARAMETER_NAME>.geojson from a meteoswiss data CSV file.

Usage:
    python build_geojson.py <data_csv_file> [--out <output_dir>]

The data CSV filename must contain the parameter shortname, e.g.:
    vnut12.lssw.202603080800.tre200dn.csv
"""

import csv
import json
import argparse
import re
import sys
from pathlib import Path
from datetime import datetime, timezone


META_POINTS_CSV = Path(__file__).parent / "ogd-local-forecasting_meta_point.csv"
META_PARAMS_CSV = Path(__file__).parent / "ogd-local-forecasting_meta_parameters.csv"


def parse_date(date_str: str) -> str:
    """Convert YYYYMMDDHHMM to ISO 8601 UTC string."""
    dt = datetime.strptime(date_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%MZ")


def load_meta_points(path: Path) -> dict:
    """Load point metadata keyed by point_id (int)."""
    points = {}
    with open(path, newline="", encoding="iso-8859-1") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                pid = int(row["point_id"])
            except (ValueError, KeyError):
                continue
            points[pid] = row
    return points


def load_meta_parameters(path: Path) -> dict:
    """Load parameter metadata keyed by parameter_shortname."""
    params = {}
    with open(path, newline="", encoding="iso-8859-1") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = row.get("parameter_shortname", "").strip()
            if name:
                params[name] = row
    return params


def extract_parameter_name(csv_path: Path) -> str:
    """Extract parameter shortname from filename (last dot-separated segment before .csv)."""
    stem = csv_path.stem  # e.g. vnut12.lssw.202603080800.tre200dn
    parts = stem.split(".")
    return parts[-1]


def load_data(csv_path: Path, param_name: str) -> dict:
    """Load data CSV, returning dict: point_id -> list of {datetime, value}."""
    data = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                pid = int(row["point_id"])
            except (ValueError, KeyError):
                continue
            raw_date = row.get("Date", "").strip()
            raw_value = row.get(param_name, "").strip()
            if not raw_date:
                continue
            try:
                value = float(raw_value) if raw_value else None
            except ValueError:
                value = None
            entry = {"datetime": parse_date(raw_date), "value": value}
            data.setdefault(pid, []).append(entry)
    return data


def cast_value(value: str, datatype: str):
    if value is None or value == "":
        return None
    try:
        if datatype == "Integer":
            return int(float(value))
        return float(value)
    except (ValueError, TypeError):
        return value


def build_geojson(data_csv: Path, out_dir: Path) -> Path:
    param_name = extract_parameter_name(data_csv)

    meta_points = load_meta_points(META_POINTS_CSV)
    meta_params = load_meta_parameters(META_PARAMS_CSV)
    data = load_data(data_csv, param_name)

    param_meta = meta_params.get(param_name, {})
    datatype = param_meta.get("parameter_datatype", "Float")

    features = []
    for pid, values in data.items():
        point = meta_points.get(pid)
        if point is None:
            continue

        try:
            lon = float(point["point_coordinates_wgs84_lon"])
            lat = float(point["point_coordinates_wgs84_lat"])
        except (ValueError, KeyError):
            continue

        # Cast values to correct type
        typed_values = [
            {"datetime": v["datetime"], "value": cast_value(v["value"], datatype) if v["value"] is not None else None}
            for v in values
        ]

        postal_code = point.get("postal_code", "").strip()
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "point_id": pid,
                "point_type_id": int(point.get("point_type_id", 1)),
                "station_abbr": point.get("station_abbr", "").strip() or None,
                "postal_code": int(postal_code) if postal_code else None,
                "name": point.get("point_name", "").strip(),
                "height_masl": float(point["point_height_masl"]) if point.get("point_height_masl") else None,
                "lv95_east": float(point["point_coordinates_lv95_east"]) if point.get("point_coordinates_lv95_east") else None,
                "lv95_north": float(point["point_coordinates_lv95_north"]) if point.get("point_coordinates_lv95_north") else None,
                "parameter": param_name,
                "parameter_description": {
                    "de": param_meta.get("parameter_description_de", "").strip(),
                    "fr": param_meta.get("parameter_description_fr", "").strip(),
                    "it": param_meta.get("parameter_description_it", "").strip(),
                    "en": param_meta.get("parameter_description_en", "").strip(),
                },
                "parameter_unit": param_meta.get("parameter_unit", "").strip(),
                "parameter_group": {
                    "de": param_meta.get("parameter_group_de", "").strip(),
                    "fr": param_meta.get("parameter_group_fr", "").strip(),
                    "it": param_meta.get("parameter_group_it", "").strip(),
                    "en": param_meta.get("parameter_group_en", "").strip(),
                },
                "parameter_granularity": param_meta.get("parameter_granularity", "").strip(),
                "point_type": {
                    "de": point.get("point_type_de", "").strip(),
                    "fr": point.get("point_type_fr", "").strip(),
                    "it": point.get("point_type_it", "").strip(),
                    "en": point.get("point_type_en", "").strip(),
                },
                "values": typed_values,
            },
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    out_path = out_dir / f"meteoswiss-{param_name}.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build meteoswiss GeoJSON from data CSV")
    parser.add_argument("data_csv", help="Path to the meteoswiss data CSV file")
    parser.add_argument("--out", default=str(Path(__file__).parent.parent / "data"),
                        help="Output directory (default: ../data)")
    args = parser.parse_args()

    data_csv = Path(args.data_csv)
    if not data_csv.exists():
        print(f"Error: file not found: {data_csv}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = build_geojson(data_csv, out_dir)
    print(f"Written: {out_path}")
    print(f"  Features: {len(json.loads(out_path.read_text())['features'])}")


if __name__ == "__main__":
    main()
