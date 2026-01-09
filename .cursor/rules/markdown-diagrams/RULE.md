---
description: "Mermaid syntax rules for creating diagrams in markdown files"
globs: ["**/*.md"]
alwaysApply: false
---

# Mermaid Syntax Rules

## Valid Code Structure

### Graph Diagrams (Flowcharts)
```mermaid
graph TB
    A[Service] --> B[Database]
    B -->|Query Results| A
```

### State Diagrams
```mermaid
stateDiagram-v2
    [*] --> Active
    note right of Active
        ✅ Supported: Special chars
        • Bullet points
        ❌ Error markers
    end note
```

### Sequence Diagrams
```mermaid
sequenceDiagram
    participant Router as API Router
    participant Service
    
    Router->>Service: Request
    Service-->>Router: Response
```

## Constraints

| Supported | Forbidden |
|-----------|-----------|
| **Diagram Type Declaration** (must start with graph/flowchart/etc) | Missing diagram type |
| **Special Characters** (✅, ❌, •) in notes | Malformed syntax blocks |
| **Complex Labels** ("Service Name") | `<br>` tags (use `\n` or newlines in notes) |
| **RGB Colors** (`rect rgb(...)`) | |
| **Participant Aliases** (`participant A as Alias`) | |

