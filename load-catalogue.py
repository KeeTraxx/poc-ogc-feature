#!/usr/bin/env python3
"""
Write OGC API - Records catalogue entries for the Swiss geospatial datasets
served by this pygeoapi PoC into a TinyDB file consumed by TinyDBCatalogue.

Each record is a valid OGC API Records GeoJSON Feature:
  - top-level:  id, type, geometry
  - properties: externalId, recordCreated, recordUpdated, type, title,
                description, keywords, themes, links, contacts

Usage:
    python3 load-catalogue.py
    TINYDB_PATH=/path/to/swiss-geodata-catalogue.tinydb python3 load-catalogue.py
    FORCE=1 python3 load-catalogue.py   # overwrite existing file

Requires: tinydb
    pip install tinydb
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from tinydb import TinyDB, Query

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PATH = SCRIPT_DIR / "data" / "swiss-geodata-catalogue.tinydb"
TINYDB_PATH = Path(os.environ.get("TINYDB_PATH", str(DEFAULT_PATH)))
FORCE = os.environ.get("FORCE", "").lower() in ("1", "true", "yes")

# Switzerland bounding box (WGS84)
CH_BBOX = [5.96, 45.82, 10.49, 47.81]
CH_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [CH_BBOX[0], CH_BBOX[1]],
        [CH_BBOX[2], CH_BBOX[1]],
        [CH_BBOX[2], CH_BBOX[3]],
        [CH_BBOX[0], CH_BBOX[3]],
        [CH_BBOX[0], CH_BBOX[1]],
    ]],
}

SWISSTOPO_CONTACT = {
    "name": "swisstopo",
    "links": [{"href": "https://www.swisstopo.admin.ch", "type": "text/html"}],
    "roles": ["pointOfContact"],
}
METEOSWISS_CONTACT = {
    "name": "MeteoSwiss",
    "links": [{"href": "https://www.meteoswiss.admin.ch", "type": "text/html"}],
    "roles": ["pointOfContact"],
}

NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

PYGEOAPI_BASE = os.environ.get(
    "PYGEOAPI_BASE", "http://localhost:5000"
).rstrip("/")


def _record(
    record_id: str,
    title: str,
    description: str,
    keywords: list[str],
    themes: list[dict],
    links: list[dict],
    contacts: list[dict],
    geometry=None,
    record_type: str = "dataset",
) -> dict:
    """Build a single OGC API Records GeoJSON Feature."""
    return {
        "id": record_id,
        "type": "Feature",
        "geometry": geometry or CH_POLYGON,
        "properties": {
            "externalId": record_id,
            "recordCreated": NOW,
            "recordUpdated": NOW,
            "type": record_type,
            "title": title,
            "description": description,
            "keywords": keywords,
            "themes": themes,
            "links": links,
            "contacts": contacts,
        },
    }


def _collection_links(collection_id: str) -> list[dict]:
    """Standard OGC API Features links for a collection."""
    base = f"{PYGEOAPI_BASE}/collections/{collection_id}"
    return [
        {"href": base, "rel": "collection", "type": "application/json",
         "title": "OGC API collection"},
        {"href": f"{base}/items", "rel": "items", "type": "application/geo+json",
         "title": "Features"},
        {"href": "https://www.swisstopo.admin.ch", "rel": "about",
         "type": "text/html", "title": "swisstopo"},
    ]


def _meteoswiss_links(collection_id: str, param_code: str) -> list[dict]:
    base = f"{PYGEOAPI_BASE}/collections/{collection_id}"
    return [
        {"href": base, "rel": "collection", "type": "application/json",
         "title": "OGC API collection"},
        {"href": f"{base}/items", "rel": "items", "type": "application/geo+json",
         "title": "Features"},
        {"href": (
            "https://www.meteoswiss.admin.ch/services-and-publications/"
            "service/open-government-data.html"
         ), "rel": "about", "type": "text/html", "title": "MeteoSwiss Open Data"},
    ]


# ---------------------------------------------------------------------------
# Record definitions
# ---------------------------------------------------------------------------

RECORDS: list[dict] = [
    # -- Swiss administrative boundaries (PostGIS) --
    _record(
        record_id="cantons-postgis",
        title="Swiss Cantons (PostGIS)",
        description=(
            "Boundaries of the 26 Swiss cantons served from PostGIS "
            "in WGS84 (EPSG:4326)."
        ),
        keywords=["Switzerland", "cantons", "boundaries", "administrative", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("cantons-postgis"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="cantons-postgis-lv95",
        title="Swiss Cantons (PostGIS, LV95)",
        description=(
            "Boundaries of the 26 Swiss cantons stored in the Swiss national "
            "coordinate system LV95 (EPSG:2056)."
        ),
        keywords=["Switzerland", "cantons", "boundaries", "LV95", "EPSG:2056", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("cantons-postgis-lv95"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="country-postgis",
        title="Swiss Country Boundary (PostGIS)",
        description="Country boundary of Switzerland in WGS84 (EPSG:4326).",
        keywords=["Switzerland", "country boundary", "administrative", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("country-postgis"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="country-postgis-lv95",
        title="Swiss Country Boundary (PostGIS, LV95)",
        description="Country boundary of Switzerland stored in LV95 (EPSG:2056).",
        keywords=["Switzerland", "country boundary", "LV95", "EPSG:2056", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("country-postgis-lv95"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="districts-postgis",
        title="Swiss Districts (PostGIS)",
        description=(
            "Boundaries of the 144 Swiss districts in WGS84 (EPSG:4326)."
        ),
        keywords=["Switzerland", "districts", "boundaries", "administrative", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("districts-postgis"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="districts-postgis-lv95",
        title="Swiss Districts (PostGIS, LV95)",
        description=(
            "Boundaries of the 144 Swiss districts stored in LV95 (EPSG:2056)."
        ),
        keywords=["Switzerland", "districts", "boundaries", "LV95", "EPSG:2056", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("districts-postgis-lv95"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="municipalities-postgis",
        title="Swiss Municipalities (PostGIS)",
        description=(
            "Boundaries of all 2113 Swiss municipalities in WGS84 (EPSG:4326)."
        ),
        keywords=["Switzerland", "municipalities", "boundaries", "administrative", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("municipalities-postgis"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="municipalities-postgis-lv95",
        title="Swiss Municipalities (PostGIS, LV95)",
        description=(
            "Boundaries of all 2113 Swiss municipalities stored in LV95 (EPSG:2056)."
        ),
        keywords=["Switzerland", "municipalities", "boundaries", "LV95", "EPSG:2056", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("municipalities-postgis-lv95"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="lakes-postgis",
        title="Swiss Lakes (PostGIS)",
        description="Major Swiss lakes in WGS84 (EPSG:4326).",
        keywords=["Switzerland", "lakes", "hydrology", "water", "swisstopo"],
        themes=[{"concepts": [{"id": "hydrography"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("lakes-postgis"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="lakes-postgis-lv95",
        title="Swiss Lakes (PostGIS, LV95)",
        description="Major Swiss lakes stored in LV95 (EPSG:2056).",
        keywords=["Switzerland", "lakes", "hydrology", "LV95", "EPSG:2056", "swisstopo"],
        themes=[{"concepts": [{"id": "hydrography"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("lakes-postgis-lv95"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="swiss-places-geojson-postgis",
        title="Swiss Places (PostGIS)",
        description=(
            "Swiss cities, mountains, and lakes as named point/polygon features "
            "loaded from GeoJSON into PostGIS (WGS84)."
        ),
        keywords=["Switzerland", "places", "cities", "mountains", "named features", "swisstopo"],
        themes=[{"concepts": [{"id": "geographic-names"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("swiss-places-geojson-postgis"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="swiss-places-geojson-postgis-lv95",
        title="Swiss Places (PostGIS, LV95)",
        description=(
            "Swiss cities, mountains, and lakes as named features stored in LV95 (EPSG:2056)."
        ),
        keywords=["Switzerland", "places", "cities", "mountains", "LV95", "EPSG:2056", "swisstopo"],
        themes=[{"concepts": [{"id": "geographic-names"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("swiss-places-geojson-postgis-lv95"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    # -- OpenSearch collections --
    _record(
        record_id="cantons-opensearch",
        title="Swiss Cantons (OpenSearch)",
        description="Boundaries of the 26 Swiss cantons indexed in OpenSearch.",
        keywords=["Switzerland", "cantons", "boundaries", "OpenSearch", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("cantons-opensearch"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="country-opensearch",
        title="Swiss Country Boundary (OpenSearch)",
        description="Country boundary of Switzerland indexed in OpenSearch.",
        keywords=["Switzerland", "country boundary", "OpenSearch", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("country-opensearch"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="districts-opensearch",
        title="Swiss Districts (OpenSearch)",
        description="Boundaries of the 144 Swiss districts indexed in OpenSearch.",
        keywords=["Switzerland", "districts", "boundaries", "OpenSearch", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("districts-opensearch"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="lakes-opensearch",
        title="Swiss Lakes (OpenSearch)",
        description="Major Swiss lakes indexed in OpenSearch.",
        keywords=["Switzerland", "lakes", "hydrology", "OpenSearch", "swisstopo"],
        themes=[{"concepts": [{"id": "hydrography"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("lakes-opensearch"),
        contacts=[SWISSTOPO_CONTACT],
    ),
    _record(
        record_id="municipalities-opensearch",
        title="Swiss Municipalities (OpenSearch)",
        description="Boundaries of all 2113 Swiss municipalities indexed in OpenSearch.",
        keywords=["Switzerland", "municipalities", "boundaries", "OpenSearch", "swisstopo"],
        themes=[{"concepts": [{"id": "boundaries"}], "scheme": "https://inspire.ec.europa.eu/theme"}],
        links=_collection_links("municipalities-opensearch"),
        contacts=[SWISSTOPO_CONTACT],
    ),
]

# ---------------------------------------------------------------------------
# MeteoSwiss parameter records (one catalogue entry per parameter)
# ---------------------------------------------------------------------------

METEOSWISS_PARAMS = [
    ("tre200dx",  "Air temperature 2 m above ground; daily maximum", "temperature"),
    ("tre200dn",  "Air temperature 2 m above ground; daily minimum", "temperature"),
    ("tre200h0",  "Air temperature 2 m above ground; hourly mean", "temperature"),
    ("tre200px",  "Air temperature 2 m above ground; monthly maximum", "temperature"),
    ("tre200pn",  "Air temperature 2 m above ground; monthly minimum", "temperature"),
    ("treq10h0",  "Air temperature 2 m above ground; 10th percentile hourly", "temperature"),
    ("treq90h0",  "Air temperature 2 m above ground; 90th percentile hourly", "temperature"),
    ("rre150h0",  "Precipitation; hourly total", "precipitation"),
    ("rka150d0",  "Precipitation; daily total (climate normal)", "precipitation"),
    ("rka150p0",  "Precipitation; monthly total (climate normal)", "precipitation"),
    ("rre003i0",  "Precipitation; 3-minute intensity", "precipitation"),
    ("rp0003i0",  "Precipitation; 3-minute probability", "precipitation"),
    ("rreq10h0",  "Precipitation; 10th percentile hourly", "precipitation"),
    ("rreq10p0",  "Precipitation; 10th percentile monthly", "precipitation"),
    ("rreq90h0",  "Precipitation; 90th percentile hourly", "precipitation"),
    ("rreq90p0",  "Precipitation; 90th percentile monthly", "precipitation"),
    ("gre000h0",  "Global radiation; hourly mean", "radiation"),
    ("sre000h0",  "Sunshine duration; hourly total", "radiation"),
    ("dkl010h0",  "Diffuse radiation; hourly mean", "radiation"),
    ("fu3010h0",  "Wind speed; scalar mean 10 min at full hour", "wind"),
    ("fu3010h1",  "Wind speed; scalar mean 10 min before full hour", "wind"),
    ("fu3q10h0",  "Wind speed; 10th percentile hourly", "wind"),
    ("fu3q10h1",  "Wind speed; 10th percentile (before full hour)", "wind"),
    ("fu3q90h0",  "Wind speed; 90th percentile hourly", "wind"),
    ("fu3q90h1",  "Wind speed; 90th percentile (before full hour)", "wind"),
    ("zprfr0hs",  "Freezing level; hourly", "atmosphere"),
    ("ods000h0",  "Ozone; daily mean", "atmosphere"),
    ("jww003i0",  "Weather; present weather 3-minute", "atmosphere"),
    ("jp2000d0",  "Pressure; daily mean QFE", "atmosphere"),
    ("nprolohs",  "Precipitation profile; lower bound hourly", "precipitation"),
    ("npromths",  "Precipitation profile; middle bound hourly", "precipitation"),
    ("nprohihs",  "Precipitation profile; upper bound hourly", "precipitation"),
]

for code, description, theme_id in METEOSWISS_PARAMS:
    collection_id = f"meteoswiss-{code}"
    RECORDS.append(_record(
        record_id=collection_id,
        title=f"MeteoSwiss - {description}",
        description=(
            f"MeteoSwiss open government data: {description}. "
            "Point observations from Swiss weather stations."
        ),
        keywords=["MeteoSwiss", "Switzerland", "weather", "climate", "opendata",
                  code, theme_id],
        themes=[
            {"concepts": [{"id": theme_id}],
             "scheme": "https://inspire.ec.europa.eu/theme"},
            {"concepts": [{"id": "meteorological-geographical-features"}],
             "scheme": "https://inspire.ec.europa.eu/theme"},
        ],
        links=_meteoswiss_links(collection_id, code),
        contacts=[METEOSWISS_CONTACT],
    ))
    # OpenSearch variant
    os_collection_id = f"meteoswiss-{code}-opensearch"
    RECORDS.append(_record(
        record_id=os_collection_id,
        title=f"MeteoSwiss - {description} (OpenSearch)",
        description=(
            f"MeteoSwiss open government data: {description}. "
            "Point observations from Swiss weather stations, indexed in OpenSearch."
        ),
        keywords=["MeteoSwiss", "Switzerland", "weather", "climate", "opendata",
                  code, theme_id, "OpenSearch"],
        themes=[
            {"concepts": [{"id": theme_id}],
             "scheme": "https://inspire.ec.europa.eu/theme"},
        ],
        links=_meteoswiss_links(os_collection_id, code),
        contacts=[METEOSWISS_CONTACT],
    ))

# Combined MeteoSwiss OpenSearch
RECORDS.append(_record(
    record_id="meteoswiss-combined-opensearch",
    title="MeteoSwiss - All Parameters (OpenSearch)",
    description=(
        "All MeteoSwiss open government data parameters combined in a single "
        "OpenSearch wildcard index. Includes temperature, precipitation, "
        "wind, radiation, and atmospheric parameters."
    ),
    keywords=["MeteoSwiss", "Switzerland", "weather", "climate", "opendata",
              "OpenSearch", "combined"],
    themes=[
        {"concepts": [{"id": "meteorological-geographical-features"}],
         "scheme": "https://inspire.ec.europa.eu/theme"},
    ],
    links=_meteoswiss_links("meteoswiss-combined-opensearch", "*"),
    contacts=[METEOSWISS_CONTACT],
))


# ---------------------------------------------------------------------------
# TinyDB writing
# ---------------------------------------------------------------------------

def _add_anytext(record: dict) -> dict:
    """Add _metadata-anytext field that TinyDBCatalogueProvider uses for q= search."""
    props = record["properties"]
    props["_metadata-anytext"] = props.get("title", "") + props.get("description", "")
    return record


def main():
    print("=" * 55)
    print(" Writing OGC Records catalogue to TinyDB")
    print("=" * 55)
    print(f"Output:  {TINYDB_PATH}")
    print(f"Records: {len(RECORDS)}")
    print()

    if TINYDB_PATH.exists():
        if FORCE:
            print("  FORCE=1 set — overwriting existing file ...")
            TINYDB_PATH.unlink()
        else:
            db = TinyDB(str(TINYDB_PATH))
            count = len(db.all())
            db.close()
            print(f"  File already exists with {count} records. "
                  "Set FORCE=1 to overwrite. Exiting.")
            sys.exit(0)

    TINYDB_PATH.parent.mkdir(parents=True, exist_ok=True)

    db = TinyDB(str(TINYDB_PATH))
    try:
        print(f"  Inserting {len(RECORDS)} records ... ", end="", flush=True)
        for record in RECORDS:
            db.insert(_add_anytext(record))
        print(f"{len(RECORDS)} inserted")
    finally:
        db.close()

    print("\nDone!")
    print(f"\nCopy to container with:")
    print(f"  docker cp {TINYDB_PATH} poc-ogc-feature-pygeoapi-1:/pygeoapi/data/swiss-geodata-catalogue.tinydb")


if __name__ == "__main__":
    main()
