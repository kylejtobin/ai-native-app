# Data Flow and Traceability

> **Every operation is an explicit transformation with traceable state changes**

This document shows how our architecture creates clear, traceable data flow using real examples from the codebase.

## Explicit Transformation Pipeline

Traditional code obscures how data changes. Our approach makes every transformation explicit.

### The Full Conversation Flow

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
    
    Execution Flow:
        1. Wrap user text in StoredMessage with ID
        2. Phase 1a: Model Selection (if auto_route enabled)
        3. Phase 1b: Tool Selection (if auto_route enabled)
        4. Phase 2: Execution
        5. Wrap response message(s) with IDs
        6. Return new Conversation instance (immutable update)
    """
    # === Step 1: Wrap User Input ===
    user_msg = StoredMessage(
        id=MessageId(),
        content=ModelRequest(parts=[UserPromptPart(content=text)]),
    )
    
    # Immutably append to history (returns new ConversationHistory)
    updated_history = self.history.append_message(user_msg)
    
    # === Phase 1a: Model Selection (Fast → Strong) ===
    if auto_route and spec is None and self.router:
        spec = await self.router.route(updated_history)
    
    if spec is None:
        spec = self.registry.default
    
    # === Phase 1b: Tool Selection (Fast → Filtered) ===
    tool_names: list[str] | None = None
    if auto_route and self.tool_router:
        tool_names = await self.tool_router.route(text)
    
    # === Phase 2: Execute with Selected Model + Tools ===
    model = self.model_pool.get_model(spec, tool_names=tool_names)
    
    result = await model.run(
        deps=updated_history,
        message_history=list(updated_history.message_content),
        model_settings=settings,
    )
    
    # === Step 3: Process Response Messages ===
    response_messages = [
        StoredMessage(id=MessageId(), content=msg) 
        for msg in result.new_messages()
    ]
    
    # Immutably append all response messages to history
    final_history = updated_history
    for response_msg in response_messages:
        final_history = final_history.append_message(response_msg)
    
    # === Step 4: Return New Conversation ===
    return self.model_copy(update={"history": final_history})
```

**Every arrow is explicit:**
```
text → StoredMessage → updated_history → routing → spec → model → result → response_messages → final_history → new_Conversation
```

## Tracing State Through Layers

The data flows through our architecture with clear transformations at each boundary.

### Layer 1: HTTP → API Contract

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
@router.post("/", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,  # ← HTTP JSON → Pydantic model
    ...
) -> SendMessageResponse:
```

**Transformation:** Raw HTTP JSON → validated `SendMessageRequest`

### Layer 2: API → Domain

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
# Load or start conversation
if request.conversation_id:
    conversation = await Conversation.load(
        conv_id=request.conversation_id,
        redis=redis,
        registry=registry,
        model_pool=model_pool,
    )
else:
    conversation = Conversation.start(
        registry=registry,
        model_pool=model_pool,
    )

# Execute domain logic
updated_conversation = await conversation.send_message(
    text=request.text,
    spec=spec,
    settings=None,
    auto_route=request.auto_route,
)
```

**Transformation:** `SendMessageRequest` → `Conversation` → `updated_Conversation`

### Layer 3: Domain → Persistence

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
# Persist updated conversation (domain owns serialization)
await updated_conversation.save(redis)
```

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
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

**Transformation:** `Conversation` → JSON string → Redis

### Layer 4: Domain → API Contract

From [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py):

```python
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

**Transformation:** `Conversation` → `SendMessageResponse` → HTTP JSON

## Immutable State Transitions

Each operation returns a new state, creating a traceable history.

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
def append_message(self, msg: StoredMessage) -> ConversationHistory:
    """Append Message Immutably.
    
    Functional update pattern: creates new ConversationHistory with added message.
    Original instance remains unchanged, enabling safe concurrent access.
    """
    return self.model_copy(update={"messages": (*self.messages, msg)})
```

**The flow:**
```python
history1 = ConversationHistory(id=conv_id)  # State 1: 0 messages
history2 = history1.append_message(user_msg)  # State 2: 1 message
history3 = history2.append_message(response_msg)  # State 3: 2 messages

# Can compare any two states
assert len(history1.messages) == 0  # Original unchanged
assert len(history2.messages) == 1  # After user message
assert len(history3.messages) == 2  # After response
```

## Multi-Step Operations Are Explicit

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
# === Step 3: Process Response Messages ===
# Wrap ALL response messages with identity for persistence
# Important: When tools are invoked, result.new_messages() returns multiple messages:
#   1. ModelRequest with tool call(s)
#   2. ModelResponse with tool return(s)
#   3. ModelResponse with final text answer
response_messages = [
    StoredMessage(id=MessageId(), content=msg) 
    for msg in result.new_messages()
]

# Immutably append all response messages to history
final_history = updated_history
for response_msg in response_messages:
    final_history = final_history.append_message(response_msg)
```

**Why explicit loop instead of bulk append?**
- Each message gets its own `MessageId`
- Each append is a traceable state transition
- Can inspect intermediate states if debugging
- Makes the multi-message nature explicit

## Loading and Persisting State

Domain models own their serialization strategy.

### Loading from Redis

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
```

**Transformation:** Redis bytes → JSON → `ConversationHistory` → `Conversation`

### Saving to Redis

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
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

**Transformation:** `Conversation` → `ConversationHistory` → JSON → Redis bytes

**Key insight:** Infrastructure provides the client, domain owns the format.

## Complete End-to-End Flow

Let's trace a single request through the entire system:

```
1. HTTP Request
   POST /conversation/
   {"text": "What is 5 + 3?"}
   
2. API Layer Validates
   → SendMessageRequest(text="What is 5 + 3?")
   
3. Domain Layer: Start Conversation
   → Conversation.start(registry, pool)
   → Conversation(history=ConversationHistory(messages=()))
   
4. Domain Layer: Add User Message
   → StoredMessage(id=MessageId(), content=ModelRequest(...))
   → updated_history = history.append_message(user_msg)
   → updated_history.messages = (StoredMessage_1,)
   
5. Domain Layer: Route Model
   → router.route(updated_history)
   → spec = ModelSpec(vendor=AIModelVendor.ANTHROPIC, variant_id="claude-sonnet...")
   
6. Domain Layer: Route Tools
   → tool_router.route("What is 5 + 3?")
   → tool_names = ["calculator"]
   
7. Domain Layer: Execute
   → model = model_pool.get_model(spec, ["calculator"])
   → result = await model.run(...)
   → result.new_messages() = [tool_call_msg, tool_return_msg, response_msg]
   
8. Domain Layer: Wrap Responses
   → response_messages = [StoredMessage(id=..., content=msg) for msg in ...]
   → final_history = updated_history
   → final_history = final_history.append_message(response_1)  # tool call
   → final_history = final_history.append_message(response_2)  # tool return
   → final_history = final_history.append_message(response_3)  # final answer
   → final_history.messages = (user_msg, tool_call, tool_return, response)
   
9. Domain Layer: Return New State
   → new_conversation = self.model_copy(update={"history": final_history})
   
10. API Layer: Persist
    → await new_conversation.save(redis)
    → key = "conversation:{uuid}"
    → data = final_history.model_dump_json()
    → await redis.set(key, data)
    
11. API Layer: Extract Response
    → last_message = new_conversation.history.messages[-1]
    → response_text = last_message.content.parts[0].content
    → response_text = "8"
    
12. API Layer: Map to Contract
    → SendMessageResponse(
         conversation_id=ConversationId(...),
         message=MessageResponse(content="8"),
         total_tokens=1234
       )
       
13. HTTP Response
    {
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
      "message": {"content": "8"},
      "total_tokens": 1234
    }
```

**Every transformation is explicit and traceable.**

## Benefits

### Debuggability

Can inspect state at any point:

```python
# Insert logging at any step
logger.info(f"After user message: {len(updated_history.messages)} messages")
logger.info(f"Selected model: {spec.variant_id}")
logger.info(f"Selected tools: {tool_names}")
logger.info(f"After execution: {len(final_history.messages)} messages")
```

### Auditability

Complete record of what happened:

```python
# Can reconstruct exact state
conversation = await Conversation.load(conv_id, redis, registry, pool)

# Can inspect history
for msg in conversation.history.messages:
    print(f"ID: {msg.id.root}")
    print(f"Type: {type(msg.content).__name__}")
    print(f"Content: {msg.content}")
```

### Testability

Each transformation is independently testable:

```python
# Test domain logic without HTTP
conversation = Conversation.start(registry, pool)
updated = await conversation.send_message("Hello")
assert len(updated.history.messages) == 2

# Test serialization without domain logic
history = ConversationHistory(id=ConversationId(), messages=())
json_data = history.model_dump_json()
restored = ConversationHistory.model_validate_json(json_data)
assert restored == history
```

### Correctness

Type system enforces valid transformations:

```python
# ✅ Type-safe - can only pass ConversationId
conversation = await Conversation.load(
    conv_id=ConversationId(root=uuid),  # ← Must be ConversationId
    redis=redis,
    registry=registry,
    model_pool=pool,
)

# ❌ Type error - can't pass UUID directly
conversation = await Conversation.load(
    conv_id=uuid,  # ← Type error!
    ...
)
```

---

**See Also:**
- [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py) - Full flow implementation
- [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py) - Immutable state
- [`src/app/api/routers/conversation.py`](../../src/app/api/routers/conversation.py) - HTTP layer
- `immutability.md` - Why immutability enables traceability
- `domain-models.md` - Domain logic organization

