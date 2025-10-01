# Immutability and Functional Patterns

> **Immutable data structures eliminate whole classes of bugs**

This document shows why and how we use immutability throughout our domain layer, with real examples from `src/app/domain/`.

> **Principle: Every State Change Returns New Data**
>
> Mutability is implicit transformation. When an object changes underneath you, there's no record of what happened, no way to compare before/after, no audit trail.
>
> Immutability forces explicitness. If `user.update()` returned `User`, you'd wonder: is it the same user? A new one? A modified copy? But if every model is `frozen=True`, there's only one possibility: new instance, old instance unchanged.
>
> This eliminates entire categories of bugs: no race conditions (nothing changes while you're reading it), no action-at-a-distance (your reference can't be modified elsewhere), no temporal coupling (order of operations doesn't matter if nothing mutates), natural audit trails (compare old and new instances).
>
> See: [philosophy.md](../philosophy.md) "Every State Change Returns New Data"

---

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

### Immutable Collections: The Pipeline Pattern

Pipeline demonstrates comprehensive immutability: frozen model + immutable collection + functional updates.

From [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py):

```python
class Pipeline(BaseModel):
    """Immutable pipeline orchestrator tracking multi-stage transformations."""
    
    stages: tuple[Stage, ...] = ()  # ← Tuple: immutable collection
    
    model_config = ConfigDict(frozen=True)  # ← Frozen: immutable model
    
    def append(self, stage: Stage) -> Pipeline:
        """Append stage immutably, returning new Pipeline instance.
        
        Immutability Pattern:
            Original pipeline unchanged. Returns new Pipeline with stage added.
            This enables time-travel debugging and safe concurrent access.
        """
        # Tuple unpacking creates new tuple with appended stage
        # model_copy returns new Pipeline instance (frozen=True prevents mutation)
        return self.model_copy(update={"stages": (*self.stages, stage)})
```

**Why this matters for complex workflows:**

```python
# Track transformation history immutably
pipeline = Pipeline()

# Stage 1: Parse
stage1 = SuccessStage(name=StageName("parse"), data=parsed_data, ...)
pipeline = pipeline.append(stage1)  # → New Pipeline with 1 stage

# Stage 2: Validate
stage2 = SuccessStage(name=StageName("validate"), data=validated_data, ...)
pipeline = pipeline.append(stage2)  # → New Pipeline with 2 stages

# Stage 3: Enrich (fails!)
stage3 = FailedStage(name=StageName("enrich"), error=ErrorMessage("API timeout"), ...)
pipeline = pipeline.append(stage3)  # → New Pipeline with 3 stages

# Can inspect any point in history
assert len(pipeline.stages) == 3
assert pipeline.failed  # True (has FailedStage)
assert pipeline.error_summary.total_errors == 1

# Original states never mutated - safe for concurrent access
```

**The pattern in practice:**

```python
def execute_stage(pipeline: Pipeline, stage_fn: Callable) -> Pipeline:
    """Execute stage function and append result to pipeline.
    
    Pipeline is immutable - original unchanged, new instance returned.
    """
    stage = stage_fn()  # Returns SuccessStage | FailedStage | SkippedStage
    return pipeline.append(stage)  # Returns new Pipeline

# Build pipeline through functional composition
pipeline = Pipeline()
pipeline = execute_stage(pipeline, parse_stage)
pipeline = execute_stage(pipeline, validate_stage)
pipeline = execute_stage(pipeline, enrich_stage)

# Each step returns new instance
# Original Pipeline() instance still has 0 stages
```

**Compared to mutable approach:**

```python
# ❌ Mutable - dangerous!
class MutablePipeline:
    def __init__(self):
        self.stages: list[Stage] = []  # Mutable!
    
    def append(self, stage: Stage) -> None:
        self.stages.append(stage)  # Mutation!

# Multiple problems
pipeline = MutablePipeline()
pipeline.append(stage1)

# Problem 1: No way to access previous state
# Problem 2: Concurrent access requires locks
# Problem 3: Hard to debug (what changed when?)
# Problem 4: Can't undo or compare states

# ✅ Immutable - safe!
pipeline = Pipeline()
pipeline_after_stage1 = pipeline.append(stage1)

# Can compare states
assert len(pipeline.stages) == 0  # Original unchanged
assert len(pipeline_after_stage1.stages) == 1  # New state

# No locks needed for concurrent reads
# Easy debugging (inspect any state)
# Can undo by keeping references to previous states
```

**Key insight:** Immutable collections (tuple) + frozen models + functional updates = complete immutability and all its benefits.

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

## Anti-Patterns: What NOT to Do

❌ **DON'T use mutable collections (list, dict, set) in frozen models**
- `messages: list[Message] = []` even with `frozen=True`
- Reality: Can still mutate the list even though model is frozen
- Use immutable collections: `tuple[Message, ...] = ()`

❌ **DON'T mutate and return self**
- `def update(self): self.value = new; return self`
- Reality: Hidden mutation, unclear if new instance or modified
- Return new instance: `return self.model_copy(update={...})`

❌ **DON'T skip frozen=True on domain models**
- "I'll just be careful not to mutate"
- Reality: Future you (or teammates) will mutate accidentally
- Always `model_config = ConfigDict(frozen=True)` for domain models

❌ **DON'T use global mutable state**
- Module-level `CACHE = {}` that gets mutated
- Reality: Race conditions, unclear ownership, hard to test
- Pass state explicitly or use immutable caching patterns

❌ **DON'T try to "optimize" by reusing instances**
- Caching model instances to avoid creating new ones
- Reality: Pydantic is fast, premature optimization, adds complexity
- Create new instances freely, optimize only if profiling shows need

❌ **DON'T mix mutable and immutable patterns**
- Some models frozen, others not, unclear which is which
- Reality: Cognitive overhead, easy to make mistakes
- Domain models always frozen, infrastructure clients mutable

❌ **DON'T use in-place operations**
- `messages.sort()`, `data.update()`, `items.append()`
- Reality: Mutates original, no trace of change
- Use functional equivalents: `sorted(messages)`, `{**data, **updates}`, `items + (new,)`

---

**See Also:**
- [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py) - Immutable value objects
- [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py) - Immutable aggregate
- [`src/app/domain/pipeline.py`](../../src/app/domain/pipeline.py) - Immutable collections pattern
- [Domain Models](domain-models.md) - Rich model patterns
- [Pipeline Pattern](pipeline-pattern.md) - Comprehensive immutability example
- [Data Flow](data-flow.md) - Traceability with immutable operations

