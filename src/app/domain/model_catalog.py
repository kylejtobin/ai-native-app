"""Model Catalog - Configuration-Driven LLM Model Management.

Provides type-safe, validated management of available LLM models across providers.
The catalog is loaded from JSON configuration and provides O(1) lookups for model
variants and capabilities.

Architecture:
    ModelCatalog: Root container, loaded from model_metadata.json
    ├─ VendorCatalog: Per-provider metadata (Anthropic, OpenAI)
    │  └─ ModelVariant: Specific model versions with capabilities
    ├─ ModelSpec: Normalized reference (vendor + variant_id)
    └─ ModelRegistry: Allow-listed subset with default model

Key Features:
    - O(1) Model Lookup: Uses computed dicts, not linear search
    - Validation: Pydantic ensures no duplicate IDs, required fields present
    - Type Safety: Enums for vendors, frozen models prevent mutation
    - Flexible Identifiers: Support aliases (e.g., "claude-sonnet-4.5" → full ID)
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    RootModel,
    ValidationInfo,
    computed_field,
    field_validator,
    model_validator,
)

from .domain_type import AIModelVendor

# ---------------------------------------------------------------------------
# Model Catalog Definitions (loaded from configuration)
# ---------------------------------------------------------------------------


class ModelVariant(BaseModel):
    """Specific LLM Model Version within a Vendor's Catalog.

    Represents a concrete model like "claude-sonnet-4-5-20250929" with its
    metadata and capabilities. Multiple identifiers (ID, API ID, aliases)
    can all resolve to the same variant.

    Attributes:
        id: Canonical identifier (e.g., "claude-sonnet-4-5-20250929")
        api_id: Provider's API string (usually same as id)
        family: Model family for grouping (e.g., "claude-sonnet")
        tier: Specific tier within family (e.g., "sonnet-4.5")
        tier_class: Performance category for routing decisions
        aliases: Alternative names that resolve to this variant
        notes: Human-readable description/usage notes

    Tier Classes:
        fast: Low-latency, inexpensive (routing/tool selection)
        standard: Balanced performance (general queries)
        deep: Maximum capability, higher cost (complex reasoning)
    """

    id: str
    api_id: str
    family: str
    tier: str
    tier_class: Literal["fast", "standard", "deep"] = "standard"
    aliases: tuple[str, ...] = ()
    notes: str | None = None

    model_config = ConfigDict(frozen=True)

    @computed_field
    @property
    def identifiers(self) -> frozenset[str]:
        """All Valid Lookup Keys for This Variant.

        Returns frozenset of {id, api_id, *aliases} for O(1) lookup.
        Pydantic automatically caches this on frozen models, so it's
        computed once and reused.

        Example:
            >>> variant = ModelVariant(
            ...     id="claude-sonnet-4-5",
            ...     api_id="claude-sonnet-4-5-20250929",
            ...     aliases=("claude-sonnet-4.5",)
            ... )
            >>> variant.identifiers
            frozenset({'claude-sonnet-4-5', 'claude-sonnet-4-5-20250929', 'claude-sonnet-4.5'})
        """
        return frozenset({self.id, self.api_id, *self.aliases})


class VendorCatalog(BaseModel):
    """Per-Provider Model Catalog with Metadata.

    Contains all available models for a single LLM provider (Anthropic, OpenAI)
    along with provider-specific capabilities and configuration.

    Attributes:
        vendor: Provider identifier enum value
        template_key: String key for provider-specific templates
        supports_native_thinking: Whether provider offers extended thinking mode
        allowed_markers: Valid prefixes for model identifiers
        available_models: All model variants offered by this provider

    Performance:
        Uses computed property to build O(1) lookup dict from list of variants.
        This trades memory (one dict) for speed (instant lookups vs linear search).
    """

    vendor: AIModelVendor
    template_key: str
    supports_native_thinking: bool = False
    allowed_markers: tuple[str, ...] = ()
    available_models: tuple[ModelVariant, ...] = ()

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="after")
    def check_duplicate_identifiers(self) -> VendorCatalog:
        """Validate No Duplicate Model Identifiers.

        Runs after model construction to ensure all model identifiers
        (including aliases) are unique within this vendor's catalog.

        Raises:
            ValueError: If any identifier appears in multiple variants
        """
        # Flatten all identifiers from all variants
        all_ids = [id for variant in self.available_models for id in variant.identifiers]
        unique_ids = set(all_ids)

        # Check for duplicates
        if len(all_ids) != len(unique_ids):
            duplicates = [x for x in unique_ids if all_ids.count(x) > 1]
            raise ValueError(f"Duplicate model identifiers for vendor '{self.vendor.value}': {sorted(duplicates)}")
        return self

    @computed_field
    @property
    def _variant_lookup(self) -> dict[str, ModelVariant]:
        """O(1) Lookup Dictionary (Cached by Pydantic).

        Builds a flattened dictionary mapping every identifier (id, api_id, alias)
        to its ModelVariant. This allows instant lookups instead of iterating
        through all variants and checking identifiers.

        Performance:
            - Construction: O(n × m) where n=variants, m=identifiers per variant
            - Lookup: O(1) constant time
            - Memory: O(n × m) for the dict

        Pydantic caches this on frozen models, so it's computed once per instance.
        """
        return {id: variant for variant in self.available_models for id in variant.identifiers}

    def find_variant(self, identifier: str) -> ModelVariant:
        """Find Model Variant by Any Valid Identifier.

        Performs O(1) lookup using the cached _variant_lookup dictionary.
        Accepts ID, API ID, or any alias.

        Args:
            identifier: Model identifier string (whitespace stripped)

        Returns:
            ModelVariant for the requested model

        Raises:
            KeyError: If identifier not found in catalog

        Example:
            >>> catalog = vendor.find_variant("claude-sonnet-4.5")  # alias
            >>> catalog = vendor.find_variant("claude-sonnet-4-5-20250929")  # full ID
            >>> # Both return the same ModelVariant instance
        """
        variant = self._variant_lookup.get(identifier.strip())
        if variant is None:
            raise KeyError(f"Model '{identifier}' not registered for vendor '{self.vendor.value}'")
        return variant


class ModelCatalog(RootModel[dict[AIModelVendor, VendorCatalog]]):
    """Catalog of vendors - wraps dict for type safety and validation."""

    root: dict[AIModelVendor, VendorCatalog]

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelCatalog:
        """Load catalog from dict, explicitly injecting vendor keys - no mutation."""
        enriched = {vendor_key: {**vendor_data, "vendor": vendor_key} for vendor_key, vendor_data in data.items()}
        return cls.model_validate(enriched)

    @classmethod
    def from_json_file(cls, path: Path) -> ModelCatalog:
        """Load and validate catalog from JSON."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def vendor(self, vendor: AIModelVendor) -> VendorCatalog:
        """O(1) dict lookup - vendor enum as key!"""
        if vendor not in self.root:
            raise KeyError(f"Vendor '{vendor.value}' not registered")
        return self.root[vendor]

    def parse_spec(self, identifier: str) -> ModelSpec:
        vendor_key, sep, variant_id = identifier.partition(":")
        if not sep:
            raise ValueError("Model identifier must be in 'vendor:model' format")
        vendor = AIModelVendor(vendor_key.strip())
        variant = self.vendor(vendor).find_variant(variant_id.strip())
        return ModelSpec(vendor=vendor, variant_id=variant.id)

    def ensure_spec(self, spec: ModelSpec) -> ModelSpec:
        self.vendor(spec.vendor).find_variant(spec.variant_id)
        return spec


# ---------------------------------------------------------------------------
# Model specifications and capabilities
# ---------------------------------------------------------------------------


class ModelSpec(BaseModel):
    """Normalized reference to a vendor-scoped model variant."""

    vendor: AIModelVendor
    variant_id: str

    model_config = ConfigDict(frozen=True)

    def variant(self, catalog: ModelCatalog) -> ModelVariant:
        return catalog.vendor(self.vendor).find_variant(self.variant_id)

    def to_agent_model(self, catalog: ModelCatalog) -> str:
        variant = self.variant(catalog)
        return variant.api_id


class ModelCapability(BaseModel):
    """Capability view constructed from a model spec and catalog metadata."""

    spec: ModelSpec
    variant: ModelVariant
    vendor: VendorCatalog

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_catalog(cls, spec: ModelSpec, catalog: ModelCatalog) -> ModelCapability:
        vendor = catalog.vendor(spec.vendor)
        variant = vendor.find_variant(spec.variant_id)
        return cls(spec=spec, variant=variant, vendor=vendor)

    @property
    def is_fast_tier(self) -> bool:
        return self.variant.tier_class == "fast"

    @property
    def is_deep_tier(self) -> bool:
        return self.variant.tier_class == "deep"


class FastModelOverrides(BaseModel):
    """Mapping from deep-thinking models to their fast companion variants."""

    overrides: tuple[tuple[ModelSpec, ModelSpec], ...] = ()

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_identifiers(
        cls,
        mapping: dict[str, str],
        *,
        catalog: ModelCatalog,
    ) -> FastModelOverrides:
        pairs = [(catalog.parse_spec(primary), catalog.parse_spec(companion)) for primary, companion in mapping.items()]
        return cls(overrides=tuple(pairs))

    def for_spec(self, spec: ModelSpec) -> ModelSpec | None:
        for primary, companion in self.overrides:
            if primary == spec:
                return companion
        return None


class ModelRegistry(BaseModel):
    """Allow-listed set of models scoped to a single catalog."""

    catalog: ModelCatalog
    default: ModelSpec
    available: tuple[ModelSpec, ...]

    model_config = ConfigDict(frozen=True)

    @field_validator("available", mode="after")
    @classmethod
    def _deduplicate_and_ensure_default(cls, v: tuple[ModelSpec, ...], info: ValidationInfo) -> tuple[ModelSpec, ...]:
        """Deduplicate specs and ensure default is first."""
        default = info.data.get("default")
        if not default:
            return v

        # Deduplicate while preserving order, ensure default is first
        seen: set[ModelSpec] = set()
        ordered: list[ModelSpec] = []

        # Add default first if it exists in available
        if default in v:
            ordered.append(default)
            seen.add(default)

        # Add remaining specs in order, skipping duplicates
        for spec in v:
            if spec not in seen:
                ordered.append(spec)
                seen.add(spec)

        return tuple(ordered)

    @classmethod
    def from_specs(
        cls,
        catalog: ModelCatalog,
        default: ModelSpec,
        available: Sequence[ModelSpec] | None = None,
    ) -> ModelRegistry:
        """Factory - Pydantic validator will deduplicate automatically."""
        return cls(catalog=catalog, default=default, available=tuple([default, *(available or [])]))

    def ids(self) -> tuple[str, ...]:
        return tuple(f"{spec.vendor.value}:{spec.variant_id}" for spec in self.available)

    def capability_for(self, spec: ModelSpec) -> ModelCapability:
        """Build capability view for a spec."""
        self.catalog.ensure_spec(spec)
        return ModelCapability.from_catalog(spec, self.catalog)

    def resolve_spec(self, spec: ModelSpec) -> ModelSpec:
        """Validate that spec is allow-listed."""
        self.catalog.ensure_spec(spec)
        if spec not in self.available:
            raise ValueError(f"Model not allow-listed: {spec.vendor.value}:{spec.variant_id}")
        return spec

    def resolve_identifier(self, identifier: str) -> ModelSpec:
        """Parse identifier string and validate."""
        spec = self.catalog.parse_spec(identifier)
        return self.resolve_spec(spec)

    def resolve_or_default(self, spec: ModelSpec | None) -> ModelSpec:
        """Use provided spec or fall back to default."""
        return self.default if spec is None else self.resolve_spec(spec)


__all__ = [
    "FastModelOverrides",
    "ModelCapability",
    "ModelCatalog",
    "ModelRegistry",
    "ModelSpec",
]
