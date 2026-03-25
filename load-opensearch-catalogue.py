#!/usr/bin/env python3
"""
Index the swissgeo-catalog from per-language item files into OpenSearch.

Reads from ITEMS_DIR (default: aws-s3-records/not_needed/swissgeo.catalog/items).
Each record ID has up to 4 files: <id>.de, <id>.en, <id>.fr, <id>.it
These are merged into a single OGC Records-style document with title_*/description_* fields.

Usage:
    python3 load-opensearch-catalogue.py
    OS_URL=http://localhost:9200 python3 load-opensearch-catalogue.py
    FORCE=1 python3 load-opensearch-catalogue.py   # delete and recreate index
    COLLECTIONS_DIR=aws-s3-records/oar/v0/collections python3 load-opensearch-catalogue.py

Requires: opensearch-py
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from opensearchpy import OpenSearch, helpers

OS_URL = os.environ.get("OS_URL", "http://localhost:9200")
INDEX = os.environ.get("OS_INDEX", "swissgeo-catalog")
ITEMS_DIR = Path(os.environ.get("ITEMS_DIR", "aws-s3-records/not_needed/swissgeo.catalog/items"))
COLLECTIONS_DIR = Path(os.environ.get("COLLECTIONS_DIR", "aws-s3-records/oar/v0/collections"))
FORCE = os.environ.get("FORCE", "").lower() in ("1", "true", "yes")

LANGUAGES = ["de", "en", "fr", "it"]

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id":       {"type": "keyword"},
            "type":     {"type": "keyword"},
            "geometry": {"type": "geo_shape"},
            "properties": {
                "properties": {
                    "type":            {"type": "keyword"},
                    "title_de":        {"type": "text"},
                    "title_en":        {"type": "text"},
                    "title_fr":        {"type": "text"},
                    "title_it":        {"type": "text"},
                    "description_de":  {"type": "text"},
                    "description_en":  {"type": "text"},
                    "description_fr":  {"type": "text"},
                    "description_it":  {"type": "text"},
                    "keywords":        {"type": "keyword"},
                    "preferredDistributionId": {"type": "keyword"},
                }
            }
        }
    }
}

JSONLD_CONTEXT = {
    "wms": "http://www.opengis.net/wms",
    "wmts": "http://www.opengis.net/wmts/1.0",
    "ows": "http://www.opengis.net/ows/1.1",
}

OGC_SCHEMA = "https://schemas.opengis.net/ogcapi/records/part1/1.0/openapi/schemas/recordGeoJSON.yaml"


WMS_SERVICE_ID = "wms-geoadminch"
WMTS_SERVICE_ID = "wmts-geoadminch"

WMS_LINK_TEMPLATE = {
    "uriTemplate": "https://wms.geo.admin.ch/?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0&FORMAT=text/xml&lang={lang}",
    "rel": "about",
    "title": "WMS Capabilities File",
    "type": "application/xml",
    "variables": {
        "lang": {
            "enum": ["de", "fr", "en", "it"],
            "type": "string",
            "default": "de",
            "description": "Language",
        }
    },
}

WMTS_LINK_TEMPLATE = {
    "uriTemplate": "https://wmts.geo.admin.ch/EPSG/{EPSG}/1.0.0/WMTSCapabilities.xml",
    "rel": "about",
    "title": "WMTS Capabilities File",
    "type": "application/vnd.ogc.wmts_xml",
    "variables": {
        "EPSG": {
            "enum": [2056, 21781, 4326],
            "type": "number",
            "format": "integer",
            "default": 2056,
            "description": "EPSG",
        }
    },
}


def load_link_templates(collections_dir: Path) -> dict[str, list[dict]]:
    """
    Scan collections dir and return a mapping of record_id -> list of linkTemplates.
    Only one language file per record is needed; we use .de if present, else any.
    """
    # Pick one file per record ID (prefer .de)
    by_id: dict[str, Path] = {}
    for path in collections_dir.iterdir():
        parts = path.name.rsplit(".", 1)
        if len(parts) == 2 and parts[1] in LANGUAGES:
            record_id, lang = parts
            if record_id not in by_id or lang == "de":
                by_id[record_id] = path

    result: dict[str, list[dict]] = {}
    for record_id, path in by_id.items():
        data = json.loads(path.read_text())
        templates = []
        for dist in data.get("records", []):
            dist_id = dist.get("id", "")
            layer_name = dist_id.rsplit(":", 1)[0] if ":" in dist_id else record_id
            service_hrefs = {
                link["href"].rsplit("/", 1)[-1]
                for link in dist.get("links", [])
                if link.get("rel") == "service"
            }
            if WMS_SERVICE_ID in service_hrefs:
                templates.append({**WMS_LINK_TEMPLATE, "wms:Name": layer_name})
            if WMTS_SERVICE_ID in service_hrefs:
                templates.append({**WMTS_LINK_TEMPLATE, "ows:Identifier": layer_name})
        if templates:
            result[record_id] = templates

    return result


def load_records(items_dir: Path, collections_dir: Path) -> list[dict]:
    """Merge per-language item files into OGC Records-shaped documents."""
    link_templates = load_link_templates(collections_dir)

    # Group files by record ID
    by_id: dict[str, dict[str, Path]] = defaultdict(dict)
    for path in items_dir.iterdir():
        parts = path.name.rsplit(".", 1)
        if len(parts) == 2 and parts[1] in LANGUAGES:
            record_id, lang = parts
            by_id[record_id][lang] = path

    records = []
    for record_id, lang_files in sorted(by_id.items()):
        lang_data: dict[str, dict] = {}
        for lang, path in lang_files.items():
            lang_data[lang] = json.loads(path.read_text())

        # Use the first available language as the base for structure
        base = lang_data.get("de") or lang_data.get("en") or next(iter(lang_data.values()))

        record = {
            "@context": JSONLD_CONTEXT,
            "$schema": OGC_SCHEMA,
            "id": record_id,
            "type": base["type"],
            "geometry": base["geometry"],
            "links": base.get("links", []),
            "properties": {
                **{k: v for k, v in base["properties"].items()
                   if k not in ("title", "description", "language")},
            },
        }
        if record_id in link_templates:
            record["linkTemplates"] = link_templates[record_id]

        for lang in LANGUAGES:
            if lang in lang_data:
                props = lang_data[lang]["properties"]
                record["properties"][f"title_{lang}"] = props.get("title", "")
                record["properties"][f"description_{lang}"] = props.get("description", "")

        records.append(record)

    return records


def main():
    print("=" * 60)
    print(" Indexing Swiss Geodata Catalogue into OpenSearch")
    print("=" * 60)
    print(f"Source:  {ITEMS_DIR}")
    print(f"Target:  {OS_URL}/{INDEX}")
    print()

    if not ITEMS_DIR.exists():
        print(f"ERROR: Items directory not found: {ITEMS_DIR}")
        sys.exit(1)

    client = OpenSearch(OS_URL, verify_certs=False)
    if not client.ping():
        print(f"ERROR: Cannot connect to OpenSearch at {OS_URL}")
        sys.exit(1)

    if client.indices.exists(index=INDEX):
        if FORCE:
            print(f"  FORCE=1 — deleting index '{INDEX}' ...")
            client.indices.delete(index=INDEX)
        else:
            count = client.count(index=INDEX)["count"]
            print(f"  Index '{INDEX}' already exists with {count} documents.")
            print("  Set FORCE=1 to delete and recreate. Exiting.")
            sys.exit(0)

    print(f"  Creating index '{INDEX}' ...", end=" ", flush=True)
    client.indices.create(index=INDEX, body=INDEX_MAPPING)
    print("done")

    print(f"  Loading records from {ITEMS_DIR} ...", end=" ", flush=True)
    records = load_records(ITEMS_DIR, COLLECTIONS_DIR)
    print(f"{len(records)} records")

    def _actions():
        for rec in records:
            yield {
                "_index": INDEX,
                "_id": rec["id"],
                "_source": rec,
            }

    print(f"  Indexing {len(records)} documents ...", end=" ", flush=True)
    ok, errors = helpers.bulk(client, _actions(), raise_on_error=False)
    if errors:
        print(f"\n  WARNING: {len(errors)} errors during indexing:")
        for e in errors[:5]:
            print(f"    {e}")
    print(f"{ok} indexed")
    print("\nDone!")


if __name__ == "__main__":
    main()
