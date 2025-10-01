"""
Tests for ModelCatalog and ModelRegistry domain logic.

These tests demonstrate:
- Testing business logic (deduplication, default ordering)
- Testing factory methods
- NOT testing enum validation (that's Pydantic's job)
- NOT testing frozen=True (that's Pydantic's job)
"""

from pathlib import Path

import pytest

from app.domain.domain_type import AIModelVendor
from app.domain.model_catalog import ModelCatalog, ModelRegistry, ModelSpec


@pytest.fixture
def model_catalog() -> ModelCatalog:
    """Load the real model catalog from configuration."""
    catalog_path = Path(__file__).parents[3] / "src" / "app" / "domain" / "model_metadata.json"
    return ModelCatalog.from_json_file(catalog_path)


@pytest.fixture
def anthropic_sonnet_spec() -> ModelSpec:
    """Create a ModelSpec for Anthropic Claude Sonnet."""
    return ModelSpec(
        vendor=AIModelVendor.ANTHROPIC,
        variant_id="claude-sonnet-4-5-20250929",
    )


@pytest.fixture
def anthropic_haiku_spec() -> ModelSpec:
    """Create a ModelSpec for Anthropic Claude Haiku."""
    return ModelSpec(
        vendor=AIModelVendor.ANTHROPIC,
        variant_id="claude-3-5-haiku-20241022",
    )


def test_model_catalog_loads_from_json(model_catalog: ModelCatalog):
    """
    Demonstrates: Testing factory method behavior, not validation.

    We test that the catalog loads and has expected structure.
    We don't test JSON parsing (Python's job) or field validation (Pydantic's job).
    """
    # Test that catalog has vendors
    anthropic_catalog = model_catalog.vendor(AIModelVendor.ANTHROPIC)
    assert anthropic_catalog.vendor == AIModelVendor.ANTHROPIC

    openai_catalog = model_catalog.vendor(AIModelVendor.OPENAI)
    assert openai_catalog.vendor == AIModelVendor.OPENAI


def test_model_registry_deduplicates_specs(
    model_catalog: ModelCatalog,
    anthropic_sonnet_spec: ModelSpec,
):
    """
    Demonstrates: Testing business logic (deduplication behavior).

    This is our domain rule: duplicate specs should be deduplicated.
    We're testing the validator logic, not Pydantic's validation framework.
    """
    # Create registry with duplicate specs
    registry = ModelRegistry.from_specs(
        catalog=model_catalog,
        default=anthropic_sonnet_spec,
        available=[anthropic_sonnet_spec, anthropic_sonnet_spec],  # Duplicates
    )

    # Business assertion: duplicates removed
    assert len(registry.available) == 1
    assert registry.available[0] == anthropic_sonnet_spec


def test_model_registry_default_appears_first(
    model_catalog: ModelCatalog,
    anthropic_sonnet_spec: ModelSpec,
    anthropic_haiku_spec: ModelSpec,
):
    """
    Demonstrates: Testing business invariant (default ordering).

    Domain rule: default model always appears first in available list.
    This enables "pick first valid model" strategies.
    """
    # Create registry with default NOT first in available list
    registry = ModelRegistry.from_specs(
        catalog=model_catalog,
        default=anthropic_sonnet_spec,
        available=[anthropic_haiku_spec, anthropic_sonnet_spec],  # Default is second
    )

    # Business assertion: default moved to front
    assert registry.available[0] == anthropic_sonnet_spec
    assert len(registry.available) == 2  # Both specs present


def test_model_spec_equality_by_value_not_identity():
    """
    Demonstrates: Testing value semantics (frozen model behavior).

    We test that two ModelSpec instances with same data are equal.
    We don't test frozen=True itself—we test the business consequence.
    """
    spec1 = ModelSpec(vendor=AIModelVendor.ANTHROPIC, variant_id="claude-sonnet-4-5-20250929")
    spec2 = ModelSpec(vendor=AIModelVendor.ANTHROPIC, variant_id="claude-sonnet-4-5-20250929")

    # Different instances
    assert spec1 is not spec2
    # But equal by value
    assert spec1 == spec2
    # And hashable (can be used in sets/dicts)
    assert {spec1, spec2} == {spec1}  # Deduplicate in set


def test_model_catalog_ensure_spec_validates_existence(
    model_catalog: ModelCatalog,
    anthropic_sonnet_spec: ModelSpec,
):
    """
    Demonstrates: Testing domain validation logic.

    This tests our business rule: specs must exist in catalog.
    We're testing domain logic, not Pydantic field validation.
    """
    # Valid spec - should not raise
    model_catalog.ensure_spec(anthropic_sonnet_spec)

    # Invalid spec - should raise KeyError (domain uses KeyError for missing variants)
    fake_spec = ModelSpec(vendor=AIModelVendor.ANTHROPIC, variant_id="nonexistent-model")
    with pytest.raises(KeyError, match="not registered"):
        model_catalog.ensure_spec(fake_spec)
