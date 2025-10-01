# Testing

How Pydantic and immutability radically reduce what you need to test.

---

## The Testing Efficiency Gain

Traditional codebases spend 60-70% of test code verifying things that **cannot go wrong** in this architecture. Type validation, serialization, mutation safety—all guaranteed by design.

This architecture shifts testing effort from "does this work at all?" to "does this do the right thing?"

---

## What You DON'T Test

These entire categories of tests **become unnecessary** thanks to Pydantic and frozen models:

### 1. Type Validation

**You don't test:**
```python
# ❌ Traditional testing - wasted effort
def test_conversation_id_rejects_invalid_uuid():
    with pytest.raises(ValidationError):
        ConversationId("not-a-uuid")

def test_send_message_requires_text():
    with pytest.raises(ValidationError):
        SendMessageRequest(text=None)

def test_model_spec_vendor_must_be_enum():
    with pytest.raises(ValidationError):
        ModelSpec(vendor="typo", name="...")
```

**Why:** Pydantic validates at construction. If it constructs, it's valid. If it's invalid, it won't construct. Testing this tests Pydantic, not your code.

### 2. Serialization/Deserialization

**You don't test:**
```python
# ❌ Unnecessary - Pydantic guarantees this
def test_conversation_history_serializes_to_json():
    history = ConversationHistory(...)
    json_str = history.model_dump_json()
    assert json_str  # Will always work

def test_conversation_history_round_trips():
    original = ConversationHistory(...)
    data = original.model_dump()
    restored = ConversationHistory(**data)
    assert original == restored  # Guaranteed by Pydantic
```

**Why:** `model_dump()`, `model_dump_json()`, and `model_validate()` are Pydantic core functionality. They work correctly or Pydantic itself is broken.

### 3. Immutability Violations

**You don't test:**
```python
# ❌ Impossible with frozen=True
def test_conversation_history_append_doesnt_mutate():
    history = ConversationHistory(messages=(...))
    original_length = len(history.messages)
    history.append_message(msg)  # Won't compile/will raise
    assert len(history.messages) == original_length
```

**Why:** Frozen models raise `ValidationError` on attempted mutation. The type system prevents this at write-time, not run-time.

### 4. Field Constraints

**You don't test:**
```python
# ❌ Redundant - field validators handle this
def test_message_text_max_length():
    with pytest.raises(ValidationError):
        SendMessageRequest(text="x" * 100_000)

def test_model_spec_name_not_empty():
    with pytest.raises(ValidationError):
        ModelSpec(vendor=AIModelVendor.ANTHROPIC, name="")
```

**Why:** `Field(max_length=10_000)`, `Field(min_length=1)` are Pydantic validators. Trust the framework.

---

## What You DO Test

Focus testing effort on the **unique value** your code provides:

### 1. Business Logic

**Test the transformations:**
```python
def test_conversation_appends_message_immutably():
    """Verify append_message returns new instance with message added."""
    history = ConversationHistory.empty()
    msg = StoredMessage(...)
    
    new_history = history.append_message(msg)
    
    assert new_history is not history  # Different instance
    assert len(new_history.messages) == 1
    assert new_history.messages[0] == msg
```

**Test domain methods:**
```python
def test_model_classifier_selects_fastest_available_model():
    """Verify classifier picks Haiku when Anthropic key present."""
    registry = ModelRegistry(...)  # Has Anthropic key
    classifier = ModelClassifier(registry=registry)
    
    spec = classifier.select_fast_model()
    
    assert spec.vendor == AIModelVendor.ANTHROPIC
    assert spec.name == "claude-3-5-haiku-20241022"
```

### 2. Orchestration Logic

**Test services coordinate correctly:**
```python
async def test_conversation_service_persists_history():
    """Verify service calls domain.save() after domain operation."""
    # Setup mocks for Redis
    conversation = await service.send_message(conv_id, "Hello")
    
    # Assert domain save was called with correct data
    assert redis_client.set.called
```

### 3. Integration Behavior

**Test that layers compose:**
```python
async def test_send_message_endpoint_returns_streamed_response():
    """Verify API layer correctly streams domain response."""
    response = client.post("/conversations/123/messages", json={"text": "Hi"})
    
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
```

---

## Testing Superpowers

Pydantic enables testing patterns that are difficult or impossible in traditional codebases.

### 1. Property-Based Testing

Generate random valid models and assert invariants hold:

```python
from hypothesis import given, strategies as st

@given(st.builds(ConversationHistory))
def test_append_message_always_increases_length(history):
    """Property: appending always adds exactly one message."""
    msg = StoredMessage(...)
    new_history = history.append_message(msg)
    assert len(new_history.messages) == len(history.messages) + 1

@given(st.builds(ModelSpec))
def test_model_spec_always_has_valid_vendor(spec):
    """Property: vendor is always a valid enum member."""
    assert isinstance(spec.vendor, AIModelVendor)
```

**Why this works:** `st.builds(ConversationHistory)` auto-generates valid instances. You test behavior across entire input space, not hand-picked examples.

### 2. Schema-Based Contract Testing

Assert API contracts match expectations:

```python
def test_send_message_response_schema_stable():
    """Verify API response schema hasn't changed (prevents breaking clients)."""
    schema = SendMessageResponse.model_json_schema()
    
    assert "message_id" in schema["properties"]
    assert schema["properties"]["text"]["type"] == "string"
    assert schema["required"] == ["message_id", "text", "timestamp"]
```

**Why this works:** Pydantic models define the contract. The schema is the test oracle.

### 3. Model Factories

Valid test data for free:

```python
def conversation_factory(**overrides) -> Conversation:
    """Create valid Conversation with sensible defaults."""
    defaults = {
        "id": ConversationId.generate(),
        "history": ConversationHistory.empty(),
        # ... other required fields
    }
    return Conversation(**(defaults | overrides))

def test_conversation_send_message():
    # Valid by construction, focus on behavior
    conv = conversation_factory()
    result = conv.send_message("Hello")
    assert result.text
```

**Why this works:** Pydantic validates construction. Factories give you valid test objects without manual field setup.

---

## Testing Patterns by Layer

### Domain Models

**What to test:** Business logic, state transformations, invariants

```python
def test_conversation_history_rejects_duplicate_message_ids():
    """Domain rule: message IDs must be unique."""
    # Test will go here - focuses on business rule
    pass

def test_model_pool_reuses_cached_models():
    """Performance invariant: same (spec, tools) returns same Agent."""
    # Test will go here - focuses on caching behavior
    pass
```

**What NOT to test:** Field validation (Pydantic), serialization (Pydantic), type safety (mypy)

### Service Layer

**What to test:** Orchestration logic, error handling, dependency coordination

```python
async def test_conversation_service_handles_missing_conversation():
    """Service returns 404 when conversation doesn't exist."""
    # Test will go here - focuses on error path
    pass

async def test_conversation_service_passes_registry_to_domain():
    """Service provides domain with needed dependencies."""
    # Test will go here - focuses on DI
    pass
```

**What NOT to test:** Request/response validation (Pydantic contracts), domain business logic (tested in domain layer)

### API Layer

**What to test:** HTTP concerns, status codes, streaming, error formatting

```python
async def test_health_endpoint_returns_200():
    """Verify API is reachable."""
    # Test will go here
    pass

async def test_send_message_streams_events():
    """Verify SSE streaming works correctly."""
    # Test will go here
    pass
```

**What NOT to test:** Domain logic (tested in domain), orchestration (tested in service)

---

## Test Organization

```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_conversation.py       # ConversationHistory immutability
│   │   └── test_model_catalog.py      # ModelRegistry, ModelSpec
│   └── service/
│       └── test_conversation_service.py
├── integration/
│   ├── test_conversation_api.py       # End-to-end API tests (real LLM calls)
│   ├── test_health.py                 # Smoke tests
│   └── test_persistence.py            # Redis round-trips
└── conftest.py                         # Shared fixtures
```

**Principle:** Test each layer independently at its own level of abstraction.

---

## Benefits of This Approach

**1. Less Test Code**
- No validation tests → 40% fewer tests
- No serialization tests → 20% fewer tests
- No mutation tests → 10% fewer tests
- **70% reduction in test surface area**

**2. Higher-Value Tests**
- Every test verifies business logic, not framework behavior
- Property-based tests find edge cases you'd never think of
- Schema tests catch breaking changes automatically

**3. Faster Feedback**
- Many bugs caught at construction time (type errors, validation)
- Tests run faster (fewer of them)
- Type checker (mypy) catches issues before tests run

**4. Maintainability**
- Tests document domain behavior, not technical details
- Fewer tests to update when implementation changes
- Clear separation: domain tests vs service tests vs API tests

---

## Anti-Patterns to Avoid

### ❌ Testing Pydantic

```python
# Don't do this
def test_conversation_id_is_uuid():
    conv_id = ConversationId.generate()
    assert isinstance(conv_id.root, UUID)  # Pydantic guarantees this
```

### ❌ Testing Immutability

```python
# Don't do this
def test_frozen_model_raises_on_mutation():
    history = ConversationHistory(...)
    with pytest.raises(ValidationError):
        history.messages = []  # frozen=True guarantees this
```

### ❌ Testing Framework Serialization

```python
# Don't do this
def test_model_round_trips_through_json():
    model = MyModel(...)
    json_str = model.model_dump_json()
    restored = MyModel.model_validate_json(json_str)
    assert model == restored  # Pydantic's job, not yours
```

### ✅ Instead, Test Your Logic

```python
# Do this
def test_conversation_maintains_message_order():
    """Business rule: messages appear in chronological order."""
    history = ConversationHistory.empty()
    msg1 = StoredMessage(..., timestamp=100)
    msg2 = StoredMessage(..., timestamp=200)
    
    history = history.append_message(msg1).append_message(msg2)
    
    assert history.messages[0].timestamp < history.messages[1].timestamp
```

---

## Implementation Examples

This codebase demonstrates these principles in practice:

### Unit Tests
- [`tests/unit/domain/test_conversation.py`](../../tests/unit/domain/test_conversation.py) - ConversationHistory immutability and message appending
- [`tests/unit/domain/test_model_catalog.py`](../../tests/unit/domain/test_model_catalog.py) - ModelRegistry deduplication, spec equality, catalog loading

### Integration Tests
- [`tests/integration/test_conversation_api.py`](../../tests/integration/test_conversation_api.py) - End-to-end API tests hitting real Docker stack
- [`tests/integration/test_health.py`](../../tests/integration/test_health.py) - Fast smoke tests for API availability

### End-to-End Testing Strategy

The integration tests demonstrate **true end-to-end testing**:
- Hit the real running API at `http://localhost:8000` (not TestClient)
- Use real Redis for state persistence
- Make real LLM API calls to Anthropic/OpenAI
- Verify complete business flows (create conversation, continue conversation, retrieve metadata)

**Why real infrastructure?** These tests catch integration bugs that mocks hide. They're slower (~18 seconds for 7 tests) but prove the system actually works.

**Real bug caught:** The integration test `test_create_conversation_with_provided_id` revealed that providing a `conversation_id` that didn't exist would return 404 instead of creating a new conversation with that ID. This is an idempotent API design issue that unit tests wouldn't catch—it required testing the full API contract end-to-end.

**Trade-off:** Fast unit tests (milliseconds) verify domain logic. Slow integration tests (seconds) verify the stack integrates correctly. Both are necessary.

---

## See Also

- [Domain Models](domain-models.md) - What to test in domain layer
- [Service Patterns](service-patterns.md) - What to test in service layer
- [Immutability](immutability.md) - Why mutation tests are unnecessary
- [Type System](type-system.md) - How types eliminate validation tests

