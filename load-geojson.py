#!/usr/bin/env python3
"""
Load all GeoJSON files from data/ into PostGIS and OpenSearch.

Usage:
    python3 load-geojson.py
    PG_HOST=postgis OS_URL=http://opensearch:9200 python3 load-geojson.py

Requires: psycopg2-binary requests
    pip install psycopg2-binary requests
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

# --- PostGIS settings ---
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = os.environ.get("PG_PORT", "5432")
PG_DB = os.environ.get("PG_DB", "geodata")
PG_USER = os.environ.get("PG_USER", "geo")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "geo")

# --- OpenSearch settings ---
OS_URL = os.environ.get("OS_URL", "http://localhost:9200").rstrip("/")


def pg_connect():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


def _sql_type(value):
    """Map a Python/JSON value to a PostgreSQL column type."""
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "DOUBLE PRECISION"
    return "TEXT"


def _infer_columns(features: list[dict]) -> list[tuple[str, str]]:
    """Scan features to build (column_name, sql_type) list.

    Uses the first non-None value for each key to determine the type.
    """
    type_map: dict[str, str] = {}
    seen_keys: list[str] = []

    for feat in features:
        props = feat.get("properties", {})
        for k, v in props.items():
            if k not in type_map:
                seen_keys.append(k)
                type_map[k] = "TEXT"  # default
            if v is not None and type_map[k] == "TEXT":
                type_map[k] = _sql_type(v)
        # Stop scanning once every key has a non-None sample
        if all(type_map[k] != "TEXT" or k in type_map for k in seen_keys):
            all_resolved = True
            for feat2 in features:
                props2 = feat2.get("properties", {})
                for k2 in seen_keys:
                    if type_map[k2] == "TEXT" and props2.get(k2) is not None:
                        type_map[k2] = _sql_type(props2[k2])
            break

    return [(k, type_map[k]) for k in seen_keys]


def _safe_table(name: str) -> str:
    """Convert a dataset name to a valid SQL table name."""
    return "geojson_" + name.replace("-", "_")


def load_postgis(name: str, features: list[dict]) -> int:
    """Load features into PostGIS with flat columns. Returns row count."""
    table = _safe_table(name)
    columns = _infer_columns(features)

    conn = pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

            col_defs = ",\n                    ".join(
                f'"{col}" {sql_type}' for col, sql_type in columns
            )
            cur.execute(f"""
                CREATE TABLE {table} (
                    gid SERIAL PRIMARY KEY,
                    {col_defs},
                    geom GEOMETRY(Geometry, 4326)
                )
            """)

            col_names = [f'"{c}"' for c, _ in columns]
            placeholders = ["%s"] * len(columns) + [
                "ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)"
            ]
            insert_sql = (
                f"INSERT INTO {table} ({', '.join(col_names)}, geom) "
                f"VALUES ({', '.join(placeholders)})"
            )

            for feat in features:
                props = feat.get("properties", {})
                values = [props.get(col) for col, _ in columns]
                values.append(json.dumps(feat["geometry"]))
                cur.execute(insert_sql, values)

            cur.execute(
                f"CREATE INDEX idx_{table}_geom ON {table} USING GIST (geom)"
            )
            conn.commit()

            cur.execute(f"SELECT count(*) FROM {table}")
            return cur.fetchone()[0]
    finally:
        conn.close()


def _dedup_ring(ring: list) -> list:
    if not ring:
        return ring
    result = [ring[0]]
    for coord in ring[1:]:
        if coord != result[-1]:
            result.append(coord)
    return result


def _dedup_coords(geometry: dict) -> dict:
    """Remove duplicate consecutive coordinates (OpenSearch rejects these)."""
    geom_type = geometry.get("type", "")
    coords = geometry.get("coordinates")
    if coords is None:
        return geometry

    if geom_type == "Polygon":
        coords = [_dedup_ring(ring) for ring in coords]
    elif geom_type == "MultiPolygon":
        coords = [[_dedup_ring(ring) for ring in poly] for poly in coords]

    return {**geometry, "coordinates": coords}


def infer_mapping(properties: dict) -> dict:
    """Infer OpenSearch field mappings from a sample feature's properties."""
    field_defs = {}
    for k, v in properties.items():
        if isinstance(v, bool):
            field_defs[k] = {"type": "boolean"}
        elif isinstance(v, int):
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


def load_opensearch(name: str, features: list[dict]) -> tuple[int, int]:
    """Load features into OpenSearch index `geojson-{name}`.

    Returns (indexed_count, error_count).
    """
    index = f"geojson-{name}"

    if not features:
        return 0, 0

    for feat in features:
        feat["geometry"] = _dedup_coords(feat["geometry"])

    # Recreate index
    requests.delete(f"{OS_URL}/{index}", timeout=10)
    resp = requests.put(
        f"{OS_URL}/{index}",
        json=infer_mapping(features[0].get("properties", {})),
        timeout=10,
    )
    resp.raise_for_status()

    # Bulk index
    bulk_lines = []
    for i, feat in enumerate(features, start=1):
        bulk_lines.append(json.dumps({"index": {"_index": index, "_id": str(i)}}))
        bulk_lines.append(json.dumps({
            "id": i,
            "type": "Feature",
            "properties": feat.get("properties", {}),
            "geometry": feat.get("geometry"),
        }))
    bulk_body = "\n".join(bulk_lines) + "\n"

    resp = requests.post(
        f"{OS_URL}/_bulk",
        headers={"Content-Type": "application/x-ndjson"},
        data=bulk_body,
        timeout=120,
    )
    resp.raise_for_status()

    bulk_result = resp.json()
    errors = 0
    if bulk_result.get("errors"):
        for item in bulk_result.get("items", []):
            if item.get("index", {}).get("error"):
                errors += 1

    requests.post(f"{OS_URL}/{index}/_refresh", timeout=10)
    count_resp = requests.get(f"{OS_URL}/{index}/_count", timeout=10)
    return count_resp.json().get("count", 0), errors


def main():
    geojson_files = sorted(DATA_DIR.glob("*.geojson"))
    if not geojson_files:
        print(f"No .geojson files found in {DATA_DIR}")
        sys.exit(1)

    print("=" * 55)
    print(" Loading GeoJSON files into PostGIS & OpenSearch")
    print("=" * 55)
    print(f"Data dir:    {DATA_DIR}")
    print(f"PostGIS:     {PG_HOST}:{PG_PORT}/{PG_DB}")
    print(f"OpenSearch:  {OS_URL}")
    print(f"Files:       {len(geojson_files)}")
    print()

    for path in geojson_files:
        name = path.stem

        with open(path) as f:
            fc = json.load(f)
        features = fc.get("features", [])
        if not features:
            print(f"  {name}: empty, skipping")
            continue

        table = _safe_table(name)

        # PostGIS
        print(f"  {name} -> PostGIS ({table}) ... ", end="", flush=True)
        count = load_postgis(name, features)
        print(f"{count} features")

        # OpenSearch
        print(f"  {name} -> OpenSearch (geojson-{name}) ... ", end="", flush=True)
        indexed, errors = load_opensearch(name, features)
        msg = f"{indexed} features"
        if errors:
            msg += f" ({errors} skipped - invalid geometry)"
        print(msg)

        print()

    print("Done!")


if __name__ == "__main__":
    main()
