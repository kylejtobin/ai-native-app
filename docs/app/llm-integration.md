# LLM Integration Patterns

> **Using rich types as the interface between application and AI**

This document shows how we integrate LLMs using Pydantic AI's type-driven approach, with real examples from our codebase.

> **Principle: Every Boundary is Type-Safe**
>
> Boundaries are where errors hide. The network boundary (JSON), the database boundary (SQL), the user boundary (forms), the LLM boundary (text). Each boundary is a translation point, and translations can lie.
>
> Type-safe boundaries use Pydantic: LLM output → Pydantic validates → Application (guaranteed structured). Each boundary is a validation checkpoint. If something makes it past the boundary, it's been proven valid.
>
> Validate at boundaries, trust internally. The interior of your system operates on guarantees, not hopes.
>
> See: [philosophy.md](../philosophy.md) "Every Boundary is Type-Safe"

---

## Pydantic AI as Type System Extension

**Key insight:** Pydantic AI is not a vendor framework—it's an extension of Pydantic's type system.

Just as you use `BaseModel` and `Field` from Pydantic without wrapping them, you use Pydantic AI's types (`ModelMessage`, `AgentRunResult`, `Agent`) directly in your domain.

### What We Use Directly

From [`src/app/domain/domain_value.py`](../../src/app/domain/domain_value.py):

```python
from pydantic_ai.messages import ModelMessage, ModelResponse

class StoredMessage(BaseModel):
    """Message with Persistence Identity.
    
    Wraps Pydantic AI's ModelMessage with our own MessageId for storage and reference.
    
    Attributes:
        id: Our unique identifier for this message
        content: Pydantic AI's ModelMessage (discriminated union of Request/Response)
    
    Note:
        arbitrary_types_allowed is required because ModelMessage is a Pydantic AI type
        that we don't own, but we want to compose it into our domain model
    """
    id: MessageId
    content: ModelMessage  # ← Pydantic AI's type!
    
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
```

**The Separation:**
- **Identity** (ours): `MessageId`, `ConversationId`
- **Content** (Pydantic AI's): `ModelMessage`, `ModelRequest`, `ModelResponse`
- **Metadata** (ours): `ConversationStatus`, token tracking

We don't duplicate Pydantic AI's types—we compose them.

## Structured Outputs: Type-Safe LLM Responses

Define Pydantic models as the LLM's output type, and Pydantic AI validates the response.

### Model Selection Decision

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class RouteDecision(BaseModel):
    """Model router's selection decision."""
    
    model: ModelRoute  # ← Enum: must be valid route
    reasoning: str | None = None
    
    model_config = ConfigDict(frozen=True)
```

**Usage:**

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class ModelClassifier(BaseModel):
    """Routes queries to appropriate models using a fast classifier."""
    
    spec: ModelSpec  # Fast model for routing
    registry: ModelRegistry
    _client_cache: Agent[ConversationHistory, RouteDecision] | None = PrivateAttr(default=None)
    
    @property
    def client(self) -> Agent[ConversationHistory, RouteDecision]:
        """Lazy-initialized classifier (cached)."""
        if self._client_cache is None:
            from pydantic_ai import Agent
            
            model = self.spec.to_agent_model(self.registry.catalog)
            client: Agent[ConversationHistory, RouteDecision] = Agent(
                model,
                deps_type=ConversationHistory,
                output_type=RouteDecision,  # ← LLM must return this type
                system_prompt=MODEL_ROUTER_SYSTEM_PROMPT,
            )
            object.__setattr__(self, "_client_cache", client)
            return client
        return self._client_cache
    
    async def route(self, history: ConversationHistory) -> ModelSpec:
        """Decide which model to use based on conversation history."""
        # Extract user prompt
        latest_msg = history.messages[-1] if history.messages else None
        user_prompt = ""
        if latest_msg:
            for part in latest_msg.content.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    user_prompt = part.content
                    break
        
        # Call LLM - output is validated as RouteDecision
        result = await self.client.run(user_prompt=user_prompt, deps=history)
        decision: RouteDecision = result.output  # ← Type-safe!
        
        # Use the structured decision
        return self.registry.catalog.parse_spec(decision.model.value)
```

**What this gives us:**
- LLM response is automatically parsed and validated
- Type-safe: `decision.model` is guaranteed to be a `ModelRoute` enum
- Invalid responses raise validation errors (can retry with feedback)
- Optional `reasoning` field for observability

### Tool Selection Decision

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
class ToolDecision(BaseModel):
    """Tool router's selection decision."""
    
    tools: list[str] = []  # List of tool names
    reasoning: str | None = None
    
    model_config = ConfigDict(frozen=True)


class ToolClassifier(BaseModel):
    """Routes queries to appropriate tools using a fast classifier."""
    
    spec: ModelSpec
    registry: ModelRegistry
    _client_cache: Agent[str, ToolDecision] | None = PrivateAttr(default=None)
    
    @property
    def client(self) -> Agent[str, ToolDecision]:
        """Lazy-initialized tool classifier (cached)."""
        if self._client_cache is None:
            from pydantic_ai import Agent
            
            model = self.spec.to_agent_model(self.registry.catalog)
            client: Agent[str, ToolDecision] = Agent(
                model,
                deps_type=str,
                output_type=ToolDecision,  # ← LLM returns tool list
                system_prompt=TOOL_ROUTER_SYSTEM_PROMPT,
            )
            object.__setattr__(self, "_client_cache", client)
            return client
        return self._client_cache
    
    async def route(self, query: str) -> list[str]:
        """Decide which tools are needed for the query."""
        result = await self.client.run(user_prompt=query, deps=query)
        decision: ToolDecision = result.output
        
        # Validate tools exist
        from .tools import ALL_TOOLS
        valid_tools = [tool for tool in decision.tools if tool in ALL_TOOLS]
        
        return valid_tools
```

**Pattern:**
- Fast model analyzes query → returns `ToolDecision`
- Extract validated `tools` list
- Filter to ensure tools exist
- Pass to execution model

## Tool Definitions

Tools are just async functions with type hints and docstrings. Pydantic AI generates the schema automatically.

### Calculator Tool

From [`src/app/domain/tools.py`](../../src/app/domain/tools.py):

```python
async def calculator(
    ctx: RunContext[ConversationHistory],
    expression: str,
) -> str:
    """Evaluate Mathematical Expressions Safely.
    
    Uses Python's AST (Abstract Syntax Tree) module to safely evaluate math
    expressions without the security risks of eval(). Only allows whitelisted
    operations and functions.
    
    Use this tool when you need to:
        - Perform arithmetic calculations
        - Evaluate mathematical expressions
        - Compute factorials, powers, trigonometry
    
    Args:
        ctx: Pydantic AI run context with conversation history
        expression: Math expression as string (e.g., "5 * 8", "factorial(6)")
    
    Returns:
        String result of the calculation, or error message if invalid
    """
    import ast
    import math
    import operator
    
    # Whitelist of safe operators
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.Mod: operator.mod,
    }
    
    # Whitelist of safe functions
    safe_functions = {
        "abs": abs,
        "round": round,
        "sqrt": math.sqrt,
        "factorial": math.factorial,
        "sin": math.sin,
        "cos": math.cos,
        "pi": math.pi,
        "e": math.e,
    }
    
    def eval_expr(node: ast.expr) -> Any:
        """Recursively evaluate AST expression node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left_val = eval_expr(node.left)
            right_val = eval_expr(node.right)
            op_func = operators[type(node.op)]
            return op_func(left_val, right_val)
        # ... more node types ...
        else:
            raise ValueError(f"Unsupported operation: {type(node)}")
    
    try:
        tree = ast.parse(expression, mode="eval")
        result = eval_expr(tree.body)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"
```

**Tool Pattern:**
- Clear docstring (LLM reads this!)
- Type-hinted parameters
- Returns string (easy for LLM to parse)
- Handles errors gracefully (returns error string, doesn't raise)
- Security: AST-based evaluation, no `eval()`

### Web Search Tool

From [`src/app/domain/tools.py`](../../src/app/domain/tools.py):

```python
async def tavily_search(
    ctx: RunContext[ConversationHistory],
    query: str,
) -> str:
    """Search the Web for Current Information.
    
    Uses Tavily's AI-powered search API to find recent, relevant information
    from across the web. Tavily optimizes results specifically for LLM consumption.
    
    Use this tool when you need:
        - Recent news or current events
        - Facts that may have changed since LLM training cutoff
        - Real-time information (weather, stock prices, sports scores)
    
    Args:
        ctx: Pydantic AI run context with conversation history
        query: Clear, specific search query
    
    Returns:
        Formatted string with AI summary and top 5 sources, or error message
    """
    from tavily import AsyncTavilyClient
    from ..config import settings
    
    client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    
    response = await client.search(
        query=query,
        max_results=5,
        search_depth="basic",
        include_answer=True,
        include_raw_content=False,
    )
    
    if not response or "results" not in response:
        return f"No web results found for query: '{query}'"
    
    # Format for LLM consumption
    parts = []
    
    if response.get("answer"):
        parts.append(f"Summary: {response['answer']}\n")
    
    parts.append("Sources:")
    for i, result in enumerate(response["results"][:5], 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        snippet = result.get("content", "")[:200]
        parts.append(f"{i}. {title}\n   {snippet}...\n   {url}\n")
    
    return "\n".join(parts)
```

**Tool Pattern:**
- Integrates external API (Tavily)
- Formats results for LLM (summary + sources)
- Handles errors gracefully
- Truncates content to keep token usage reasonable
- Returns structured text the LLM can parse

## Tool Registration

From [`src/app/domain/tools.py`](../../src/app/domain/tools.py):

```python
# Tool Registry - All Available Tools
ALL_TOOLS = {
    "calculator": calculator,
    "tavily_search": tavily_search,
}
```

From [`src/app/domain/model_pool.py`](../../src/app/domain/model_pool.py):

```python
def get_model(self, spec: ModelSpec, tool_names: list[str] | None = None) -> Agent[ConversationHistory, str]:
    """Get or create cached model client with selected tools."""
    from pydantic_ai import Agent
    from .tools import ALL_TOOLS
    
    # Select tools based on routing decision
    if tool_names is None:
        tool_funcs = list(ALL_TOOLS.values())
        cache_key = (spec, frozenset(ALL_TOOLS.keys()))
    else:
        tool_funcs = [ALL_TOOLS[name] for name in tool_names if name in ALL_TOOLS]
        cache_key = (spec, frozenset(tool_names))
    
    if cache_key not in self._cache:
        model = spec.to_agent_model(self.registry.catalog)
        self._cache[cache_key] = Agent(
            model,
            deps_type=ConversationHistory,
            output_type=str,
            tools=tool_funcs,  # ← Pass tool functions directly
        )
    return self._cache[cache_key]
```

**Pattern:**
- Tools are just functions in a dict
- Pass list of functions to `Agent(tools=[...])`
- Cache clients by (model, tools) tuple
- Different tool combinations = different cached clients

## System Prompts

From [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py):

```python
MODEL_ROUTER_SYSTEM_PROMPT = """
Analyze the user's latest query and select the best model to handle it.

Model capabilities:
- ANTHROPIC_SONNET: Best for complex reasoning, analysis, creative writing
- OPENAI_GPT4: General purpose, balanced performance
- OPENAI_GPT4_MINI: Fast responses for simple queries, lookups, casual chat

Consider:
- Query complexity (simple vs. multi-step reasoning)
- Domain (technical, creative, general)
- User intent (quick answer vs. detailed analysis)

Always provide reasoning for your selection.
""".strip()

TOOL_ROUTER_SYSTEM_PROMPT = """
Analyze the user's query and select which tools are needed to answer it.

Available tools:
- calculator: For mathematical calculations, arithmetic, factorials, trigonometry
- tavily_search: For current events, recent information, web searches, fact checking

Rules:
- Only select tools that are NECESSARY for the query
- If the query needs multiple tools, select all relevant ones
- If no tools are needed (general knowledge, simple Q&A), return empty list
- Be conservative - don't select tools unless truly needed

Examples:
- "What is 5 factorial?" → ["calculator"]
- "Who won the 2024 Super Bowl?" → ["tavily_search"]
- "Calculate 5! and search for Python news" → ["calculator", "tavily_search"]
- "What is the capital of France?" → []
""".strip()
```

**System Prompt Guidelines:**
- Explain the task clearly
- List available options (models, tools)
- Provide decision criteria
- Include examples when helpful
- Keep it concise but complete

## Benefits

### Type Safety

```python
# ✅ Type-safe - LLM response validated
result = await self.client.run(user_prompt=query, deps=history)
decision: RouteDecision = result.output  # Guaranteed to be RouteDecision

# Can safely access fields
model_enum = decision.model  # ModelRoute enum
reason = decision.reasoning  # str | None
```

### Automatic Schema Generation

Pydantic AI generates tool schemas from type hints:

```python
async def calculator(ctx: RunContext[ConversationHistory], expression: str) -> str:
    """Docstring becomes tool description."""
```

Becomes this schema for the LLM:
```json
{
  "name": "calculator",
  "description": "Docstring becomes tool description.",
  "parameters": {
    "type": "object",
    "properties": {
      "expression": {"type": "string"}
    },
    "required": ["expression"]
  }
}
```

### Validation with Retry

If LLM returns invalid data, Pydantic AI can retry with error feedback:

```python
# Pydantic AI handles this automatically:
# 1. LLM returns {"model": "INVALID_MODEL"}
# 2. Pydantic validation fails
# 3. Pydantic AI retries with error message
# 4. LLM corrects and returns valid {"model": "ANTHROPIC_SONNET"}
```

### Composability

Domain models use Pydantic AI types directly:

```python
class StoredMessage(BaseModel):
    id: MessageId  # Our type
    content: ModelMessage  # Pydantic AI's type
```

No wrapping, no conversion layers—just composition.

---

## Anti-Patterns: What NOT to Do

❌ **DON'T load all tools into all agents**
- Create one agent with calculator + search + 10 other tools "just in case"
- Reality: Tool descriptions bloat context, confuse model, reduce accuracy
- Use two-phase routing: classifier selects needed tools, agent only loads those

❌ **DON'T skip structured outputs for complex responses**
- Parse LLM text output with regex or string splitting
- Reality: Brittle, fails on format variations, no validation
- Use Pydantic models as `result_type` for guaranteed structure

❌ **DON'T bypass model pool and create clients directly**
- `agent = Agent(model="claude-sonnet...")` in application code
- Reality: No caching, creates new client per request, slow and expensive
- Use model pool: `model_pool.get_model(spec, tool_names)`

❌ **DON'T ignore two-phase routing benefits**
- Always use most expensive model for every query
- Reality: Wastes money on simple queries that cheaper models handle fine
- Use classifier to route: cheap for simple, expensive for complex

❌ **DON'T put LLM logic in services**
- Service builds prompts, parses responses, handles tool selection
- Reality: Business logic scattered, hard to test without LLM
- Domain models own LLM integration, services just orchestrate

❌ **DON'T skip validation on structured outputs**
- Trust LLM to always return valid data matching your type
- Reality: LLMs make mistakes, return invalid formats occasionally
- Pydantic validates automatically, but add field validators for business rules

❌ **DON'T create wrapper types around Pydantic AI types**
- Custom `MyModelMessage` that wraps `ModelMessage`
- Reality: Unnecessary abstraction, impedance mismatch, more code
- Use Pydantic AI types directly via composition

---

**See Also:**
- [`src/app/domain/tools.py`](../../src/app/domain/tools.py) - Tool definitions
- [`src/app/domain/conversation.py`](../../src/app/domain/conversation.py) - Structured outputs
- [`src/app/domain/model_pool.py`](../../src/app/domain/model_pool.py) - Model pool with tools
- [Domain Models](domain-models.md) - Rich model patterns
- [Type System](type-system.md) - Type-driven design

