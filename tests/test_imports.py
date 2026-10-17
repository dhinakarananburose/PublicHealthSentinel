"""Smoke test verifying package import and public API visibility."""

def test_package_import():
    """Verify that the package imports and has a valid semantic version."""
    import public_health_sentinel

    assert hasattr(public_health_sentinel, "__version__")
    assert public_health_sentinel.__version__ == "0.1.0"


def test_public_api_symbols():
    """Verify that expected core symbols are exported at top-level."""
    from public_health_sentinel import (
        AggregatedObservation,
        DataStatus,
        MobilityIndicator,
        SentinelConfig,
        align_surveillance_and_mobility,
        evaluate_models,
        get_config,
        run_mobility_analysis_pipeline,
    )

    assert AggregatedObservation is not None
    assert MobilityIndicator is not None
    assert DataStatus is not None
    assert SentinelConfig is not None
    assert callable(get_config)
    assert callable(align_surveillance_and_mobility)
    assert callable(evaluate_models)
    assert callable(run_mobility_analysis_pipeline)


def test_default_config():
    """Verify that configuration loads cleanly with default settings."""
    from public_health_sentinel.config import get_config

    config = get_config()
    assert config.app_name == "PublicHealthSentinel"
    assert config.app_env in {"development", "testing", "staging", "production"}
    assert config.log_level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
