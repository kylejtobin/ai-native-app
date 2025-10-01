"""Domain Tools - LLM-Callable Functions for Agent Use.

Defines tools that Pydantic AI agents can call during execution. Tools are
simply async functions with proper type hints and docstrings - Pydantic AI
automatically generates the tool schema from these definitions.

Tool Registration:
    Tools are registered by passing them to Agent constructor:
    >>> Agent(model, tools=[calculator, tavily_search])

Best Practices:
    - Clear docstrings (LLM sees these!)
    - Specific parameter names and types
    - Return string results (easy for LLM to parse)
    - Handle errors gracefully within the tool

Reference: https://ai.pydantic.dev/tools/
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import RunContext

from .domain_value import ConversationHistory


async def calculator(
    ctx: RunContext[ConversationHistory],
    expression: str,
) -> str:
    """Evaluate Mathematical Expressions Safely.

    Uses Python's AST (Abstract Syntax Tree) module to safely evaluate math
    expressions without the security risks of eval(). Only allows whitelisted
    operations and functions.

    Security Note:
        Never use eval() or exec() with user input! This tool demonstrates
        safe evaluation by parsing to AST first, then recursively evaluating
        only approved nodes.

    Use this tool when you need to:
        - Perform arithmetic calculations
        - Evaluate mathematical expressions
        - Compute factorials, powers, trigonometry

    Args:
        ctx: Pydantic AI run context with conversation history
        expression: Math expression as string (e.g., "5 * 8", "factorial(6)", "sin(pi/2)")

    Returns:
        String result of the calculation, or error message if invalid

    Examples:
        >>> await calculator(ctx, "5 + 3 * 2")
        "11"
        >>> await calculator(ctx, "factorial(5)")
        "120"
    """
    import ast
    import math
    import operator

    # Whitelist of safe binary/unary operators
    # Maps AST node types to their actual operator functions
    operators = {
        ast.Add: operator.add,  # +
        ast.Sub: operator.sub,  # -
        ast.Mult: operator.mul,  # *
        ast.Div: operator.truediv,  # /
        ast.Pow: operator.pow,  # **
        ast.USub: operator.neg,  # unary -
        ast.Mod: operator.mod,  # %
    }

    # Whitelist of safe functions and constants
    # These are the ONLY functions/names the LLM can call
    safe_functions = {
        # Built-in functions
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        # Math module functions
        "sqrt": math.sqrt,
        "factorial": math.factorial,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        # Math constants
        "pi": math.pi,
        "e": math.e,
    }

    def eval_expr(node: ast.expr) -> Any:
        """Recursively Evaluate AST Expression Node.

        This function walks the AST and evaluates only approved node types.
        Any unapproved operation raises ValueError, preventing code injection.
        """
        if isinstance(node, ast.Constant):
            # Literal values: 5, 3.14, "text" (though we expect numbers)
            return node.value

        elif isinstance(node, ast.BinOp):
            # Binary operations: a + b, a * b, etc.
            # Recursively evaluate left and right operands, then apply operator
            left_val = eval_expr(node.left)
            right_val = eval_expr(node.right)
            op_func = operators[type(node.op)]
            return op_func(left_val, right_val)  # type: ignore[operator]

        elif isinstance(node, ast.UnaryOp):
            # Unary operations: -x, +x
            operand_val = eval_expr(node.operand)
            op_func = operators[type(node.op)]
            return op_func(operand_val)  # type: ignore[operator]

        elif isinstance(node, ast.Call):
            # Function calls: sqrt(16), factorial(5)
            # Security: Only allow simple named functions, no attribute access
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only named functions allowed")

            func_name = node.func.id
            if func_name not in safe_functions:
                raise ValueError(f"Function {func_name} not allowed")

            # Recursively evaluate arguments
            args = [eval_expr(arg) for arg in node.args]
            return safe_functions[func_name](*args)  # type: ignore[operator]

        elif isinstance(node, ast.Name):
            # Variable/constant names: pi, e
            if node.id in safe_functions:
                return safe_functions[node.id]
            raise ValueError(f"Name {node.id} not allowed")

        else:
            # Reject anything not explicitly allowed (list comprehensions, imports, etc.)
            raise ValueError(f"Unsupported operation: {type(node)}")

    try:
        # Parse expression string into AST (raises SyntaxError if invalid)
        tree = ast.parse(expression, mode="eval")

        # Evaluate the parsed AST recursively
        result = eval_expr(tree.body)

        # Return as string for LLM to parse
        return str(result)

    except Exception as e:
        # Return error message instead of raising - LLM can retry or explain to user
        return f"Error evaluating expression: {e}"


async def tavily_search(
    ctx: RunContext[ConversationHistory],
    query: str,
) -> str:
    """Search the Web for Current Information.

    Uses Tavily's AI-powered search API to find recent, relevant information
    from across the web. Tavily optimizes results specifically for LLM consumption,
    providing clean summaries and high-quality sources.

    Use this tool when you need:
        - Recent news or current events
        - Facts that may have changed since LLM training cutoff
        - Real-time information (weather, stock prices, sports scores)
        - Verification of time-sensitive claims

    Args:
        ctx: Pydantic AI run context with conversation history
        query: Clear, specific search query (e.g., "2024 Super Bowl winner", "latest Python version")

    Returns:
        Formatted string with AI summary and top 5 sources, or error message

    Example:
        >>> await tavily_search(ctx, "Who won the 2024 NBA Finals?")
        "Summary: Boston Celtics won the 2024 NBA Finals...
         Sources:
         1. Official NBA - Celtics Win Championship
            The Boston Celtics defeated the Dallas Mavericks...
            https://nba.com/..."
    """
    from tavily import AsyncTavilyClient

    from ..config import settings

    # Create Tavily client with API key from configuration
    client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    # Perform search with LLM-optimized settings
    response = await client.search(
        query=query,
        max_results=5,  # Top 5 most relevant results
        search_depth="basic",  # Fast search mode (vs "advanced" for deeper research)
        include_answer=True,  # Get AI-generated summary
        include_raw_content=False,  # Skip full page content to reduce tokens
    )

    # Handle empty or invalid response
    if not response or "results" not in response:
        return f"No web results found for query: '{query}'"

    # Format results for LLM consumption
    parts = []

    # Add AI-generated summary if available
    if response.get("answer"):
        parts.append(f"Summary: {response['answer']}\n")

    # Add source citations with snippets
    parts.append("Sources:")
    for i, result in enumerate(response["results"][:5], 1):
        title = result.get("title", "Untitled")
        url = result.get("url", "")
        # Truncate content to ~200 chars to keep response concise
        snippet = result.get("content", "")[:200]
        parts.append(f"{i}. {title}\n   {snippet}...\n   {url}\n")

    return "\n".join(parts)


# Tool Registry - All Available Tools for Agent Use
# Used by ToolClassifier to validate tool selections and by ModelPool for registration
ALL_TOOLS = {
    "calculator": calculator,
    "tavily_search": tavily_search,
}

__all__ = ["ALL_TOOLS", "calculator", "tavily_search"]
