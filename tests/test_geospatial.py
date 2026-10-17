"""Unit and API integration tests for Phase 7 Geospatial Intelligence."""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from public_health_sentinel.api import app
from public_health_sentinel.db.session import get_db_session
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


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


def test_registry_synthetic_regions() -> None:
    """Verify registry exposes all 5 synthetic regions with documented coordinates."""
    regions = list_all_regions()
    assert len(regions) == 5
    region_ids = {r.region_id for r in regions}
    assert region_ids == {"REGION_A", "REGION_B", "REGION_C", "REGION_D", "REGION_E"}

    for r in regions:
        assert r.is_synthetic_geography is True
        assert "SYNTHETIC-GEOGRAPHY NOTICE" in r.synthetic_disclaimer
        assert r.population > 0
        assert r.facility_count > 0
        assert validate_coordinates(r.centroid_lat, r.centroid_lon) is True
        min_lon, min_lat, max_lon, max_lat = r.bounding_box
        assert min_lon < max_lon
        assert min_lat < max_lat


def test_registry_coordinate_validation() -> None:
    """Test coordinate range validator (-90 to 90 lat, -180 to 180 lon)."""
    assert validate_coordinates(42.5, -73.5) is True
    assert validate_coordinates(-90.0, 180.0) is True
    assert validate_coordinates(91.0, 0.0) is False
    assert validate_coordinates(-91.0, 0.0) is False
    assert validate_coordinates(0.0, 181.0) is False
    assert validate_coordinates(0.0, -181.0) is False
    assert validate_coordinates("invalid", -73.5) is False  # type: ignore[arg-type]


def test_registry_region_normalization() -> None:
    """Test region ID normalization and matching."""
    assert normalize_region_id("region_a") == "REGION_A"
    assert normalize_region_id("REGION_B") == "REGION_B"
    assert normalize_region_id("c") == "REGION_C"
    assert normalize_region_id("  REGION_D  ") == "REGION_D"

    assert get_region_metadata("region_a") is not None
    assert get_region_metadata("NONEXISTENT") is None


def test_registry_geojson_feature_collection() -> None:
    """Verify RFC 7946 GeoJSON output formatting and structure."""
    fc = get_regions_geojson()
    assert fc.type == "FeatureCollection"
    assert len(fc.features) == 5
    for f in fc.features:
        assert f.type == "Feature"
        assert f.geometry.type == "Polygon"
        assert len(f.geometry.coordinates[0]) >= 4  # Closed polygon
        assert f.properties["is_synthetic_geography"] is True


def test_service_regional_surveillance_summary() -> None:
    """Test regional surveillance count aggregation and anomaly summarization."""
    session = next(get_db_session())
    try:
        summary = get_regional_surveillance_summary(session)
        assert summary.total_regions == 5
        assert summary.total_surveillance_cases > 0
        assert summary.total_anomalies_flagged == 64
        assert len(summary.regions) == 5

        # Check crude rates are non-zero and populations match
        for r in summary.regions:
            assert r.population in {150_000, 250_000, 350_000, 500_000, 750_000}
            assert r.crude_rate_per_100k is not None
            assert r.crude_rate_per_100k > 0
            assert r.active_days_count == 180
            assert set(r.syndromic_breakdown.keys()) == {"Respiratory", "Gastrointestinal", "Febrile"}

        # Filter by syndrome
        resp_summary = get_regional_surveillance_summary(session, syndrome="Respiratory")
        assert resp_summary.syndrome_filter == "Respiratory"
        for r in resp_summary.regions:
            assert list(r.syndromic_breakdown.keys()) == ["Respiratory"]
    finally:
        session.close()


def test_service_geospatial_timeseries() -> None:
    """Test daily time-series retrieval aligned with anomaly indicators."""
    session = next(get_db_session())
    try:
        ts = get_geospatial_timeseries(
            session=session,
            region_id="REGION_A",
            syndrome="Respiratory",
        )
        assert ts.region_id == "REGION_A"
        assert ts.syndrome == "Respiratory"
        assert ts.points_count == 180
        assert ts.anomaly_points_count > 0

        # Verify time ordering
        for i in range(len(ts.points) - 1):
            assert ts.points[i].observation_date < ts.points[i + 1].observation_date

        # Check anomaly properties on flagged points
        anom_points = [p for p in ts.points if p.is_anomaly]
        assert len(anom_points) == ts.anomaly_points_count
        for p in anom_points:
            assert p.detection_method == "rolling_mad"
            assert p.anomaly_score is not None
            assert p.expected_baseline is not None
    finally:
        session.close()


def test_service_geospatial_mobility_overlay() -> None:
    """Test calendar-aligned surveillance and mobility overlay points."""
    session = next(get_db_session())
    try:
        overlay = get_geospatial_mobility_overlay(
            session=session,
            region_id="REGION_A",
            syndrome="Respiratory",
            mobility_metric="transit_station_pct_change",
        )
        assert overlay.aligned_days == 180
        assert len(overlay.points) == 180

        for p in overlay.points:
            assert p.report_count > 0
            assert p.mobility_value is not None
    finally:
        session.close()


def test_service_geospatial_lagged_correlation() -> None:
    """Test lagged cross-correlation analysis on region time series."""
    session = next(get_db_session())
    try:
        corr = compute_geospatial_lagged_correlation(
            session=session,
            region_id="REGION_A",
            syndrome="Respiratory",
            mobility_metric="transit_station_pct_change",
            min_lag=-7,
            max_lag=14,
        )
        assert corr.sample_size == 180
        assert len(corr.lag_points) == 22  # -7 to +14 inclusive = 22 points
        assert corr.lag_points[0].lag_days == -7
        assert corr.lag_points[-1].lag_days == 14

        # Zero lag point should exist
        zero_lag = [p for p in corr.lag_points if p.lag_days == 0]
        assert len(zero_lag) == 1
        assert zero_lag[0].sample_size_n == 180
        assert zero_lag[0].pearson_r is not None
    finally:
        session.close()


def test_api_geospatial_endpoints(test_client: TestClient) -> None:
    """Test all Phase 7 Geospatial HTTP endpoints."""
    # 1. Regions
    res_reg = test_client.get("/api/v1/geospatial/regions")
    assert res_reg.status_code == 200
    regions = res_reg.json()
    assert len(regions) == 5

    # 2. GeoJSON
    res_geo = test_client.get("/api/v1/geospatial/geojson")
    assert res_geo.status_code == 200
    geojson = res_geo.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 5

    # 3. Surveillance summary
    res_surv = test_client.get("/api/v1/geospatial/surveillance?syndrome=Respiratory")
    assert res_surv.status_code == 200
    surv_data = res_surv.json()
    assert surv_data["total_regions"] == 5
    assert surv_data["syndrome_filter"] == "Respiratory"

    # 4. Timeseries
    res_ts = test_client.get("/api/v1/geospatial/timeseries?region_id=REGION_A&syndrome=Respiratory")
    assert res_ts.status_code == 200
    ts_data = res_ts.json()
    assert ts_data["points_count"] == 180

    # 5. Mobility overlay
    res_mob = test_client.get("/api/v1/geospatial/mobility?region_id=REGION_A&mobility_metric=transit_station_pct_change")
    assert res_mob.status_code == 200
    mob_data = res_mob.json()
    assert mob_data["aligned_days"] == 180

    # 6. Lagged correlation
    res_corr = test_client.get("/api/v1/geospatial/correlations?region_id=REGION_A")
    assert res_corr.status_code == 200
    corr_data = res_corr.json()
    assert len(corr_data["lag_points"]) > 0


def test_api_geospatial_invalid_parameters_returns_400(test_client: TestClient) -> None:
    """Test parameter validation on geospatial endpoints."""
    # Invalid date range
    res = test_client.get("/api/v1/geospatial/surveillance?start_date=2026-06-01&end_date=2026-01-01")
    assert res.status_code == 400

    # Invalid lag range (min_lag >= max_lag)
    res_lag = test_client.get("/api/v1/geospatial/correlations?min_lag=10&max_lag=5")
    assert res_lag.status_code == 400
