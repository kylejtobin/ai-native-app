"""Thin orchestration service - delegates to domain aggregate."""

from __future__ import annotations

from pathlib import Path

from pydantic_ai.settings import ModelSettings

from ..domain.conversation import Conversation
from ..domain.model_catalog import ModelCatalog, ModelSpec


class ConversationService:
    """
    Pure infrastructure orchestrator - zero business logic.

    Service responsibilities:
    1. Own ModelCatalog (single source of truth)
    2. Parse model identifiers to ModelSpec
    3. Delegate to Conversation aggregate
    4. (Future: Persist to Redis/DB)

    Domain aggregate owns ALL business logic.
    """

    def __init__(self, catalog: ModelCatalog):
        """Initialize service with model catalog."""
        self.catalog = catalog

    async def send_message(
        self,
        conversation: Conversation,
        text: str,
        model_id: str | None = None,
        settings: ModelSettings | None = None,
        auto_route: bool = True,
    ) -> Conversation:
        """
        Send message through conversation aggregate.

        Args:
            conversation: Domain aggregate
            text: User message text
            model_id: Optional model identifier in 'vendor:model' format
            settings: Optional Pydantic AI model settings
            auto_route: Whether to use router (if configured)

        Returns:
            Updated conversation aggregate (immutable)
        """
        spec: ModelSpec | None = None
        if model_id:
            spec = self.catalog.parse_spec(model_id)

        return await conversation.send_message(
            text=text,
            spec=spec,
            settings=settings,
            auto_route=auto_route,
        )


def create_conversation_service(catalog_path: Path) -> ConversationService:
    """
    Factory function for creating ConversationService.

    Service owns its own construction logic - deps.py just calls this.

    Args:
        catalog_path: Path to model_metadata.json

    Returns:
        Configured ConversationService ready for use
    """
    catalog = ModelCatalog.from_json_file(catalog_path)
    return ConversationService(catalog=catalog)


__all__ = ["ConversationService", "create_conversation_service"]
