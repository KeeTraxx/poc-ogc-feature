#!/usr/bin/env python3
"""
Load swissmaps-2026 shapefiles into PostGIS and OpenSearch.

Usage:
    python3 load-swissmaps.py
    PG_HOST=postgis OS_URL=http://opensearch:9200 python3 load-swissmaps.py

Requires: ogr2ogr (GDAL), psycopg2, requests
    pip install psycopg2-binary requests
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import psycopg2
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
SHP_DIR = SCRIPT_DIR / "swissmaps-2026"

# --- PostGIS settings ---
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_DB = os.environ.get("PG_DB", "geodata")
PG_USER = os.environ.get("PG_USER", "geo")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "geo")

# --- OpenSearch settings ---
OS_URL = os.environ.get("OS_URL", "http://localhost:9200")

DATASETS = ["cantons", "country", "districts", "lakes", "municipalities"]


def load_postgis(ds: str) -> int:
    """Load a shapefile into PostGIS using ogr2ogr, return feature count."""
    shp = SHP_DIR / f"{ds}.shp"
    table = f"swissmaps_{ds}"
    pg_conn = f"PG:host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASSWORD}"

    subprocess.run(
        [
            "ogr2ogr", "-f", "PostgreSQL", pg_conn, str(shp),
            "-nln", table,
            "-s_srs", "EPSG:2056",
            "-t_srs", "EPSG:4326",
            "-lco", "GEOMETRY_NAME=geom",
            "-lco", "FID=gid",
            "-lco", "PRECISION=NO",
            "-nlt", "PROMOTE_TO_MULTI",
            "-overwrite", "-q",
        ],
        check=True,
        env={**os.environ, "PGPASSWORD": PG_PASSWORD},
    )

    conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASSWORD)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_geom ON {table} USING GIST (geom)")
            conn.commit()
            cur.execute(f"SELECT count(*) FROM {table}")
            return cur.fetchone()[0]
    finally:
        conn.close()


def infer_mapping(properties: dict) -> dict:
    """Infer OpenSearch field mappings from a sample feature's properties."""
    field_defs = {}
    for k, v in properties.items():
        if isinstance(v, int):
            field_defs[k] = {"type": "integer"}
        elif isinstance(v, float):
            field_defs[k] = {"type": "float"}
        elif isinstance(v, str):
            field_defs[k] = {"type": "text", "fields": {"raw": {"type": "keyword"}}}
        else:
            field_defs[k] = {"type": "keyword"}
    return {
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "type": {"type": "keyword"},
                "geometry": {"type": "geo_shape"},
                "properties": {"type": "object", "properties": field_defs},
            }
        }
    }


def _dedup_ring(ring: list) -> list:
    """Remove duplicate consecutive coordinates from a coordinate ring."""
    if not ring:
        return ring
    result = [ring[0]]
    for coord in ring[1:]:
        if coord != result[-1]:
            result.append(coord)
    return result


def _dedup_coords(geometry: dict) -> dict:
    """Remove duplicate consecutive coordinates from a GeoJSON geometry."""
    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates")
    if coords is None:
        return geometry

    if geom_type == "Polygon":
        coords = [_dedup_ring(ring) for ring in coords]
    elif geom_type == "MultiPolygon":
        coords = [[_dedup_ring(ring) for ring in poly] for poly in coords]

    return {**geometry, "coordinates": coords}


def load_opensearch(ds: str, tmpdir: Path) -> tuple[int, int]:
    """Load a shapefile into OpenSearch via GeoJSON conversion.

    Returns (indexed_count, error_count).
    """
    shp = SHP_DIR / f"{ds}.shp"
    index = f"swissmaps-{ds}"
    geojson_path = tmpdir / f"{ds}.geojson"

    # Convert shapefile to GeoJSON (reprojected to WGS84, fix invalid geometries)
    subprocess.run(
        [
            "ogr2ogr", "-f", "GeoJSON", str(geojson_path), str(shp),
            "-s_srs", "EPSG:2056",
            "-t_srs", "EPSG:4326",
            "-makevalid",
            "-q",
        ],
        check=True,
    )

    with open(geojson_path) as f:
        fc = json.load(f)

    features = fc.get("features", [])
    if not features:
        return 0, 0

    # Remove duplicate consecutive coordinates (OpenSearch rejects these)
    for feat in features:
        feat["geometry"] = _dedup_coords(feat["geometry"])

    # Delete index if exists
    requests.delete(f"{OS_URL}/{index}", timeout=10)

    # Create index with mapping
    mapping = infer_mapping(features[0].get("properties", {}))
    resp = requests.put(f"{OS_URL}/{index}", json=mapping, timeout=10)
    resp.raise_for_status()

    # Build NDJSON bulk payload (use sequential ID to avoid duplicates)
    bulk_lines = []
    for i, feat in enumerate(features, start=1):
        action = json.dumps({"index": {"_index": index, "_id": str(i)}})
        doc = {
            "id": i,
            "type": "Feature",
            "properties": feat.get("properties", {}),
            "geometry": feat.get("geometry"),
        }
        bulk_lines.append(action)
        bulk_lines.append(json.dumps(doc))
    bulk_body = "\n".join(bulk_lines) + "\n"

    # Send bulk request
    resp = requests.post(
        f"{OS_URL}/_bulk",
        headers={"Content-Type": "application/x-ndjson"},
        data=bulk_body,
        timeout=120,
    )
    resp.raise_for_status()

    # Count errors from bulk response
    bulk_result = resp.json()
    errors = 0
    if bulk_result.get("errors"):
        for item in bulk_result.get("items", []):
            if item.get("index", {}).get("error"):
                errors += 1

    # Refresh and count
    requests.post(f"{OS_URL}/{index}/_refresh", timeout=10)
    count_resp = requests.get(f"{OS_URL}/{index}/_count", timeout=10)
    return count_resp.json().get("count", 0), errors


def main():
    print("=" * 50)
    print(" Loading swissmaps-2026 into PostGIS & OpenSearch")
    print("=" * 50)
    print(f"PostGIS:     {PG_HOST}:{PG_PORT}/{PG_DB}")
    print(f"OpenSearch:  {OS_URL}")
    print()

    # --- PostGIS ---
    print("--- PostGIS ---")
    for ds in DATASETS:
        print(f"  {ds} -> swissmaps_{ds} ... ", end="", flush=True)
        count = load_postgis(ds)
        print(f"{count} features")
    print()

    # --- OpenSearch ---
    print("--- OpenSearch ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        for ds in DATASETS:
            print(f"  {ds} -> swissmaps-{ds} ... ", end="", flush=True)
            count, errors = load_opensearch(ds, Path(tmpdir))
            msg = f"{count} features"
            if errors:
                msg += f" ({errors} skipped - invalid geometry)"
            print(msg)
    print()
    print("Done!")


if __name__ == "__main__":
    main()
