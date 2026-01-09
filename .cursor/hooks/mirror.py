"""
The Architect's Mirror
======================

A simple AST scanner to detect EMDCA violations.
It emits signals; the Agent (LLM) decides the verdict.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PositiveInt, RootModel, ValidationError

# =============================================================================
# 1. DOMAIN (Types)
# =============================================================================


class PatternId(StrEnum):
    P00_MASTER = "00"
    P01_FACTORY = "01"
    P02_STATE = "02"
    P03_RAILWAY = "03"
    P04_EXECUTION = "04"
    P05_CONFIG = "05"
    P06_STORAGE = "06"
    P07_TRANSLATION = "07"
    P08_ORCHESTRATOR = "08"
    P09_WORKFLOW = "09"
    P10_INFRA = "10"


class SignalKind(StrEnum):
    SERVICE_IDENTITY = "service_identity"
    DOMAIN_IDENTITY = "domain_identity"
    SERVICE_IN_DOMAIN = "service_in_domain"
    VALIDATE_FUNCTION = "validate_function"
    TRY_BLOCK = "try_block"
    RAISE_STMT = "raise_stmt"
    AWAIT_EXPR = "await_expr"
    PRIMITIVE_TYPE = "primitive_type"
    FIELD_DEFAULT = "field_default"
    BOOLEAN_FLAG = "boolean_flag"


class Signal(BaseModel):
    """A mechanical observation of a potential violation."""

    model_config = {"frozen": True}
    kind: SignalKind
    pattern_id: PatternId
    line: PositiveInt
    content: str
    hint: str


# =============================================================================
# 2. LOGIC (Detection)
# =============================================================================


def detect_signal(
    node: ast.AST, file_path: Path, get_line: Callable[[int], str]
) -> Signal | None:
    """Pure Function: Map AST node to Signal."""
    is_domain = "domain" in file_path.parts
    is_service = "service" in file_path.parts

    # 1. Class Definitions
    if isinstance(node, ast.ClassDef):
        # Service Classes must be Plain
        if is_service:
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    return Signal(
                        kind=SignalKind.SERVICE_IDENTITY,
                        pattern_id=PatternId.P00_MASTER,
                        line=node.lineno,
                        content=get_line(node.lineno),
                        hint="Service classes must be Plain Classes, not Pydantic Models.",
                    )

        # Domain Objects must be Models (mostly)
        if is_domain:
            is_model = any(
                (isinstance(b, ast.Name) and b.id == "BaseModel") for b in node.bases
            )
            is_enum = any(
                "Enum" in (b.id if isinstance(b, ast.Name) else "") for b in node.bases
            )
            is_exc = node.name.endswith("Error") or "Exception" in [
                b.id for b in node.bases if isinstance(b, ast.Name)
            ]

            if not is_model and not is_enum and not is_exc:
                return Signal(
                    kind=SignalKind.DOMAIN_IDENTITY,
                    pattern_id=PatternId.P00_MASTER,
                    line=node.lineno,
                    content=get_line(node.lineno),
                    hint="Domain objects must be Pydantic Models (Data) or Enums.",
                )

        # Service Injection in Domain
        if is_domain and re.search(r"(Service|Manager|Handler|Processor)$", node.name):
            return Signal(
                kind=SignalKind.SERVICE_IN_DOMAIN,
                pattern_id=PatternId.P04_EXECUTION,
                line=node.lineno,
                content=get_line(node.lineno),
                hint="Service/Manager classes belong in service/, not domain/.",
            )

    # 2. Control Flow
    if is_domain:
        if isinstance(node, ast.Try):
            return Signal(
                kind=SignalKind.TRY_BLOCK,
                pattern_id=PatternId.P03_RAILWAY,
                line=node.lineno,
                content=get_line(node.lineno),
                hint="Avoid try/except in Domain. Use Result Types or Let it Crash.",
            )
        if isinstance(node, ast.Raise):
            return Signal(
                kind=SignalKind.RAISE_STMT,
                pattern_id=PatternId.P03_RAILWAY,
                line=node.lineno,
                content=get_line(node.lineno),
                hint="Avoid raise in Domain. Return Failure Result Types.",
            )
        if isinstance(node, ast.Await):
            return Signal(
                kind=SignalKind.AWAIT_EXPR,
                pattern_id=PatternId.P04_EXECUTION,
                line=node.lineno,
                content=get_line(node.lineno),
                hint="Domain Logic should be Pure/Synchronous. Async/IO belongs in Shell.",
            )

    # 3. Naming Smells
    if isinstance(node, ast.FunctionDef):
        if re.match(r"^(validate_|check_|verify_)", node.name):
            return Signal(
                kind=SignalKind.VALIDATE_FUNCTION,
                pattern_id=PatternId.P01_FACTORY,
                line=node.lineno,
                content=get_line(node.lineno),
                hint="Avoid validation functions. Use Parse-Don't-Validate via Types.",
            )

    return None


# =============================================================================
# 3. SHELL (Entry Point)
# =============================================================================

# -- Cursor Hook Schema --


class FileEditHook(BaseModel):
    model_config = {"frozen": True}
    hook_event_name: Literal["afterFileEdit"]
    workspace_roots: list[str] = []
    file_path: Path
    edits: list[dict[str, Any]] = []


class StopHook(BaseModel):
    model_config = {"frozen": True}
    hook_event_name: Literal["stop"]
    workspace_roots: list[str] = []
    status: str


# Discriminated Union for Input (Only exact matches)
type CursorHookType = Annotated[
    FileEditHook | StopHook, Field(discriminator="hook_event_name")
]


class CursorHookInput(RootModel[CursorHookType]):
    root: CursorHookType


# Output Schemas
class MessageOutput(BaseModel):
    model_config = {"frozen": True}
    kind: Literal["message"] = "message"
    agent_message: str


class NoOutput(BaseModel):
    model_config = {"frozen": True}
    kind: Literal["no_output"] = "no_output"


# -- Internal Context --


class EditInput(BaseModel):
    file_path: Path
    content: str


def parse_input(raw: str) -> CursorHookType | None:
    try:
        return CursorHookInput.model_validate_json(raw).root
    except (ValidationError, json.JSONDecodeError):
        return None


def write_feedback(file_path: Path, signals: list[Signal]) -> None:
    """Side Effect: Write violations to the feedback file."""
    # Assume .cursor/ is relative to script location
    path = Path(__file__).parent.parent / "mirror-feedback.md"

    if not signals:
        if path.exists():
            path.write_text("", encoding="utf-8")
        return

    output_lines = [f"## Architect's Mirror: {file_path.name}\n"]
    output_lines.append("### Signals Detected\n")
    for sig in signals:
        output_lines.append(f"- **Line {sig.line}** [{sig.kind}]: `{sig.content}`")
        output_lines.append(f"  - Hint: {sig.hint}")
        output_lines.append(f"  - Pattern: {sig.pattern_id}\n")

    path.write_text("\n".join(output_lines), encoding="utf-8")


def main() -> None:
    cli_mode = len(sys.argv) > 1
    edit_input: EditInput | None = None

    # 1. Parse Input
    if cli_mode:
        # CLI Mode: python mirror.py <file>
        try:
            path = Path(sys.argv[1])
            content = path.read_text(encoding="utf-8")
            edit_input = EditInput(file_path=path, content=content)
        except Exception:
            return
    else:
        # Hook Mode: stdin
        if sys.stdin.isatty():
            return
        raw = sys.stdin.read()
        if not raw:
            return

        hook_input = parse_input(raw)
        if not hook_input:
            return

        if isinstance(hook_input, FileEditHook):
            # Read file from disk (Cursor may have updated it)
            try:
                content = hook_input.file_path.read_text(encoding="utf-8")
                edit_input = EditInput(file_path=hook_input.file_path, content=content)
            except Exception:
                return
        else:
            # StopHook: Clear feedback on stop
            write_feedback(Path("stop"), [])
            return

    if not edit_input:
        return

    # 2. Execute Logic
    try:
        tree = ast.parse(edit_input.content)
    except SyntaxError:
        return

    lines = edit_input.content.splitlines()

    def get_line(n: int) -> str:
        if 1 <= n <= len(lines):
            return lines[n - 1].strip()
        return ""

    signals: list[Signal] = []
    for node in ast.walk(tree):
        sig = detect_signal(node, edit_input.file_path, get_line)
        if sig:
            signals.append(sig)

    # 3. Output (Side Effect)
    if not cli_mode:
        write_feedback(edit_input.file_path, signals)
    else:
        # CLI Output to stdout
        if not signals:
            print("✅ No signals.")
        else:
            for sig in signals:
                print(f"[Line {sig.line}] {sig.kind}: {sig.hint}")


if __name__ == "__main__":
    main()
