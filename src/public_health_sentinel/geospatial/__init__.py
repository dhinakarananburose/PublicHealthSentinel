"""Geospatial Intelligence and Regional Surveillance Module for PublicHealthSentinel."""

from public_health_sentinel.geospatial.registry import (
    SYNTHETIC_REGIONS,
    get_region_metadata,
    get_regions_geojson,
    list_all_regions,
    normalize_region_id,
    validate_coordinates,
)
from public_health_sentinel.geospatial.service import (
    compute_geospatial_lagged_correlation,
    get_geospatial_mobility_overlay,
    get_geospatial_timeseries,
    get_regional_surveillance_summary,
)

__all__ = [
    "SYNTHETIC_REGIONS",
    "get_region_metadata",
    "get_regions_geojson",
    "list_all_regions",
    "normalize_region_id",
    "validate_coordinates",
    "get_regional_surveillance_summary",
    "get_geospatial_timeseries",
    "get_geospatial_mobility_overlay",
    "compute_geospatial_lagged_correlation",
]
