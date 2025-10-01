"""API dependency wiring with intelligent model selection."""

from functools import lru_cache
from pathlib import Path

from ..config import settings
from ..domain.model_pool import ModelPool
from ..domain.domain_type import AIModelVendor
from ..domain.model_catalog import ModelCatalog, ModelRegistry, ModelSpec
from ..service import ConversationService, create_conversation_service
from ..service.storage import (
    MemoryStoreConfig,
    ObjectStoreConfig,
    StorageService,
    VectorStoreConfig,
    create_storage_service,
)


def _select_default_model(catalog: ModelCatalog) -> str:
    """Intelligently select default model based on available API keys and catalog.

    Priority:
    1. anthropic (if API key exists and is valid)
    2. openai (if API key exists and is valid)
    3. First available vendor in catalog

    Within vendor, prefer standard tier over fast or deep.

    Returns:
        Model identifier in 'vendor:model_id' format
    """
    # Check which vendors have valid API keys
    available_vendors: list[AIModelVendor] = []

    if settings.anthropic_api_key and settings.anthropic_api_key != "NEED-API-KEY":
        available_vendors.append(AIModelVendor.ANTHROPIC)
    if settings.openai_api_key and settings.openai_api_key != "NEED-API-KEY":
        available_vendors.append(AIModelVendor.OPENAI)

    # Fallback: use first vendor in catalog if no valid API keys
    if not available_vendors and catalog.root:
        available_vendors = [next(iter(catalog.root.keys()))]

    # Find first standard-tier model from preferred vendor
    for vendor_enum in available_vendors:
        try:
            vendor_entry = catalog.vendor(vendor_enum)

            # Prefer standard tier
            for variant in vendor_entry.available_models:
                if variant.tier_class == "standard":
                    return f"{vendor_enum.value}:{variant.id}"

            # Fallback: use first model if no standard tier
            if vendor_entry.available_models:
                variant = vendor_entry.available_models[0]
                return f"{vendor_enum.value}:{variant.id}"
        except KeyError:
            continue

    # Last resort: use first model from first vendor
    if catalog.root:
        first_vendor_key = next(iter(catalog.root.keys()))
        first_vendor = catalog.root[first_vendor_key]
        if first_vendor.available_models:
            first_model = first_vendor.available_models[0]
            return f"{first_vendor.vendor.value}:{first_model.id}"

    raise RuntimeError("No models available in catalog")


@lru_cache(maxsize=1)
def get_conversation_service() -> ConversationService:
    """
    Create conversation service with intelligent model selection (cached singleton).

    Service factory handles all construction logic - deps.py is just thin DI glue.
    """
    catalog_path = Path(settings.model_catalog_path)
    return create_conversation_service(catalog_path=catalog_path)


@lru_cache(maxsize=1)
def get_model_registry() -> ModelRegistry:
    """Create model registry with intelligent model selection (cached singleton)."""
    service = get_conversation_service()

    # Use the same auto-selected default
    default_model = _select_default_model(service.catalog)
    default_spec = service.catalog.parse_spec(default_model)

    # Auto-allow all models from vendors with valid API keys
    allowed_list: list[ModelSpec] = []
    for vendor_entry in service.catalog.root.values():
        vendor = vendor_entry.vendor

        # Check if this vendor has a valid API key
        has_key: bool = False
        if vendor == AIModelVendor.ANTHROPIC:
            key = settings.anthropic_api_key
            has_key = bool(key and key != "NEED-API-KEY")
        elif vendor == AIModelVendor.OPENAI:
            key = settings.openai_api_key
            has_key = bool(key and key != "NEED-API-KEY")

        if has_key:
            for variant in vendor_entry.available_models:
                allowed_list.append(ModelSpec(vendor=vendor, variant_id=variant.id))

    # If no valid API keys, allow all models (for testing/development)
    if not allowed_list:
        for vendor_entry in service.catalog.root.values():
            for variant in vendor_entry.available_models:
                allowed_list.append(ModelSpec(vendor=vendor_entry.vendor, variant_id=variant.id))

    # Create registry using domain factory method
    return ModelRegistry.from_specs(
        catalog=service.catalog,
        default=default_spec,
        available=allowed_list if allowed_list else None,
    )


@lru_cache(maxsize=1)
def get_model_pool() -> ModelPool:
    """Create agent pool with registry (cached singleton)."""
    registry = get_model_registry()
    return ModelPool(registry=registry)


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    """Create storage service from config (cached singleton)."""
    return create_storage_service(
        memory_config=MemoryStoreConfig(url=settings.redis_url),
        object_config=ObjectStoreConfig(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        ),
        vector_config=VectorStoreConfig(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
        ),
    )
