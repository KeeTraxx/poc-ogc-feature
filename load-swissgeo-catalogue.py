#!/usr/bin/env python3
"""
Populate TinyDB with records from the AWS S3 OAR collections (swissgeo.catalog.*).

Reads all four language variants (de/en/fr/it) from the swissgeo.catalog.* files
and merges them into a single record per dataset, storing translated titles and
descriptions under language-keyed sub-fields.

Each TinyDB record is a valid OGC API Records GeoJSON Feature:
  - top-level:  id, type, geometry
  - properties: externalId, recordCreated, recordUpdated, type, title,
                description, keywords, themes, links, contacts,
                title_de/title_en/title_fr/title_it,
                description_de/description_en/description_fr/description_it,
                languages, _metadata-anytext

Usage:
    python3 load-swissgeo-catalogue.py
    COLLECTIONS_DIR=/path/to/collections python3 load-swissgeo-catalogue.py
    TINYDB_PATH=/path/to/output.tinydb python3 load-swissgeo-catalogue.py
    FORCE=1 python3 load-swissgeo-catalogue.py   # overwrite existing file

Requires: tinydb
    pip install tinydb
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from tinydb import TinyDB

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_COLLECTIONS_DIR = SCRIPT_DIR / "aws-s3-records" / "oar" / "v0" / "collections"
COLLECTIONS_DIR = Path(os.environ.get("COLLECTIONS_DIR", str(DEFAULT_COLLECTIONS_DIR)))

DEFAULT_TINYDB_PATH = SCRIPT_DIR / "data" / "swissgeo-catalogue.tinydb"
TINYDB_PATH = Path(os.environ.get("TINYDB_PATH", str(DEFAULT_TINYDB_PATH)))

FORCE = os.environ.get("FORCE", "").lower() in ("1", "true", "yes")

LANGUAGES = ["de", "en", "fr", "it"]

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_catalog(lang: str) -> dict[str, dict]:
    """Load swissgeo.catalog.<lang> and return a dict keyed by record id."""
    path = COLLECTIONS_DIR / f"swissgeo.catalog.{lang}"
    if not path.exists():
        raise FileNotFoundError(f"Catalog file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {rec["id"]: rec for rec in data.get("records", [])}


def build_record(record_id: str, by_lang: dict[str, dict]) -> dict:
    """Merge language variants into a single TinyDB record."""
    # Use English as the default, fall back to German, then whatever is available
    base = by_lang.get("en") or by_lang.get("de") or next(iter(by_lang.values()))
    props = base.get("properties", {})

    # Collect per-language titles and descriptions
    titles = {}
    descriptions = {}
    for lang, rec in by_lang.items():
        lprops = rec.get("properties", {})
        titles[lang] = lprops.get("title", "")
        descriptions[lang] = lprops.get("description", "")

    # Default title/description (English preferred)
    title = titles.get("en") or titles.get("de") or next(iter(titles.values()), "")
    description = (
        descriptions.get("en") or descriptions.get("de")
        or next(iter(descriptions.values()), "")
    )

    # Contacts: normalise to list of dicts with name/roles
    raw_contacts = props.get("contacts", [])
    contacts = []
    for c in raw_contacts:
        contacts.append({
            "name": c.get("organisation", c.get("name", "")),
            "roles": [c["role"]] if "role" in c else c.get("roles", []),
        })

    # Keywords: derive from the record id components (agency prefix + dataset name)
    parts = record_id.split(".")
    keywords = list(dict.fromkeys(
        [p.replace("-", " ").replace("_", " ") for p in parts if p]
        + ["Switzerland", "swisstopo", "geodata"]
    ))

    # Links from the base record (language-neutral subset)
    source_links = base.get("links", [])
    links = [
        lnk for lnk in source_links
        if lnk.get("rel") not in ("self", "collection")
        and "services.dev.sgdi.tech" not in lnk.get("href", "")
    ]

    # Languages metadata
    languages = props.get("languages", [])

    anytext = " ".join(filter(None, [title, description] + list(titles.values()) + list(descriptions.values())))

    return {
        "id": record_id,
        "type": "Feature",
        "geometry": base.get("geometry"),
        "properties": {
            "externalId": record_id,
            "recordCreated": NOW,
            "recordUpdated": NOW,
            "type": props.get("type", "dataset").lower(),
            "title": title,
            "description": description,
            **{f"title_{lang}": titles.get(lang, "") for lang in LANGUAGES},
            **{f"description_{lang}": descriptions.get(lang, "") for lang in LANGUAGES},
            "keywords": keywords,
            "themes": [
                {"concepts": [{"id": "geodata"}],
                 "scheme": "https://inspire.ec.europa.eu/theme"}
            ],
            "links": links,
            "contacts": contacts,
            "languages": languages,
            "_metadata-anytext": anytext,
        },
    }


def main():
    print("=" * 60)
    print(" Loading Swiss Geodata Catalogue from OAR collections")
    print("=" * 60)
    print(f"Source:  {COLLECTIONS_DIR}")
    print(f"Output:  {TINYDB_PATH}")
    print()

    if TINYDB_PATH.exists():
        if FORCE:
            print("  FORCE=1 — overwriting existing file ...")
            TINYDB_PATH.unlink()
        else:
            db = TinyDB(str(TINYDB_PATH))
            count = len(db.all())
            db.close()
            print(f"  File already exists with {count} records. "
                  "Set FORCE=1 to overwrite. Exiting.")
            sys.exit(0)

    print("  Loading language catalogs ...", end=" ", flush=True)
    catalogs: dict[str, dict[str, dict]] = {}
    for lang in LANGUAGES:
        catalogs[lang] = load_catalog(lang)
    print("done")

    # Collect all record ids across all languages
    all_ids: set[str] = set()
    for lang_records in catalogs.values():
        all_ids.update(lang_records.keys())

    print(f"  Unique dataset records: {len(all_ids)}")
    print(f"  Building merged records ...", end=" ", flush=True)

    records = []
    for record_id in sorted(all_ids):
        by_lang = {
            lang: catalogs[lang][record_id]
            for lang in LANGUAGES
            if record_id in catalogs[lang]
        }
        records.append(build_record(record_id, by_lang))

    print("done")

    TINYDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    db = TinyDB(str(TINYDB_PATH))
    try:
        print(f"  Inserting {len(records)} records ... ", end="", flush=True)
        for record in records:
            db.insert(record)
        print(f"{len(records)} inserted")
    finally:
        db.close()

    print("\nDone!")
    print(f"\nCopy to container with:")
    print(f"  docker cp {TINYDB_PATH} poc-ogc-feature-pygeoapi-1:/pygeoapi/data/swissgeo-catalogue.tinydb")


if __name__ == "__main__":
    main()
