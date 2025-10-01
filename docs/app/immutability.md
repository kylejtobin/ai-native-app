# Immutability and Functional Patterns

> **Immutable data structures eliminate whole classes of bugs**

This document shows why and how we use immutability throughout our domain layer, with real examples from `src/app/domain/`.

## Why Immutability?

### Problem: Hidden Mutations

```python
# ❌ Dangerous - what changed?
async def process_conversation(conversation):
    conversation.add_message("Hello")  # Mutates
    await classify(conversation)  # Might mutate
    await route(conversation)  # Might mutate
    await execute(conversation)  # Definitely mutates
    return conversation  # What is this now?
```

**Issues:**
- Can't trace what changed where
- Concurrent access requires locks
- Testing requires deep copies
- Debugging is painful
- Race conditions lurk

### Solution: Explicit State Transitions

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
async def send_message(self, text: str) -> Conversation:
    """Returns NEW Conversation - original unchanged."""
    # 1. Add user message (returns new history)
    user_msg = StoredMessage(id=MessageId(), content=ModelRequest(...))
    updated_history = self.history.append_message(user_msg)
    
    # 2. Route and execute
    spec = await self.router.route(updated_history)
    model = self.model_pool.get_model(spec)
    result = await model.run(...)
    
    # 3. Add response messages (returns new history)
    final_history = updated_history
    for msg in result.new_messages():
        final_history = final_history.append_message(StoredMessage(...))
    
    # 4. Return NEW Conversation with updated history
    return self.model_copy(update={"history": final_history})
```

**Every step returns a new instance. Original `self` never changes.**

## The Core Pattern: `frozen=True`

All domain models are immutable via Pydantic's `frozen` config.

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class ConversationHistory(BaseModel):
    """Complete Conversation State for Persistence."""
    
    id: ConversationId
    messages: tuple[StoredMessage, ...] = ()  # ← Tuple, not list!
    status: ConversationStatus = ConversationStatus.ACTIVE
    
    model_config = ConfigDict(frozen=True)  # ← Can't mutate after construction
```

**What `frozen=True` prevents:**
```python
history = ConversationHistory(id=conv_id)

# ❌ All of these fail with FrozenInstanceError
history.messages = [new_msg]
history.messages.append(new_msg)  # Even if it was a list
history.status = ConversationStatus.ARCHIVED
```

## Immutable Updates: `model_copy(update={})`

Pydantic's `model_copy` creates a new instance with specific fields changed.

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
def append_message(self, msg: StoredMessage) -> ConversationHistory:
    """Append Message Immutably.
    
    Functional update pattern: creates new ConversationHistory with added message.
    Original instance remains unchanged, enabling safe concurrent access.
    
    Example:
        >>> history1 = ConversationHistory(id=ConversationId())
        >>> history2 = history1.append_message(msg)
        >>> len(history1.messages)  # 0 - original unchanged
        >>> len(history2.messages)  # 1 - new instance has message
    """
    return self.model_copy(update={"messages": (*self.messages, msg)})
```

**The tuple unpacking trick:**
```python
(*self.messages, msg)  # Creates new tuple with all old messages + new one
```

This is:
- **Efficient**: Shallow copy, references same message objects
- **Explicit**: Clear that we're creating new state
- **Safe**: Original can't be corrupted

## Why Tuple Instead of List?

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
class ConversationHistory(BaseModel):
    messages: tuple[StoredMessage, ...] = ()  # ← Tuple!
```

**Why tuple enforces immutability:**
- `tuple` has no `append()`, `insert()`, or `remove()` methods
- Item assignment raises `TypeError`
- Pydantic validates immutability
- Python's type system helps catch mutations

**Convert to list only at boundaries:**

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
# Domain: immutable tuple
result = await model.run(
    message_history=list(updated_history.message_content)  # ← Boundary conversion
)
```

We convert tuple → list ONLY when calling Pydantic AI, which expects a list.

## Functional Composition: Chaining Operations

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
async def send_message(self, text: str) -> Conversation:
    """Each operation returns new state."""
    
    # Start with current history
    updated_history = self.history.append_message(user_msg)  # → new history
    
    # Process response messages
    final_history = updated_history
    for response_msg in response_messages:
        final_history = final_history.append_message(response_msg)  # → new history each time
    
    # Return new Conversation
    return self.model_copy(update={"history": final_history})  # → new Conversation
```

**Usage shows explicit state progression:**
```python
conversation = Conversation.start(registry, pool)  # Initial state
conversation = await conversation.send_message("Hello")  # State 2
conversation = await conversation.send_message("How are you?")  # State 3
conversation = await conversation.send_message("Goodbye")  # State 4

# Can compare any two states
assert len(conversation.history.messages) == 6  # 3 user + 3 assistant
```

## Concurrency Safety

Because `Conversation` is immutable (`frozen=True`), multiple async tasks can safely read from the same instance without locks. Each call to `send_message()` returns a new instance, so concurrent operations never interfere with each other.

## Lazy Initialization with Frozen Models

Use `PrivateAttr` and `object.__setattr__` for caching on frozen models.

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class ModelClassifier(BaseModel):
    """Routes queries to appropriate models using a fast classifier."""
    
    spec: ModelSpec
    registry: ModelRegistry
    _client_cache: Agent[ConversationHistory, RouteDecision] | None = PrivateAttr(default=None)
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def client(self) -> Agent[ConversationHistory, RouteDecision]:
        """Lazy-initialized classifier (cached).
        
        Frozen model pattern: Use object.__setattr__ to cache in private field.
        """
        if self._client_cache is None:
            from pydantic_ai import Agent
            
            model = self.spec.to_agent_model(self.registry.catalog)
            client: Agent[ConversationHistory, RouteDecision] = Agent(
                model,
                deps_type=ConversationHistory,
                output_type=RouteDecision,
                system_prompt=MODEL_ROUTER_SYSTEM_PROMPT,
            )
            # Special: Can mutate private attrs even on frozen models
            object.__setattr__(self, "_client_cache", client)
            return client
        return self._client_cache
```

**Why this works:**
- `PrivateAttr` fields aren't part of model's data
- `object.__setattr__` bypasses Pydantic's frozen check
- Only works for private fields (start with `_`)
- Caching expensive objects (LLM clients) on first access
- Model remains conceptually immutable to users

## Practical Guidelines

### ✅ DO:

**Use tuple for collections:**
```python
class ConversationHistory(BaseModel):
    messages: tuple[StoredMessage, ...] = ()  # ✅
```

**Return new instances:**
```python
def append_message(self, msg: StoredMessage) -> ConversationHistory:
    return self.model_copy(update={"messages": (*self.messages, msg)})  # ✅
```

**Use frozen models:**
```python
model_config = ConfigDict(frozen=True)  # ✅
```

**Convert at boundaries:**
```python
await model.run(message_history=list(self.message_content))  # ✅ tuple→list
```

### ❌ DON'T:

**Use list in domain:**
```python
class ConversationHistory(BaseModel):
    messages: list[StoredMessage] = []  # ❌ Mutable!
```

**Mutate self:**
```python
def append_message(self, msg: StoredMessage) -> None:
    self.messages.append(msg)  # ❌ Mutation!
```

**Return None from operations:**
```python
def append_message(self, msg: StoredMessage) -> None:  # ❌ No return
    self.messages = (*self.messages, msg)
```

**Skip frozen:**
```python
model_config = ConfigDict(frozen=False)  # ❌ Allows mutation
```

## Performance Considerations

**Myth:** "Immutability is slow because of copying"

**Reality:**
- Pydantic's `model_copy` is optimized
- Python uses structural sharing (references)
- Copies are shallow by default
- Tuple unpacking reuses references

**Actual cost:**
```python
# This doesn't copy message objects themselves
new_history = history.model_copy(update={
    "messages": (*history.messages, new_msg)
})
# Only creates:
# 1. New ConversationHistory instance
# 2. New tuple with N+1 references
# 3. All message objects are REUSED (same memory)
```

**When immutability costs too much:**
- Millions of operations per second (hot loops)
- Gigabyte-sized collections
- Need to measure first (profile before optimizing)

**For 99% of code:** The safety, clarity, and debuggability of immutability are worth any minimal cost.

## Real-World Example: Full Flow

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
# Each line returns NEW instance
conversation = Conversation.start(registry, pool)  # Empty history
conversation = await conversation.send_message("Hello")  # +2 messages
conversation = await conversation.send_message("What is 5+3?")  # +4 messages (tool use)
conversation = await conversation.send_message("Thanks!")  # +2 messages

# Total: 8 messages (4 user, 4 assistant+tool)
# Original Conversation.start() result still has 0 messages
# Each intermediate state still accessible if we saved it
```

---

**See Also:**
- [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py) - Immutable value objects
- [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py) - Immutable aggregate
- `domain-models.md` - Rich model patterns
- `data-flow.md` - Traceability with immutable operations

