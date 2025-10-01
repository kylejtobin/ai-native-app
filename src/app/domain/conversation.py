"""Conversation Aggregate - Main Domain Model for LLM Interactions.

This module implements the Conversation aggregate root, which orchestrates the
complete lifecycle of multi-turn LLM conversations with intelligent routing.

Two-Phase Routing Architecture:
    Phase 1a - Model Selection: Fast model (Haiku) analyzes query complexity
                               and selects execution model (Sonnet, GPT-5)

    Phase 1b - Tool Selection: Fast model analyzes query requirements and
                              selects needed tools (calculator, search, none)

    Phase 2 - Execution: Selected model runs with selected tools to answer

This architecture optimizes cost and latency by using expensive models only
when necessary and loading only relevant tools into the LLM's context.

Key Components:
    - Conversation: Main aggregate (immutable, algebraic operations)
    - ModelClassifier: Intelligent model selection using fast classifier
    - ToolClassifier: Intelligent tool selection using fast classifier
    - ConversationHistory: Persistence-ready state container
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, PrivateAttr, field_validator
from pydantic_ai.messages import ModelRequest, UserPromptPart
from pydantic_ai.settings import ModelSettings

from .domain_type import ConversationStatus, ModelRoute
from .domain_value import ConversationHistory, ConversationId, MessageId, StoredMessage
from .model_catalog import ModelRegistry, ModelSpec
from .model_pool import ModelPool

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from redis.asyncio import Redis

# Router system prompts
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


class RouteDecision(BaseModel):
    """Model router's selection decision."""

    model: ModelRoute
    reasoning: str | None = None

    model_config = ConfigDict(frozen=True)


class ToolDecision(BaseModel):
    """Tool router's selection decision."""

    tools: list[str] = []
    reasoning: str | None = None

    model_config = ConfigDict(frozen=True)


class ModelClassifier(BaseModel):
    """
    Routes queries to appropriate models using a fast classifier agent.

    Two-phase execution pattern:
    - Phase 1: Fast model decides which execution model to use
    - Phase 2: Selected model handles the actual query
    """

    spec: ModelSpec
    registry: ModelRegistry
    available_routes: tuple[ModelRoute, ...]
    _client_cache: Agent[ConversationHistory, RouteDecision] | None = PrivateAttr(default=None)

    model_config = ConfigDict(frozen=True)

    @property
    def client(self) -> Agent[ConversationHistory, RouteDecision]:
        """Lazy-initialized routing client (cached)."""
        if self._client_cache is None:
            from pydantic_ai import Agent

            model = self.spec.to_agent_model(self.registry.catalog)
            agent: Agent[ConversationHistory, RouteDecision] = Agent(
                model,
                deps_type=ConversationHistory,
                output_type=RouteDecision,
                system_prompt=MODEL_ROUTER_SYSTEM_PROMPT,
            )
            object.__setattr__(self, "_client_cache", agent)
            return agent
        return self._client_cache

    @field_validator("available_routes")
    @classmethod
    def require_at_least_one_route(cls, v: tuple[ModelRoute, ...]) -> tuple[ModelRoute, ...]:
        """Router must have at least one available route."""
        if not v:
            raise ValueError("Router requires at least one available route")
        return v

    async def route(self, history: ConversationHistory) -> ModelSpec:
        """
        Decide which model to use based on conversation history.

        Returns ModelSpec constrained by available_routes (API keys).
        """
        # Get latest user message for routing decision
        latest_msg = history.messages[-1] if history.messages else None
        user_prompt = ""
        if latest_msg:
            for part in latest_msg.content.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    user_prompt = part.content
                    break

        result = await self.client.run(user_prompt=user_prompt, deps=history)
        decision: RouteDecision = result.output

        if decision.model not in self.available_routes:
            fallback = self.available_routes[0]
            decision = RouteDecision(
                model=fallback, reasoning=f"Requested {decision.model} not available, using {fallback}"
            )

        return self.registry.catalog.parse_spec(decision.model.value)


class ToolClassifier(BaseModel):
    """
    Routes queries to appropriate tools using a fast classifier agent.

    Two-phase execution pattern:
    - Phase 1: Fast model decides which tools are needed
    - Phase 2: Main agent runs with only selected tools in scope
    """

    spec: ModelSpec
    registry: ModelRegistry
    _client_cache: Agent[str, ToolDecision] | None = PrivateAttr(default=None)

    model_config = ConfigDict(frozen=True)

    @property
    def client(self) -> Agent[str, ToolDecision]:
        """Lazy-initialized tool routing client (cached)."""
        if self._client_cache is None:
            from pydantic_ai import Agent

            model = self.spec.to_agent_model(self.registry.catalog)
            agent: Agent[str, ToolDecision] = Agent(
                model,
                deps_type=str,
                output_type=ToolDecision,
                system_prompt=TOOL_ROUTER_SYSTEM_PROMPT,
            )
            object.__setattr__(self, "_client_cache", agent)
            return agent
        return self._client_cache

    async def route(self, query: str) -> list[str]:
        """
        Decide which tools are needed for the query.

        Args:
            query: User's question/request

        Returns:
            List of tool names (e.g., ["calculator", "tavily_search"])
        """
        result = await self.client.run(user_prompt=query, deps=query)
        decision: ToolDecision = result.output

        # Validate tools exist
        from .tools import ALL_TOOLS

        valid_tools = [tool for tool in decision.tools if tool in ALL_TOOLS]

        return valid_tools


class Conversation(BaseModel):
    """
    Conversation aggregate - orchestrates routing and agent execution.

    Algebraic Composition:
    - ConversationHistory: Identity + messages (immutable)
    - ModelRegistry: Available models + default
    - ModelPool: Model client cache
    - ModelClassifier: Optional routing logic

    Business Logic:
    - send_message(): Add user message → route → run agent → wrap response
    - Returns new Conversation (immutable updates)
    """

    history: ConversationHistory
    registry: ModelRegistry
    model_pool: ModelPool
    router: ModelClassifier | None = None
    tool_router: ToolClassifier | None = None

    model_config = ConfigDict(frozen=True)

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

    @classmethod
    def start_with_id(
        cls,
        *,
        conv_id: ConversationId,
        registry: ModelRegistry,
        model_pool: ModelPool,
        router: ModelClassifier | None = None,
        tool_router: ToolClassifier | None = None,
        status: ConversationStatus = ConversationStatus.ACTIVE,
    ) -> Conversation:
        """Factory: Start new conversation with a specific ID.
        
        Useful for idempotent conversation creation where the client provides
        the ID (e.g., REST APIs with PUT semantics).
        """
        history = ConversationHistory(
            id=conv_id,
            status=status,
        )
        return cls(
            history=history,
            registry=registry,
            model_pool=model_pool,
            router=router,
            tool_router=tool_router,
        )

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

    async def send_message(
        self,
        text: str,
        spec: ModelSpec | None = None,
        settings: ModelSettings | None = None,
        auto_route: bool = True,
    ) -> Conversation:
        """Send Message and Get LLM Response with Intelligent Routing.

        Implements the complete message flow with two-phase routing optimization.
        This method is the main entry point for user interactions with the LLM.

        Execution Flow:
            1. Wrap user text in StoredMessage with ID
            2. Phase 1a: Model Selection (if auto_route enabled)
               - Fast model analyzes complexity
               - Routes to appropriate execution model
            3. Phase 1b: Tool Selection (if auto_route enabled)
               - Fast model analyzes requirements
               - Selects needed tools (or none)
            4. Phase 2: Execution
               - Get agent from pool (cached by model+tools)
               - Run with full conversation history
               - Get response with tool calls if needed
            5. Wrap response message(s) with IDs
            6. Return new Conversation instance (immutable update)

        Args:
            text: User's message content
            spec: Explicit model to use (skips routing if provided)
            settings: Pydantic AI model settings (temperature, max_tokens, etc.)
            auto_route: Enable intelligent routing (default: True)

        Returns:
            New Conversation instance with added messages

        Performance Notes:
            - Routing adds ~100-200ms latency (fast model calls)
            - Saves cost by avoiding expensive models for simple queries
            - Tool selection reduces context size and improves response quality

        Example:
            >>> conversation = Conversation.start(registry=reg, model_pool=pool)
            >>> updated = await conversation.send_message("What is 5 + 3?")
            >>> # Routing selects: Haiku (routing) → Sonnet (execution), calculator tool
            >>> updated = await updated.send_message("And what's the weather?")
            >>> # Routing selects: Haiku (routing) → Sonnet (execution), search tool
        """
        # === Step 1: Wrap User Input ===
        # Create message with unique ID for persistence/reference
        user_msg = StoredMessage(
            id=MessageId(),
            content=ModelRequest(parts=[UserPromptPart(content=text)]),
        )

        # Immutably append to history (returns new ConversationHistory)
        updated_history = self.history.append_message(user_msg)

        # === Phase 1a: Model Selection (Fast → Strong) ===
        # If no explicit model specified and routing enabled, let fast model decide
        if auto_route and spec is None and self.router:
            spec = await self.router.route(updated_history)

        # Fallback to registry's default model if still unset
        if spec is None:
            spec = self.registry.default

        # === Phase 1b: Tool Selection (Fast → Filtered) ===
        # Let fast model analyze query and pick needed tools
        tool_names: list[str] | None = None
        if auto_route and self.tool_router:
            tool_names = await self.tool_router.route(text)
            # tool_names is now ["calculator"], ["tavily_search"], both, or []

        # === Phase 2: Execute with Selected Model + Tools ===
        # Get cached agent (or create new one) with exact model+tools combination
        model = self.model_pool.get_model(spec, tool_names=tool_names)

        # Run agent with full conversation history
        result = await model.run(
            deps=updated_history,  # Domain context (can access conversation state)
            message_history=list(updated_history.message_content),  # Pydantic AI's message format
            model_settings=settings,  # Optional: temperature, max_tokens, etc.
        )

        # === Step 3: Process Response Messages ===
        # Wrap ALL response messages with identity for persistence
        # Important: When tools are invoked, result.new_messages() returns multiple messages:
        #   1. ModelRequest with tool call(s)
        #   2. ModelResponse with tool return(s)
        #   3. ModelResponse with final text answer
        response_messages = [StoredMessage(id=MessageId(), content=msg) for msg in result.new_messages()]

        # Immutably append all response messages to history
        final_history = updated_history
        for response_msg in response_messages:
            final_history = final_history.append_message(response_msg)

        # === Step 4: Return New Conversation ===
        # Algebraic update: return new instance with updated history
        # Original Conversation instance remains unchanged (safe for concurrent use)
        return self.model_copy(update={"history": final_history})


__all__ = [
    "Conversation",
    "ModelClassifier",
    "RouteDecision",
    "ToolClassifier",
    "ToolDecision",
]
