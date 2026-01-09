---
description: "Naming Conventions — Concepts over Layers. No generic filenames."
globs: ["**/*.py"]
alwaysApply: false
---

# Naming Conventions

## The Principle
File names must describe the **Business Concept** or **Specific Role** they contain, not a generic technical pattern. Generic names create "Junk Drawers" where unrelated logic accumulates. Specific names create **Context Boundaries**.

---

## ❌ Anti-Pattern: Layer Naming

Naming files after the "Layer" or "Pattern" obscures the content.

```text
domain/
  └── order/
      ├── model.py    # ❌ Generic. Every file is a model?
      ├── logic.py    # ❌ Generic. What kind of logic?
      ├── utils.py    # ❌ The Junk Drawer.
      ├── helpers.py  # ❌ The other Junk Drawer.
      └── intent.py   # ❌ Generic Pattern Name.
```

---

## ✅ Pattern: Concept Naming

Name files after the **Thing** or the **Process**.

```text
domain/
  └── order/
      ├── order.py         # ✅ The Aggregate Root
      ├── fulfillment.py   # ✅ Specific Workflow
      ├── pricing.py       # ✅ Specific Logic
      └── contract.py      # ✅ Data Contracts (Intents/Results)
```

---

## Allowed Exceptions (Boundary Files)

Some files define the **Boundary itself**, so the technical name is the concept.

| Filename | Role | Allowed? |
| :--- | :--- | :--- |
| `api.py` | API Contract (see below) | ✅ |
| `db.py` | Foreign Reality (DB Schema) | ✅ |
| `vendor.py` | Foreign Reality (3rd Party) | ✅ |
| `config.py` | Environment Schema | ✅ |
| `main.py` | Composition Root | ✅ |
| `conftest.py` | Test Fixtures | ✅ |
| `__init__.py` | Package Marker | ✅ |

---

## API Structure (Structural Colocation)

The domain defines its own API contract. "The Thing IS The Thing" applies to boundaries too.

```text
# ✅ CORRECT: Domain owns its contract
domain/
  └── event/
      ├── store.py        # Active Model
      ├── publishing.py   # Intents/Outcomes
      └── api.py          # Request/Response models (the contract)

api/
  └── event.py            # FastAPI wiring (imports from domain/event/api.py)

# ❌ WRONG: Contract separated from domain
domain/
  └── event/
      └── store.py

api/
  └── event.py            # Contains BOTH routes AND request/response models
```

**Why:** The domain knows what it exposes. Request/response models are part of the domain's contract, not framework concerns. The `api/` directory contains only framework wiring (route registration, dependency injection).

---

## Constraints

| Required | Forbidden |
|----------|-----------|
| **`domain/context/concept.py`** | `domain/context/model.py` |
| **`domain/context/workflow.py`** | `domain/context/process.py` (Too vague) |
| **`domain/context/contract.py`** | `domain/context/intent.py` |
| **`service/specific_service.py`** | `service/service.py` |
| **`shared/money.py`** | `shared/utils.py` |
| **Rename `helpers.py` to `[concept].py`** | `helpers.py` |
