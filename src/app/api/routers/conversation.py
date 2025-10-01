"""Conversation API Router - thin HTTP layer over domain aggregate."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ...domain.model_pool import ModelPool
from ...domain.conversation import Conversation
from ...domain.domain_value import ConversationId
from ...domain.model_catalog import ModelRegistry, ModelSpec
from ...service import ConversationService
from ...service.storage import StorageService
from ..contracts import (
    ConversationHistoryResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from ..deps import get_model_pool, get_conversation_service, get_model_registry, get_storage_service

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.get("/models", response_model=list[str])
async def list_models(
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
) -> list[str]:
    """List available models from the registry."""
    return list(registry.ids())


@router.post("/", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
    model_pool: Annotated[ModelPool, Depends(get_model_pool)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> SendMessageResponse:
    """
    Send a message and get AI response.

    Thin orchestration layer:
    1. Load or start conversation (domain owns serialization)
    2. Parse model spec if provided (service owns identifier parsing)
    3. Call conversation.send_message() (domain owns business logic)
    4. Save conversation (domain owns serialization)
    5. Map to API contract
    """
    redis = storage.get_memory_client()

    # Load existing or start new conversation
    if request.conversation_id:
        conversation = await Conversation.load(
            conv_id=request.conversation_id,
            redis=redis,
            registry=registry,
            model_pool=model_pool,
        )
        if not conversation:
            # Start new conversation with provided ID (idempotent create)
            conversation = Conversation.start_with_id(
                conv_id=request.conversation_id,
                registry=registry,
                model_pool=model_pool,
            )
    else:
        conversation = Conversation.start(
            registry=registry,
            model_pool=model_pool,
        )

    # Parse model spec if provided
    spec: ModelSpec | None = None
    if request.model_id:
        try:
            spec = service.catalog.parse_spec(request.model_id)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid model: {exc}") from exc

    # Execute conversation turn (domain logic)
    try:
        updated_conversation = await conversation.send_message(
            text=request.text,
            spec=spec,
            settings=None,  # Future: support custom settings
            auto_route=request.auto_route,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Persist updated conversation (domain owns serialization)
    await updated_conversation.save(redis)

    # Extract AI response (last message in history)
    last_message = updated_conversation.history.messages[-1]
    response_text = ""
    for part in last_message.content.parts:
        if hasattr(part, "content") and isinstance(part.content, str):
            response_text = part.content
            break

    # Map to API contract
    return SendMessageResponse(
        conversation_id=updated_conversation.history.id,
        message=MessageResponse(content=response_text),
        total_tokens=updated_conversation.history.used_tokens,
    )


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: UUID,
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
    model_pool: Annotated[ModelPool, Depends(get_model_pool)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> ConversationHistoryResponse:
    """Get conversation metadata by ID."""
    redis = storage.get_memory_client()

    # Convert UUID to domain ID
    conv_id = ConversationId(root=conversation_id)

    conversation = await Conversation.load(
        conv_id=conv_id,
        redis=redis,
        registry=registry,
        model_pool=model_pool,
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationHistoryResponse(
        conversation_id=conversation.history.id,
        message_count=len(conversation.history.messages),
        total_tokens=conversation.history.used_tokens,
    )
