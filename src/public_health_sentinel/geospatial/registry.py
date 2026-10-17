"""Registry of documented synthetic geographic regions for PublicHealthSentinel.

SCIENTIFIC INTEGRITY RULE:
The underlying surveillance records in PublicHealthSentinel contain abstract region
identifiers (REGION_A through REGION_E). To enable spatial algorithms, GIS testing,
and choropleth mapping without fabricating real-world municipal boundaries, this
registry defines documented synthetic geographic coordinates and regional polygon
geometries. All items are permanently marked with is_synthetic_geography=True.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from public_health_sentinel.geospatial.schemas import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeoJSONGeometry,
    SyntheticRegionMetadata,
)

# Documented Synthetic Geographic Sectors
SYNTHETIC_REGIONS: Dict[str, SyntheticRegionMetadata] = {
    "REGION_A": SyntheticRegionMetadata(
        region_id="REGION_A",
        name="Synthetic Surveillance Sector Alpha (Northwest)",
        code="SEC-A",
        population=250_000,
        facility_count=8,
        centroid_lat=42.50,
        centroid_lon=-73.50,
        bounding_box=(-74.0, 42.0, -73.0, 43.0),
        is_synthetic_geography=True,
    ),
    "REGION_B": SyntheticRegionMetadata(
        region_id="REGION_B",
        name="Synthetic Surveillance Sector Beta (Northeast)",
        code="SEC-B",
        population=500_000,
        facility_count=15,
        centroid_lat=42.50,
        centroid_lon=-71.50,
        bounding_box=(-72.0, 42.0, -71.0, 43.0),
        is_synthetic_geography=True,
    ),
    "REGION_C": SyntheticRegionMetadata(
        region_id="REGION_C",
        name="Synthetic Surveillance Sector Gamma (Central)",
        code="SEC-C",
        population=150_000,
        facility_count=5,
        centroid_lat=41.50,
        centroid_lon=-72.50,
        bounding_box=(-73.0, 41.0, -72.0, 42.0),
        is_synthetic_geography=True,
    ),
    "REGION_D": SyntheticRegionMetadata(
        region_id="REGION_D",
        name="Synthetic Surveillance Sector Delta (Southwest)",
        code="SEC-D",
        population=750_000,
        facility_count=22,
        centroid_lat=40.50,
        centroid_lon=-73.50,
        bounding_box=(-74.0, 40.0, -73.0, 41.0),
        is_synthetic_geography=True,
    ),
    "REGION_E": SyntheticRegionMetadata(
        region_id="REGION_E",
        name="Synthetic Surveillance Sector Epsilon (Southeast)",
        code="SEC-E",
        population=350_000,
        facility_count=11,
        centroid_lat=40.50,
        centroid_lon=-71.50,
        bounding_box=(-72.0, 40.0, -71.0, 41.0),
        is_synthetic_geography=True,
    ),
}

# Synthetic GeoJSON Polygon definitions [ [ [lon, lat], ... ] ]
SYNTHETIC_POLYGONS: Dict[str, List[List[float]]] = {
    "REGION_A": [
        [-74.0, 42.0],
        [-74.0, 43.0],
        [-73.0, 43.0],
        [-73.0, 42.0],
        [-74.0, 42.0],
    ],
    "REGION_B": [
        [-72.0, 42.0],
        [-72.0, 43.0],
        [-71.0, 43.0],
        [-71.0, 42.0],
        [-72.0, 42.0],
    ],
    "REGION_C": [
        [-73.0, 41.0],
        [-73.0, 42.0],
        [-72.0, 42.0],
        [-72.0, 41.0],
        [-73.0, 41.0],
    ],
    "REGION_D": [
        [-74.0, 40.0],
        [-74.0, 41.0],
        [-73.0, 41.0],
        [-73.0, 40.0],
        [-74.0, 40.0],
    ],
    "REGION_E": [
        [-72.0, 40.0],
        [-72.0, 41.0],
        [-71.0, 41.0],
        [-71.0, 40.0],
        [-72.0, 40.0],
    ],
}


def normalize_region_id(raw_id: str) -> str:
    """Normalize input region string to uppercase canonical format."""
    cleaned = raw_id.strip().upper()
    if not cleaned.startswith("REGION_") and len(cleaned) == 1 and cleaned in "ABCDE":
        return f"REGION_{cleaned}"
    return cleaned


def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate latitude and longitude ranges (-90 to 90, -180 to 180)."""
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False
    if not (-90.0 <= lat <= 90.0):
        return False
    if not (-180.0 <= lon <= 180.0):
        return False
    return True


def get_region_metadata(region_id: str) -> Optional[SyntheticRegionMetadata]:
    """Retrieve metadata for a specified region ID."""
    norm_id = normalize_region_id(region_id)
    return SYNTHETIC_REGIONS.get(norm_id)


def list_all_regions() -> List[SyntheticRegionMetadata]:
    """List metadata for all standard synthetic surveillance regions."""
    return list(SYNTHETIC_REGIONS.values())


def get_regions_geojson() -> GeoJSONFeatureCollection:
    """Generate GeoJSON FeatureCollection representing the synthetic regional grid."""
    features = []
    for region_id, meta in SYNTHETIC_REGIONS.items():
        coords = SYNTHETIC_POLYGONS[region_id]
        feature = GeoJSONFeature(
            id=region_id,
            properties={
                "region_id": meta.region_id,
                "name": meta.name,
                "code": meta.code,
                "population": meta.population,
                "facility_count": meta.facility_count,
                "centroid_lat": meta.centroid_lat,
                "centroid_lon": meta.centroid_lon,
                "is_synthetic_geography": True,
            },
            geometry=GeoJSONGeometry(
                type="Polygon",
                coordinates=[coords],
            ),
        )
        features.append(feature)

    return GeoJSONFeatureCollection(features=features)
