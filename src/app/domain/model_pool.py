"""Model Pool - Efficient Caching of LLM Client Connections.

Manages a pool of Pydantic AI Agent instances to avoid the expensive overhead
of repeatedly creating HTTP clients for LLM providers (OpenAI, Anthropic).

Key Insight:
    Pydantic AI Agents are stateless executors. The conversation history is
    passed per-run via message_history parameter, not stored in the Agent.
    This means one Agent instance can serve many conversations safely.

Performance:
    - Agent creation: Expensive (HTTP client setup, connection pooling)
    - Agent reuse: Cheap (just parameter passing)
    - Cache key: (ModelSpec, frozenset[tool_names]) for fine-grained reuse
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, PrivateAttr

from .domain_value import ConversationHistory
from .model_catalog import ModelRegistry, ModelSpec

if TYPE_CHECKING:
    from pydantic_ai import Agent


class ModelPool(BaseModel):
    """LLM Client Connection Pool.

    Caches Pydantic AI Agent instances by (ModelSpec, tool set) to avoid
    expensive repeated HTTP client initialization. Agents are stateless
    executors, so one instance can safely serve many conversations.

    Attributes:
        registry: Source of truth for available models and their specifications
        _cache: Private infrastructure dict storing Agent instances

    Architecture:
        - Domain Layer: ModelSpec (what model to use)
        - Infrastructure Layer: _cache dict (mutable, private)
        - Frozen Model: Uses PrivateAttr for mutable cache in immutable model

    Cache Strategy:
        Key: (ModelSpec, frozenset[tool_names])
        - Allows same model with different tool combinations
        - Example: Sonnet with [calculator] vs Sonnet with [search, calculator]

    Performance Impact:
        Without pool: ~500ms per model client creation (HTTP setup)
        With pool: <1ms for cached lookup
    """

    registry: ModelRegistry
    _cache: dict[tuple[ModelSpec, frozenset[str]], Agent[ConversationHistory, str]] = PrivateAttr(default_factory=dict)

    model_config = ConfigDict(frozen=True)

    def get_model(
        self,
        spec: ModelSpec,
        tool_names: list[str] | None = None,
    ) -> Agent[ConversationHistory, str]:
        """Get or Create Cached Model Client with Selected Tools.

        Implements lazy initialization: only creates Agent on cache miss.
        Subsequent calls with same (spec, tools) return cached instance.

        Args:
            spec: Model specification (vendor + variant_id)
            tool_names: Specific tools to register (None = all tools)

        Returns:
            Pydantic AI Agent configured for ConversationHistory → str

        Example:
            >>> pool = ModelPool(registry=registry)
            >>> # First call creates model client
            >>> model1 = pool.get_model(sonnet_spec, ["calculator"])
            >>> # Second call returns cached client
            >>> model2 = pool.get_model(sonnet_spec, ["calculator"])
            >>> assert model1 is model2  # Same instance!
        """
        from pydantic_ai import Agent

        from .tools import ALL_TOOLS

        # Build cache key and resolve tool functions
        if tool_names is None:
            # No filtering - use all available tools
            tool_funcs = list(ALL_TOOLS.values())
            cache_key = (spec, frozenset(ALL_TOOLS.keys()))
        else:
            # Filter to requested tools only (invalid names silently ignored)
            tool_funcs = [ALL_TOOLS[name] for name in tool_names if name in ALL_TOOLS]
            cache_key = (spec, frozenset(tool_names))

        # Lazy initialization on cache miss
        if cache_key not in self._cache:
            # Convert ModelSpec to provider-specific API string
            model = spec.to_agent_model(self.registry.catalog)

            # Create and cache new Agent instance
            self._cache[cache_key] = Agent(
                model,
                deps_type=ConversationHistory,  # Agent receives full conversation context
                output_type=str,  # Agent returns simple string responses
                tools=tool_funcs,  # Pydantic AI registers these as callable tools
            )

        return self._cache[cache_key]


__all__ = ["ModelPool"]
