# MapServer vs PyGeoAPI

---

## MapServer

- License: MIT-style (MIT/X)
- Technology: C/C++, CGI-based server (also FastCGI/WSGI)
- First released: 1994 (University of Minnesota)
- OGC standards: WMS, WFS, WCS, OGC API – Features
- Config: text-based Mapfile format

***

## PyGeoAPI

- License: MIT
- Technology: Python (Flask/Starlette), plugin-based architecture
- First released: 2018 (OSGeo community project)
- OGC standards: OGC API – Features, Records, Coverages, Tiles, Processes
- Config: YAML-based configuration

---

# On-paper comparison

---

## Backends MapServer

| Backend | Type | Notes |
|---|---|---|
| PostGIS | Vector (DB) | Primary spatial DB backend |
| Shapefile | Vector (File) | Native OGR support |
| GeoPackage | Vector/Raster (File) | Via GDAL/OGR |
| GeoTIFF | Raster (File) | Native GDAL support |
| Oracle Spatial | Vector (DB) | Enterprise option |
| WFS/WMS | Remote service | Cascading proxy |

***

### PyGeoAPI

| Backend | Type | Notes |
|---|---|---|
| PostGIS | Vector (DB) | Via `postgresql` provider |
| GeoPackage | Vector (File) | Via `OGR` provider |
| Shapefile | Vector (File) | Via `OGR` provider |
| Elasticsearch / OpenSearch | Vector (DB) | Full-text + geo search |
| MongoDB | Vector (DB) | GeoJSON-native |
| CSV / GeoJSON | Vector (File) | Lightweight file providers |
| GDAL/OGR | Vector/Raster | Generic driver for 80+ formats |


---

## Features

| Feature | MapServer | PyGeoAPI |
|---|---|---|
| OGC API – Features | yes | yes |
| WMS / WFS 1.x | yes | no |
| Raster serving | yes | limited |
| Map rendering / cartography | yes | no |
| Tiling (WMTS / OGC Tiles) | yes (via MapCache) | yes (native) |
| OGC API – Processes | no | yes |
| OGC API – Records | no | yes |
| Plugin / provider system | limited | yes |
| Admin / management UI | no | no |
| OpenAPI / Swagger docs | no | yes (built-in) |
| Docker-friendly | yes | yes |

---

## Development (last year)

### MapServer

Releases 8.4.0, 8.4.1, 8.6.0 in 2025. **18 contributors** (Jan 2025 – Mar 2026). ★ 1179 GitHub stars.

- OGC API – Features: extended `vendorSpecificParameters` support in OpenAPI docs and improved PostGIS extent compatibility
- New `CLASS FALLBACK` parameter for default rendering when no class matches a feature
- PCRE2 regex library support replacing legacy PCRE
- New `RASTERLABEL` connection type + 4 new composite blending operations
- Security patch release (8.4.1 / CVE); branches 8.0 and 8.2 dropped

---

## Development (last year)

### PyGeoAPI

Releases 0.19–0.23 in 2025–2026. **36 contributors** (Jan 2025 – Mar 2026). ★ 592 GitHub stars.

- OGC API – Pub/Sub Workflow support (draft spec, 0.23.0) for event-driven geospatial publishing
- STAC API support (0.22.0) for Earth Observation / remote sensing data
- New providers: MySQL, PostgreSQL Tiles, SensorThings EDR, OpenSearch (0.19–0.21)
- Reworked limits configuration (RFC5); stable branch model introduced (0.20.0)
- Python 3.12, rootless Docker image, CRS normalization, externalized TileMatrixSets (0.22.0)

---

# DEMO

---
