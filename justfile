run-local:
    PYTHONPATH=`pwd`:`pwd`/pygeoapi-swissgeo-extensions/providers PYGEOAPI_CONFIG=pygeoapi-config-minimal.yml PYGEOAPI_OPENAPI=pygeoapi-openapi.yml \
        uv run pygeoapi openapi generate pygeoapi-config-minimal.yml --output-file pygeoapi-openapi.yml
    PYTHONPATH=`pwd`:`pwd`/pygeoapi-swissgeo-extensions/providers PYGEOAPI_CONFIG=pygeoapi-config-minimal.yml PYGEOAPI_OPENAPI=pygeoapi-openapi.yml \
        uv run pygeoapi serve

# Start only OpenSearch (for local dev without full compose stack)
opensearch-up:
    docker compose up -d opensearch
    docker compose wait opensearch || true

# Index the swissgeo catalogue into the running OpenSearch
load-catalogue:
    FORCE=1 uv run python3 load-opensearch-catalogue.py

# Index the swissgeo catalogue into the running OpenSearch
load-sample-records:
    FORCE=1 uv run python3 load-sample-records.py


# Start OpenSearch + load catalogue, then run pygeoapi locally
run-local-os: opensearch-up load-catalogue run-local
