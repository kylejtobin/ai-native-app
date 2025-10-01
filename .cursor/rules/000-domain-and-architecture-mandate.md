---  
description: “Enforce domain-model & architectural mandates (DOs and DON’Ts)”  
globs: ["**/*"]  
alwaysApply: true  
---

## DO Mandates

**Domain Models:**  
- All business logic MUST live in domain model methods, never in services/controllers  
- Every model MUST use `frozen=True` - no mutable state  
- All fields MUST have explicit Pydantic types with constraints  
- State changes MUST return new instances, never mutate existing

**Type System:**  
- Every function parameter and return MUST have type annotations  
- Domain concepts MUST be modeled as distinct Pydantic types, never primitives  
- Validation rules MUST be encoded in Pydantic field validators, never runtime checks  
- API contracts MUST be Pydantic models defining request/response schemas

**Services:**  
- Services MUST only orchestrate domain methods and coordinate I/O  
- Business logic MUST be delegated to domain, never implemented in service  
- Dependencies MUST be explicitly injected, never imported or constructed internally  
- Data transformations MUST happen in domain, services only pass data between layers

**Testing:**  
- Tests MUST verify business logic and behavior, never Pydantic validation  
- Tests MUST verify domain method transformations, never serialization/deserialization  
- Tests MUST verify immutable updates work correctly, never that frozen=True prevents mutation  
- Integration tests MUST use real infrastructure when testing contracts between systems

---

## DON'T Mandates

**Forbidden Patterns:**  
- NEVER write runtime validation that Pydantic field constraints already enforce  
- NEVER mutate model state - no setters, no direct field assignment after construction  
- NEVER use primitive types (str, int, UUID) for domain concepts - wrap in Pydantic models  
- NEVER implement business logic in API routers, service functions, or utility modules  
- NEVER write try/except for ValidationError on model construction in business logic  
- NEVER test that Pydantic validates types correctly or that frozen models raise on mutation  
- NEVER use isinstance/type checks in business logic - use Pydantic discriminated unions  
- NEVER store mutable collections (list, dict, set) in models - use tuple or frozenset  
- NEVER pass primitive dicts/lists between layers - use Pydantic models for all boundaries  
- NEVER import domain models into infrastructure layer - only service layer knows domain
