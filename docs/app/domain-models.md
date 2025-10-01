# Rich Domain Models

> **Business logic lives in domain models, not services**

This document shows how we build rich domain models that understand their own business rules, using real examples from `src/app/domain/`.

## The Aggregate Root Pattern

An aggregate root orchestrates a cluster of related models and contains the main business logic.

### Conversation: Our Main Aggregate

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class Conversation(BaseModel):
    """
    Conversation aggregate - orchestrates routing and model execution.
    
    Algebraic Composition:
    - ConversationHistory: Identity + messages (immutable)
    - ModelRegistry: Available models + default
    - ModelPool: Model client cache
    - ModelClassifier: Optional routing logic
    
    Business Logic:
    - send_message(): Add user message → route → call model → wrap response
    - Returns new Conversation (immutable updates)
    """
    history: ConversationHistory
    registry: ModelRegistry
    model_pool: ModelPool
    router: ModelClassifier | None = None
    tool_router: ToolClassifier | None = None
    
    model_config = ConfigDict(frozen=True)
```

**What makes this a rich model?**
- **Composition**: Brings together history, registry, model pool, routers
- **Behavior**: `send_message()` contains full conversation flow logic
- **Immutability**: Always returns new instance, never mutates self
- **Dependencies**: Takes infrastructure (model_pool) as composition

## Factory Methods: Smart Construction

Domain models know how to construct themselves correctly.

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
@classmethod
def start(
    cls,
    *,
    registry: ModelRegistry,
    model_pool: ModelPool,
    router: ModelClassifier | None = None,
    tool_router: ToolClassifier | None = None,
    status: ConversationStatus = ConversationStatus.ACTIVE,
) -> Conversation:
    """Factory: Start new conversation with fresh history."""
    history = ConversationHistory(
        id=ConversationId(),
        status=status,
    )
    return cls(
        history=history,
        registry=registry,
        model_pool=model_pool,
        router=router,
        tool_router=tool_router,
    )
```

**Why factory methods?**
- Encapsulates construction logic
- Clear intent: `Conversation.start()` vs bare constructor
- Can have multiple factories: `start()`, `load()`, `from_dict()`
- Validates required dependencies are provided

## Domain-Owned Persistence

Domain models define their own serialization strategy.

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
@classmethod
async def load(
    cls,
    *,
    conv_id: ConversationId,
    redis: Redis,
    registry: ModelRegistry,
    model_pool: ModelPool,
    router: ModelClassifier | None = None,
    tool_router: ToolClassifier | None = None,
) -> Conversation | None:
    """
    Load conversation from Redis by ID.
    
    Domain owns serialization logic, infrastructure provides client.
    Returns None if conversation doesn't exist.
    """
    key = f"conversation:{conv_id.root}"
    data = await redis.get(key)
    if not data:
        return None
    
    history = ConversationHistory.model_validate_json(data)
    return cls(
        history=history,
        registry=registry,
        model_pool=model_pool,
        router=router,
        tool_router=tool_router,
    )

async def save(self, redis: Redis) -> None:
    """
    Persist conversation history to Redis.
    
    Domain owns serialization logic (Pydantic), infrastructure provides client.
    Key format: conversation:{uuid}
    """
    key = f"conversation:{self.history.id.root}"
    data = self.history.model_dump_json()
    await redis.set(key, data)
```

**Domain vs Infrastructure Separation:**
- **Domain decides**: What to save, how to serialize, key format
- **Infrastructure provides**: Redis client, connection management
- **Domain owns**: `model_validate_json()`, `model_dump_json()`
- **Infrastructure can't**: Change serialization without domain permission

## Business Logic in Methods

The core business flows live in domain model methods.

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
async def send_message(
    self,
    text: str,
    spec: ModelSpec | None = None,
    settings: ModelSettings | None = None,
    auto_route: bool = True,
) -> Conversation:
    """Send Message and Get LLM Response with Intelligent Routing.
    
    Implements the complete message flow with two-phase routing optimization.
    
    Execution Flow:
        1. Wrap user text in StoredMessage with ID
        2. Phase 1a: Model Selection (if auto_route enabled)
        3. Phase 1b: Tool Selection (if auto_route enabled)
        4. Phase 2: Execution with selected model + tools
        5. Wrap response message(s) with IDs
        6. Return new Conversation instance (immutable update)
    """
    # === Step 1: Wrap User Input ===
    user_msg = StoredMessage(
        id=MessageId(),
        content=ModelRequest(parts=[UserPromptPart(content=text)]),
    )
    updated_history = self.history.append_message(user_msg)
    
    # === Phase 1a: Model Selection ===
    if auto_route and spec is None and self.router:
        spec = await self.router.route(updated_history)
    if spec is None:
        spec = self.registry.default
    
    # === Phase 1b: Tool Selection ===
    tool_names: list[str] | None = None
    if auto_route and self.tool_router:
        tool_names = await self.tool_router.route(text)
    
    # === Phase 2: Execute ===
    model = self.model_pool.get_model(spec, tool_names=tool_names)
    result = await model.run(
        deps=updated_history,
        message_history=list(updated_history.message_content),
        model_settings=settings,
    )
    
    # === Step 3: Process Response ===
    response_messages = [
        StoredMessage(id=MessageId(), content=msg) 
        for msg in result.new_messages()
    ]
    
    final_history = updated_history
    for response_msg in response_messages:
        final_history = final_history.append_message(response_msg)
    
    # === Step 4: Return New Instance ===
    return self.model_copy(update={"history": final_history})
```

**Why this belongs in the domain:**
- **Complex workflow**: 6 distinct steps with conditional logic
- **Business decisions**: When to route, which tools to use
- **Domain concepts**: Messages, routing, history
- **No infrastructure**: Just uses provided dependencies
- **Returns domain type**: New `Conversation` instance

## Immutable Updates with Functional Patterns

Domain models use immutable updates to maintain safety and traceability.

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class ConversationHistory(BaseModel):
    """Complete Conversation State for Persistence."""
    
    id: ConversationId
    messages: tuple[StoredMessage, ...] = ()  # Tuple, not list!
    status: ConversationStatus = ConversationStatus.ACTIVE
    
    model_config = ConfigDict(frozen=True)
    
    def append_message(self, msg: StoredMessage) -> ConversationHistory:
        """Append Message Immutably.
        
        Functional update pattern: creates new ConversationHistory with added message.
        Original instance remains unchanged, enabling safe concurrent access.
        
        Args:
            msg: StoredMessage to append to conversation
        
        Returns:
            New ConversationHistory instance with message added
        
        Example:
            >>> history1 = ConversationHistory(id=ConversationId())
            >>> history2 = history1.append_message(msg)
            >>> len(history1.messages)  # 0 - original unchanged
            >>> len(history2.messages)  # 1 - new instance has message
        """
        return self.model_copy(update={"messages": (*self.messages, msg)})
```

**The Pattern:**
```python
# Immutable append using tuple unpacking
return self.model_copy(update={"messages": (*self.messages, msg)})
```

**Why tuple instead of list?**
- Enforces immutability at Python level
- Can't accidentally `messages.append()` 
- Pydantic validates it's immutable
- Convert to list only at boundaries (calling Pydantic AI)

## Sub-Domain Models with Specific Logic

Smaller models handle specific business concerns.

### Intelligent Routing

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class ModelClassifier(BaseModel):
    """
    Routes queries to appropriate models using a fast classifier.
    
    Two-Phase Optimization:
    1. Fast model (Haiku) analyzes query → picks execution model
    2. Execution model (Sonnet/GPT-5) handles actual query
    
    This saves cost by using expensive models only when needed.
    """
    spec: ModelSpec  # Fast model for routing
    registry: ModelRegistry  # Available execution models
    _client_cache: Agent[ConversationHistory, RouteDecision] | None = PrivateAttr(default=None)
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def client(self) -> Agent[ConversationHistory, RouteDecision]:
        """Lazy-initialized classifier (cached)."""
        if self._client_cache is None:
            from pydantic_ai import Agent
            model = self.spec.to_agent_model(self.registry.catalog)
            client: Agent[ConversationHistory, RouteDecision] = Agent(
                model,
                deps_type=ConversationHistory,
                output_type=RouteDecision,
                system_prompt=MODEL_ROUTER_SYSTEM_PROMPT,
            )
            object.__setattr__(self, "_client_cache", client)
            return client
        return self._client_cache
    
    async def route(self, history: ConversationHistory) -> ModelSpec:
        """
        Decide which model to use based on conversation history.
        
        Extracts latest user message, calls fast routing model,
        validates decision against registry, returns ModelSpec.
        """
        # Extract user prompt from latest message
        latest_msg = history.messages[-1] if history.messages else None
        user_prompt = ""
        if latest_msg:
            for part in latest_msg.content.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    user_prompt = part.content
                    break
        
        # Call fast routing model
        result = await self.client.run(user_prompt=user_prompt, deps=history)
        decision: RouteDecision = result.output
        
        # Parse and validate decision
        identifier = decision.model.value  # Enum value
        spec = self.registry.catalog.parse_spec(identifier)
        return spec
```

**Business Logic:**
- Knows how to extract user prompt from complex message structure
- Delegates to fast LLM for intelligent decision
- Validates decision against allowed models
- Returns type-safe `ModelSpec`

### Tool Selection

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class ToolClassifier(BaseModel):
    """
    Routes queries to appropriate tools using a fast classifier.
    
    Analyzes user query to determine which tools (if any) are needed:
    - calculator: For math expressions
    - tavily_search: For current events, web searches
    - (none): For general knowledge questions
    """
    spec: ModelSpec
    registry: ModelRegistry
    _client_cache: Agent[str, ToolDecision] | None = PrivateAttr(default=None)
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def client(self) -> Agent[str, ToolDecision]:
        """Lazy-initialized tool classifier (cached)."""
        if self._client_cache is None:
            from pydantic_ai import Agent
            model = self.spec.to_agent_model(self.registry.catalog)
            client: Agent[str, ToolDecision] = Agent(
                model,
                deps_type=str,
                output_type=ToolDecision,
                system_prompt=TOOL_ROUTER_SYSTEM_PROMPT,
            )
            object.__setattr__(self, "_client_cache", client)
            return client
        return self._client_cache
    
    async def route(self, query: str) -> list[str]:
        """
        Decide which tools are needed for the query.
        
        Returns list of tool names: ["calculator"], ["tavily_search"], 
        both, or empty list if no tools needed.
        """
        result = await self.client.run(user_prompt=query, deps=query)
        decision: ToolDecision = result.output
        
        # Validate tools exist
        from .tools import ALL_TOOLS
        valid_tools = [tool for tool in decision.tools if tool in ALL_TOOLS]
        
        return valid_tools
```

**Encapsulated Logic:**
- Lazy initialization of expensive LLM client
- Validation that requested tools exist
- Returns simple list for easy consumption
- Frozen model with private cache (safe pattern)

## Decision Models: Structured Outputs

Use Pydantic models to capture LLM decisions as typed data.

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class RouteDecision(BaseModel):
    """Model router's selection decision."""
    model: ModelRoute  # Enum: ANTHROPIC_SONNET, OPENAI_GPT5
    reasoning: str | None = None
    
    model_config = ConfigDict(frozen=True)


class ToolDecision(BaseModel):
    """Tool router's selection decision."""
    tools: list[str] = []
    reasoning: str | None = None
    
    model_config = ConfigDict(frozen=True)
```

**Why explicit decision types?**
- LLM output is validated by Pydantic
- Type-safe: Can't accidentally pass wrong enum
- Immutable: Decision can't be altered after creation
- Traceable: Can log/audit routing decisions
- Testable: Easy to mock routing for tests

## When to Use Rich Models

### ✅ DO put in domain models:

**Business Workflows:**
```python
async def send_message(self, text: str) -> Conversation:
    # Multi-step workflow with business decisions
    user_msg = self._wrap_user_input(text)
    spec = await self._select_model(user_msg)
    tools = await self._select_tools(text)
    response = await self._execute(spec, tools, user_msg)
    return self._wrap_response(response)
```

**Domain Decisions:**
```python
def resolve_or_default(self, spec: ModelSpec | None) -> ModelSpec:
    """Use provided spec or fall back to default."""
    return self.default if spec is None else self.resolve_spec(spec)
```

**State Transitions:**
```python
def append_message(self, msg: StoredMessage) -> ConversationHistory:
    """Immutable state update."""
    return self.model_copy(update={"messages": (*self.messages, msg)})
```

### ❌ DON'T put in domain models:

**Infrastructure Operations:**
```python
# ❌ Bad - Redis operations in domain
async def save_to_redis(self, host: str, port: int):
    client = Redis(host=host, port=port)
    await client.set(...)
```

**HTTP/API Concerns:**
```python
# ❌ Bad - HTTP status codes in domain
def to_response(self) -> tuple[dict, int]:
    return (self.model_dump(), 200)
```

**Service Orchestration:**
```python
# ❌ Bad - calling multiple services from domain
async def notify_all(self):
    await self.email_service.send(...)
    await self.sms_service.send(...)
```

## Benefits

**Maintainability:**
- Business logic in one place
- Changes don't ripple through services
- Easy to find what code does what

**Testability:**
```python
async def test_routing():
    # No mocks needed - pure domain logic
    conversation = Conversation.start(registry=reg, model_pool=pool, router=router)
    updated = await conversation.send_message("Hello")
    assert len(updated.history.messages) == 2
```

**Correctness:**
- Type system enforces valid states
- Immutability prevents accidental bugs
- Pydantic validates on construction

**Clarity:**
- Code reads like the business domain
- Methods map to domain concepts
- Intent is explicit

---

**See Also:**
- [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py) - Main aggregate
- [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py) - Value objects
- [`src/app/domain/model_catalog.py`](../../src/app/domain/model_catalog.py) - Configuration models
- `immutability.md` - Why frozen=True matters
- `service-patterns.md` - What goes in services instead

