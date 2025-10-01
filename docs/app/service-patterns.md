# Service Layer Patterns

> **Services orchestrate, domains contain logic**

This document shows how we keep services thin by using real examples from `src/app/service/` and `src/app/api/`.

## The Thin Orchestrator Pattern

Services coordinate between domain and infrastructure—they don't implement business logic.

### What Services DON'T Do

Our `StorageService` is a perfect example of what services SHOULD be:

From [`src/app/service/storage.py`](../../src/app/service/storage.py):

```python
class StorageService:
    """
    Thin orchestrator - lazy-loads storage clients from config.
    
    Responsibilities:
    - Provide Redis client for conversation history
    - Provide MinIO client for file storage
    - Provide Qdrant client for vector search
    - Lazy initialization for faster startup
    """
    
    def __init__(
        self,
        memory_config: MemoryStoreConfig,
        object_config: ObjectStoreConfig,
        vector_config: VectorStoreConfig,
    ):
        self.memory_config = memory_config
        self.object_config = object_config
        self.vector_config = vector_config
        self._memory_client: Redis | None = None
        self._object_client: Minio | None = None
        self._vector_client: QdrantClient | None = None
    
    def get_memory_client(self) -> Redis:
        """Get or create Redis client (lazy)."""
        if self._memory_client is None:
            from redis.asyncio import Redis
            self._memory_client = Redis.from_url(self.memory_config.url)
        return self._memory_client
```

**Notice what's NOT here:**
- ❌ No `save_conversation()` method
- ❌ No `load_conversation()` method
- ❌ No business logic
- ❌ No domain concepts

**Only infrastructure client provisioning.**

## API Layer: Thin HTTP Wrapper

Our conversation API router shows pure orchestration.

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
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
            raise HTTPException(status_code=404, detail="Conversation not found")
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
            settings=None,
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
```

**Every step is explicit:**
1. **Infrastructure**: Get Redis client from storage service
2. **Domain**: Load or start conversation (domain owns `load()` and `start()`)
3. **Service**: Parse model identifier string (infrastructure concern)
4. **Domain**: Execute conversation turn (domain owns `send_message()`)
5. **Domain**: Persist conversation (domain owns `save()`)
6. **API**: Extract response text (view concern)
7. **API**: Map to contract (boundary translation)

**No business logic in the router!**

## Service Responsibilities

### ✅ What Services DO:

**1. Provide Infrastructure Clients**

From [`src/app/service/storage.py`](../../src/app/service/storage.py):

```python
def get_memory_client(self) -> Redis:
    """Get or create Redis client (lazy)."""
    if self._memory_client is None:
        from redis.asyncio import Redis
        self._memory_client = Redis.from_url(self.memory_config.url)
    return self._memory_client
```

**2. Parse String Identifiers**

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
# Service parses string → domain type
if request.model_id:
    try:
        spec = service.catalog.parse_spec(request.model_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid model: {exc}") from exc
```

This is NOT business logic—it's infrastructure concern (string → typed domain object).

**3. Coordinate Calls**

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
# Router coordinates: domain → save → map to contract
updated_conversation = await conversation.send_message(...)
await updated_conversation.save(redis)
return SendMessageResponse(...)
```

**4. Map Between Layers**

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
# Extract from domain model
last_message = updated_conversation.history.messages[-1]

# Map to API contract
return SendMessageResponse(
    conversation_id=updated_conversation.history.id,
    message=MessageResponse(content=response_text),
    total_tokens=updated_conversation.history.used_tokens,
)
```

### ❌ What Services DON'T DO:

**No Business Logic:**
```python
# ❌ BAD - Would be business logic in service
async def send_message(self, text: str):
    if len(text) > 1000:  # ← Business rule!
        raise ValueError("Message too long")
    # ...
```

**Domain owns business rules:**

From [`src/app/api/contracts/conversation.py`](../../src/app/api/contracts/conversation.py):

```python
# ✅ GOOD - Validation in contract
class SendMessageRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=10_000,  # ← Pydantic validates
        description="User message to send",
    )
```

**No Domain Concepts:**
```python
# ❌ BAD - Service shouldn't know about routing
async def send_message(self, text: str):
    if is_complex(text):  # ← Domain concept!
        model = select_smart_model()
    # ...
```

**Domain owns routing:**
```python
# ✅ GOOD - Routing in domain
updated = await conversation.send_message(
    text=text,
    auto_route=True,  # ← Domain handles this
)
```

## Dependency Injection Pattern

Services receive dependencies via constructor injection.

From [`src/app/api/deps.py`](../../src/app/api/deps.py):

```python
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
    
    # Create registry using domain factory method
    return ModelRegistry.from_specs(
        catalog=service.catalog,
        default=default_spec,
        available=allowed_list if allowed_list else None,
    )
```

**Pattern:**
- Functions create dependencies with intelligent defaults
- `@lru_cache` makes them singletons
- FastAPI `Depends` injects them into routes
- All wiring happens in one place (`deps.py`)

**Usage in routes:**

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
async def send_message(
    request: SendMessageRequest,
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
    model_pool: Annotated[ModelPool, Depends(get_model_pool)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> SendMessageResponse:
    # All dependencies injected - no global state!
```

## Simple List Endpoint

The simplest example shows how thin services should be:

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
@router.get("/models", response_model=list[str])
async def list_models(
    registry: Annotated[ModelRegistry, Depends(get_model_registry)],
) -> list[str]:
    """List available models from the registry."""
    return list(registry.ids())
```

**That's it:**
- Inject dependency
- Call domain method
- Return result

**No orchestration needed when domain does the work.**

## Factory Functions

Create services using factory functions for clean construction:

From [`src/app/service/storage.py`](../../src/app/service/storage.py):

```python
def create_storage_service(
    memory_config: MemoryStoreConfig,
    object_config: ObjectStoreConfig,
    vector_config: VectorStoreConfig,
) -> StorageService:
    """Factory from infrastructure configs."""
    return StorageService(memory_config, object_config, vector_config)
```

From [`src/app/api/deps.py`](../../src/app/api/deps.py):

```python
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
```

**Why factories?**
- Encapsulates construction logic
- Testable (can mock config)
- Clear dependencies
- Single responsibility

## Error Handling at Boundaries

Let domain raise errors, catch at API boundary:

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
# Parse model spec - infrastructure concern
if request.model_id:
    try:
        spec = service.catalog.parse_spec(request.model_id)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid model: {exc}") from exc

# Execute domain logic - let it raise
try:
    updated_conversation = await conversation.send_message(
        text=request.text,
        spec=spec,
        settings=None,
        auto_route=request.auto_route,
    )
except ValueError as exc:
    raise HTTPException(status_code=400, detail=str(exc)) from exc
```

**Pattern:**
- Domain raises domain exceptions (`ValueError`, `KeyError`)
- API converts to HTTP exceptions (`HTTPException`)
- Service doesn't catch—just coordinates

## Benefits of Thin Services

**Maintainability:**
- Business logic in one place (domain)
- Easy to find what does what
- Changes don't ripple through layers

**Testability:**
- Domain is pure logic (easy to test)
- Services just coordinate (simple to test)
- Can test domain without HTTP layer

**Clarity:**
- Each layer has clear responsibility
- No duplicate logic
- Obvious where to add features

---

**See Also:**
- [`src/app/service/storage.py`](../../src/app/service/storage.py) - Thin storage service
- [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py) - Thin API layer
- [`src/app/api/deps.py`](../../src/app/api/deps.py) - Dependency injection
- `domain-models.md` - Where business logic lives
- `immutability.md` - Domain model patterns

