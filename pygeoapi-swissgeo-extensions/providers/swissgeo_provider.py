"""
SwissGeo OpenSearch catalogue provider for OGC API Records.

Extends OpenSearchCatalogueProvider with language-aware field selection:
when a locale is requested via the ``language`` kwarg, ``title`` and
``description`` are transparently swapped for their per-language variants
(``title_de``, ``title_fr``, …) before handing results back to pygeoapi.

Usage in pygeoapi-config.yml:
    providers:
      - type: record
        name: pygeoapi_swissgeo_extensions.providers.swissgeo_provider.SwissGeoProvider
        data: http://opensearch:9200/swissgeo-catalogue
        id_field: externalId
        time_field: recordCreated
        title_field: title
        languages:
          - en-US
          - de-CH
          - fr-CH
          - it-CH
"""

import logging

from flask import request as flask_request
from pygeoapi.provider.opensearch_ import OpenSearchCatalogueProvider

LOGGER = logging.getLogger(__name__)

# Maps ISO 639-1 / IETF primary subtag → field suffix stored in OpenSearch
_LANG_SUFFIX = {"de": "de", "en": "en", "fr": "fr", "it": "it"}


def _lang_suffix_from_request() -> str | None:
    """
    Read the raw ``lang`` query param from the current Flask request and
    return the matching field suffix, bypassing pygeoapi's broken
    single-string ``best_match`` call in ``get_plugin_locale``.

    Returns "en" if no lang param is present, unrecognised, or outside a request context.
    """
    try:
        lang_param = flask_request.args.get("lang", "")
    except RuntimeError:
        # Outside a request context (e.g. tests / OpenAPI generation)
        return "en"
    if not lang_param:
        return "en"
    # Primary language subtag: "fr-CH" → "fr", "de" → "de"
    primary = lang_param.split("-")[0].split("_")[0].lower()
    return _LANG_SUFFIX.get(primary, "en")


class SwissGeoProvider(OpenSearchCatalogueProvider):
    """
    OGC API Records provider backed by OpenSearch.

    Adds language-aware title/description field selection on top of
    the standard OpenSearchCatalogueProvider.
    """

    def __init__(self, provider_def):
        LOGGER.info("SwissGeoProvider.__init__ called")
        super().__init__(provider_def)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, offset=0, limit=10, resulttype="results", bbox=[],
              datetime_=None, properties=[], sortby=[], select_properties=[],
              skip_geometry=False, q=None, filterq=None, **kwargs):

        suffix = _lang_suffix_from_request()
        LOGGER.debug("SwissGeoProvider.query suffix=%s", suffix)

        result = super().query(
            offset=offset, limit=limit, resulttype=resulttype, bbox=bbox,
            datetime_=datetime_, properties=properties, sortby=sortby,
            select_properties=select_properties,
            skip_geometry=skip_geometry, q=q, filterq=filterq, **kwargs,
        )

        for feature in result.get("features", []):
            _apply_lang(feature["properties"], suffix)

        return result

    def get(self, identifier, **kwargs):
        suffix = _lang_suffix_from_request()
        LOGGER.debug("SwissGeoProvider.get identifier=%s suffix=%s",
                     identifier, suffix)

        result = super().get(identifier, **kwargs)

        if result:
            _apply_lang(result["properties"], suffix)

        return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _apply_lang(props: dict, suffix: str) -> None:
    """
    Overwrite ``title`` and ``description`` with their localised variants
    if the variant exists and is non-empty, then strip all per-lang fields.
    """
    for field in ("title", "description"):
        localised = props.get(f"{field}_{suffix}", "")
        if localised:
            props[field] = localised

    # Remove all per-language variants so the OGC response stays clean
    for lang in ("de", "en", "fr", "it"):
        for field in ("title", "description"):
            props.pop(f"{field}_{lang}", None)
