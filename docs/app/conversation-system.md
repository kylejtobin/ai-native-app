# Conversation System Architecture

> **A guide to understanding the intelligent conversation system's design, patterns, and principles.**

## Overview

This system implements a production-ready LLM conversation system with intelligent routing, efficient caching, and clean separation of concerns. The design prioritizes cost optimization, type safety, and developer experience.

**Key Capabilities:**
- Two-phase routing (fast model selects, strong model executes)
- Dynamic tool selection (calculator, web search)
- Conversation persistence and state management
- Multi-model support with hot-swapping
- Configuration-driven model catalog

## Table of Contents

1. [Two-Phase Routing: The Core Innovation](#two-phase-routing-the-core-innovation)
2. [Identity and State Management](#identity-and-state-management)
3. [Model Pool: Connection Caching Strategy](#model-pool-connection-caching-strategy)
4. [Model Catalog: Configuration Over Code](#model-catalog-configuration-over-code)
5. [Tool System](#tool-system)
6. [Immutability and Functional Updates](#immutability-and-functional-updates)
7. [Implementation Guide](#implementation-guide)

---

## Two-Phase Routing: The Core Innovation

### The Problem

**Different queries need different strong models.** Some need Sonnet's deep reasoning (complex analysis), others work fine with GPT-5 (general knowledge). Picking the wrong one wastes capability or costs extra.

**Too many tools degrade quality.** Loading calculator + search + other tools into every request increases context size and causes hallucinations.

### The Solution

Use a **fast classifier to make smart decisions** before executing with the strong model:

```
User: "What is 5 factorial times 8?"
         ↓
    Phase 1a: Model Classification
    Fast model from active vendor (Haiku ~$0.0001):
    "Math reasoning → Route to Sonnet"
         ↓
    Phase 1b: Tool Classification  
    Fast model from active vendor (Haiku ~$0.0001):
    "Needs calculator, not search"
         ↓
    Phase 2: Execution
    Strong model (Sonnet ~$0.003):
    Execute with ONLY calculator tool
```

### Why This Works

**Smart Model Selection:**
- Classification overhead: ~$0.0002 per query (2 fast model calls)
- Always executes with strong model, just picks the RIGHT one
- Sonnet for complex reasoning, GPT-5 for general knowledge
- Fast model dynamically selected from active vendor's family

**Quality Improvement:**
- Smaller tool context = better tool selection accuracy
- Right strong model for task = better answers
- Focused execution = fewer errors

**Cost Efficiency:**
- Cheap classification (~$0.0002) to optimize expensive execution (~$0.003+)
- ROI: Picking optimal strong model pays for classification
- Using vendor's fast model for classification keeps latency low

### Implementation

Both classifiers follow the same pattern:
1. **Fast model** from active vendor's family acts as classifier
2. Returns **structured output** (Pydantic model with decision)
3. **Validates** decision against available routes/tools
4. **Falls back** to safe defaults if needed
5. Classifier clients are **cached** for reuse

**Key Insight:** We use the fast model (e.g., Haiku from Anthropic) for classification, then ALWAYS execute with a strong model (Sonnet or GPT-5). The classification picks WHICH strong model to use, not whether to use a strong model.

**Code:** `src/app/domain/conversation.py` - See `ModelClassifier` and `ToolClassifier` classes, and `Conversation.send_message()` orchestration.

---

## Identity and State Management

### The Challenge

We need to persist conversations, but LLM frameworks provide content types without persistence identifiers. We need:
- Database/Redis keys (UUIDs)
- Message-level operations (edit, delete, reference)
- Conversation lifecycle (active, archived, deleted)

### The Architecture

Three distinct layers that compose cleanly:

```
Identity Layer (Domain)
├─ MessageId: UUID for each message
├─ ConversationId: UUID for each conversation
└─ ConversationStatus: Lifecycle enum

Composition Layer (Domain)
├─ StoredMessage: MessageId + content
└─ ConversationHistory: ConversationId + messages + status

Content Layer (Pydantic AI)
├─ ModelMessage: Request | Response union
├─ ModelRequest: User/system prompts
└─ ModelResponse: LLM replies with token usage
```

### Key Insight: Separation of Concerns

**Identity** answers: "Which message/conversation?"  
**Content** answers: "What was said?"  
**Metadata** answers: "What's the state?"

We add exactly one wrapper (`StoredMessage`) that composes identity with content. The content itself remains the Pydantic AI types unchanged.

### Bridging to LLM Framework

`ConversationHistory` has a property that extracts content:

```python
@property
def message_content(self) -> tuple[ModelMessage, ...]:
    """Strip identity layer, return pure content for LLM."""
    return tuple(msg.content for msg in self.messages)
```

This is the **only adaptation** needed. When calling Pydantic AI:

```python
result = await agent.run(
    message_history=list(history.message_content),  # tuple → list
)
```

**Code:** `src/app/domain/domain_value.py` - Identity types and composition models.

---

## Model Pool: Connection Caching Strategy

### Understanding Model Client Lifecycle

**Wrong Mental Model:** "Create new model client for each conversation"  
**Correct Mental Model:** "Reuse one client per (model, tools) across ALL conversations"

### Why This Works

Model clients wrap HTTP connections (OpenAI/Anthropic SDKs):
- HTTP client creation: ~500ms (connection pooling, auth setup)
- Clients are **stateless executors**
- Conversation history passed per-call via parameters
- One client instance can safely serve thousands of conversations

### Cache Key Design

**Simple approach:** One client per model  
**Our approach:** One client per (model, tools) combination

Why? With tool routing, we need:
- `(Sonnet, [calculator])` → Client A
- `(Sonnet, [search])` → Client B  
- `(Sonnet, [calculator, search])` → Client C
- `(Sonnet, [])` → Client D

Each combination is cached separately for instant reuse.

### Two Orthogonal Caches

```
ModelPool (In-Memory, Process Lifetime)
- Key: (ModelSpec, frozenset[tool_names])
- Value: Model client instances
- Scope: Shared across ALL users
- Purpose: Avoid expensive HTTP client recreation

Redis (Persistent)
- Key: ConversationId
- Value: ConversationHistory (JSON)
- Scope: Per-user, per-conversation
- Purpose: Conversation state storage
```

These solve different problems and never intersect.

**Performance Impact:**
- Without pooling: 500ms × every query = terrible
- With pooling: <1ms lookup × most queries = excellent

**Code:** `src/app/domain/model_pool.py` - See `ModelPool` class with detailed caching docs.

---

## Model Catalog: Configuration Over Code

### The Problem

Hard-coding model IDs creates brittleness:
- Code changes when providers update models
- Same information duplicated everywhere
- Difficult to manage aliases
- No single source of truth

### The Solution: Metadata-Driven

**Single Source:** `src/app/domain/model_metadata.json`

```json
{
  "anthropic": {
    "available_models": [
      {
        "id": "claude-sonnet-4-5-20250929",
        "aliases": ["claude-sonnet-4.5"],
        "tier_class": "standard",
        "notes": "Latest Sonnet - best balance"
      }
    ]
  }
}
```

**Loading Flow:**
```
model_metadata.json
    ↓ Load & Parse
ModelCatalog (type-safe, validated)
    ↓ Filter & Allow-list
ModelRegistry (runtime-specific)
    ↓ Reference
ModelSpec (normalized identifier)
```

### Key Benefits

**O(1) Lookups:**
- Pre-computed dictionaries, no searching
- Pydantic caches computed fields on frozen models
- Instant resolution: alias → full model info

**Flexible Identifiers:**
All of these resolve to the same model:
- `"claude-sonnet-4-5-20250929"` (full ID)
- `"claude-sonnet-4.5"` (alias)
- Both work transparently

**Type Safety:**
- Pydantic validates all fields on load
- Detects duplicate identifiers
- Enum-based vendor keys (not strings)

**Runtime Flexibility:**
- **ModelCatalog**: "What exists globally?"
- **ModelRegistry**: "What can I use now?" (filters by API keys present)
- **ModelSpec**: "Which specific model?" (normalized reference)

**Code:** `src/app/domain/model_catalog.py` and `model_metadata.json`.

---

## Tool System

### Architecture

Tools are simply **async functions with type hints and docstrings**. Pydantic AI generates the schema automatically from the function signature.

**Current Tools:**
- `calculator()` - Safe math expression evaluation (AST-based, no eval)
- `tavily_search()` - AI-powered web search

**Tool Registry:**
```python
ALL_TOOLS = {
    "calculator": calculator,
    "tavily_search": tavily_search,
}
```

### How Tool Selection Works

1. ToolClassifier analyzes query: `"What is 5 factorial?"`
2. Returns tool list: `["calculator"]`
3. ModelPool fetches model: `get_model(spec, tools=["calculator"])`
4. Model executes with **only calculator** in context

### Why This Matters

**Without tool selection:**
```
Model has: [calculator, search, file_ops, database, ...]
LLM sees: 5 tool descriptions in context
Result: Sometimes picks wrong tool, wastes tokens
```

**With tool selection:**
```
Model has: [calculator]
LLM sees: 1 tool description
Result: Always picks correctly, minimal context
```

### Tool Response Handling

When tools are invoked, `result.new_messages()` returns **multiple messages:**
1. ModelRequest with tool call(s)
2. ModelResponse with tool return value(s)
3. ModelResponse with final text answer

Our code handles this by wrapping ALL messages with IDs for persistence.

**Code:** `src/app/domain/tools.py` - Tool implementations with extensive inline docs.

---

## Immutability and Functional Updates

### The Pattern

**All domain models are frozen:**
```python
model_config = ConfigDict(frozen=True)
```

**Operations return new instances** instead of mutating:
```python
# Wrong (throws TypeError)
conversation.history.messages.append(msg)  # ❌

# Correct (functional update)
new_history = conversation.history.append_message(msg)  # ✅
```

### Why Immutability?

**Concurrency Safety:**
- Multiple async tasks read same data safely
- No locks or synchronization needed
- No race conditions possible

**Debuggability:**
- Can compare before/after states
- Old instances remain unchanged
- Clear data lineage

**Functional Composition:**
```python
conv = Conversation.start(...)
conv = await conv.send_message("Hello")  # New instance
conv = await conv.send_message("World")  # Another new instance
# Each step traceable, original unchanged
```

### The Update Pattern

Every operation follows this flow:

```python
async def send_message(self, text: str) -> Conversation:
    # 1. Create updated component
    updated_history = self.history.append_message(user_msg)
    
    # 2. Run operations with it
    result = await agent.run(deps=updated_history, ...)
    
    # 3. Create final component
    final_history = updated_history.append_message(response_msg)
    
    # 4. Return new aggregate
    return self.model_copy(update={"history": final_history})
```

### Framework Boundary

Pydantic AI uses mutable types (`list[ModelMessage]`), so we convert at the call site:

```python
# Our immutable type
history: tuple[ModelMessage, ...] = (...)

# Convert for framework
await agent.run(message_history=list(history))
```

This is the **only** place we use mutable types - at the framework boundary where required.

**Code:** `src/app/domain/conversation.py` - See `send_message()` for complete flow.

---

## Implementation Guide

### Key Files and Their Roles

| File | Purpose | Key Classes |
|------|---------|-------------|
| `domain_value.py` | Identity and state | `MessageId`, `ConversationId`, `StoredMessage`, `ConversationHistory` |
| `domain_type.py` | Type-safe constants | `ConversationStatus`, `ModelRoute`, `AIModelVendor` |
| `conversation.py` | Main business logic | `Conversation`, `ModelClassifier`, `ToolClassifier` |
| `model_pool.py` | Connection pooling | `ModelPool` |
| `tools.py` | LLM-callable functions | `calculator`, `tavily_search`, `ALL_TOOLS` |
| `model_catalog.py` | Model configuration | `ModelCatalog`, `ModelRegistry`, `ModelSpec` |
| `model_metadata.json` | Model definitions | Configuration data |

### Message Flow Walkthrough

**1. User sends message** → `POST /conversation/`

**2. API calls domain:**
```python
conversation = await Conversation.load(conv_id, redis, ...)
updated = await conversation.send_message("What is 5+3?")
await updated.save(redis)
```

**3. Inside `send_message()`:**

```
Step 1: Wrap user input
  user_msg = StoredMessage(id=MessageId(), content=ModelRequest(...))
  ↓
Step 2: Phase 1a - Model routing
  if router: spec = await router.route(history)
  ↓
Step 3: Phase 1b - Tool routing  
  if tool_router: tools = await tool_router.route(text)
  ↓
Step 4: Phase 2 - Execution
  model = pool.get_model(spec, tools)
  result = await model.run(...)
  ↓
Step 5: Wrap response(s)
  response_msgs = [StoredMessage(id=MessageId(), content=m) 
                   for m in result.new_messages()]
  ↓
Step 6: Return new conversation
  return self.model_copy(update={"history": final_history})
```

**4. API returns response** with conversation_id and message content

### Reading Path for New Developers

**Start here:**
1. `domain_value.py` - Understand the core data structures
2. `conversation.py` - See how they're used in business logic
3. `model_pool.py` - Understand caching strategy

**Then explore:**
4. `tools.py` - See how tools work
5. `model_catalog.py` - Understand model configuration
6. `domain_type.py` - See what enums exist

**Finally:**
7. `src/app/api/routers/conversation.py` - How HTTP layer uses domain
8. `src/app/service/conversation.py` - Thin orchestration layer

### Pydantic AI Integration Points

We use Pydantic AI directly for:
- **Types:** `ModelMessage`, `ModelRequest`, `ModelResponse`
- **Results:** `AgentRunResult[str]` with `.output`, `.usage`, `.new_messages()`
- **Usage:** `RunUsage` for token aggregation
- **Limits:** `UsageLimits` for budget enforcement
- **Client:** Core `Agent[ConversationHistory, str]` type (Pydantic AI's executor interface)

We DON'T wrap these - they're used directly as our domain vocabulary. This minimizes code and maximizes type system leverage.

---

## Architectural Principles

### 1. Smart Routing
Fast models make decisions, strong models execute. Optimize cost without sacrificing quality.

### 2. Efficient Caching
One client per (model, tools), reused across all conversations. Massive performance win.

### 3. Configuration Over Code
Models, routes, capabilities defined in JSON metadata, not hardcoded everywhere.

### 4. Immutability First
Frozen models, functional updates, no mutation. Safe for concurrent access.

### 5. Separation of Concerns
Identity (ours) wraps Content (framework). Each layer has a clear, single responsibility.

### 6. Type Safety Throughout
Pydantic validation at every boundary. Enums over strings. Prevent bugs at compile time.

### 7. Minimal Abstraction
Use framework types directly when they fit. Only add code when framework doesn't provide it.

---

## Checklist: What's Implemented

**Core System** ✅
- [x] Two-phase routing (model + tool selection)
- [x] Model pooling with (model, tools) caching
- [x] Conversation persistence (Redis)
- [x] Multi-message handling (tool calls)
- [x] Immutable domain models

**Model System** ✅
- [x] JSON-driven model catalog
- [x] Type-safe model registry
- [x] Flexible identifier resolution
- [x] O(1) model lookups

**Tool System** ✅
- [x] Calculator (AST-based safe eval)
- [x] Web search (Tavily API)
- [x] Dynamic tool selection
- [x] Tool registry

**Future Enhancements** 🚧
- [ ] Extended thinking mode
- [ ] Conversation branching/forking
- [ ] Streaming responses
- [ ] Multi-turn tool use

---

**Remember:** This document explains the architecture and principles. The actual code in `src/app/domain/` has comprehensive docstrings and inline comments for implementation details.

