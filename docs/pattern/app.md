# Rich Domain Model Pattern

> **The foundational pattern: business logic lives in immutable domain models**

## File Structure

```
src/
  domain/
    value.py         # ID value objects (UserId, OrderId, etc)
    type.py          # Smart enums with business logic
    user.py          # Rich domain model (User aggregate)
    order.py         # Rich domain model (Order aggregate)
```

**Key principle**: Domain models are in `domain/` module. They import nothing from `service/` or `storage/`.

---

## The Problem: Anemic Models

Traditional approach puts data in classes but logic in services:

```python
# Anemic model - just data
class Order:
    id: UUID
    status: str
    total: float

# Business logic scattered in services/utils
def can_cancel_order(order: Order) -> bool:
    return order.status in ["pending", "confirmed"]

def cancel_order(order: Order) -> Order:
    if not can_cancel_order(order):
        raise ValueError("Cannot cancel")
    order.status = "cancelled"  # Mutation!
    return order
```

**Problems**:
- Business rules scattered across codebase
- Mutable state (unsafe, bugs)
- Rules can be bypassed
- No type safety

---

## The Solution: Rich Domain Models

Put business logic **in** the model itself:

```python
class Order(BaseModel):
    model_config = {"frozen": True}  # Immutable

    id: OrderId
    status: OrderStatus  # Smart enum
    total: Money

    def can_cancel(self) -> bool:
        """Business logic in model."""
        return self.status.is_cancellable()

    def cancel(self) -> Order:
        """Business operation returns new instance."""
        if not self.can_cancel():
            raise ValueError("Cannot cancel")
        return self.model_copy(update={
            "status": OrderStatus.CANCELLED
        })
```

**Benefits**:
- Business logic co-located with data
- Immutable (safe, predictable)
- Type-safe (Pydantic validates)
- Rules cannot be bypassed

---

## The Pattern

### 1. Immutability (`frozen=True`)

**Rule**: Models never mutate. Operations return new instances.

```python
class Aggregate(BaseModel):
    model_config = {"frozen": True}

    field: str

    def update_field(self, new_value: str) -> Aggregate:
        return self.model_copy(update={"field": new_value})
```

### 2. Business Logic Methods

**Rule**: If it's a business rule, it's a method on the model.

```python
class Aggregate(BaseModel):
    status: Status

    def can_perform_action(self) -> bool:
        """Business logic: when is action allowed?"""
        return self.status.allows_action()

    def perform_action(self) -> Aggregate:
        """Business operation with validation."""
        if not self.can_perform_action():
            raise ValueError("Action not allowed")
        return self.model_copy(update={"status": Status.DONE})
```

### 3. Value Objects (IDs Only)

**Rule**: Wrap IDs for type safety. Use Pydantic Field for validation.

```python
# Wrap IDs to prevent mixups
class UserId(RootModel[UUID]):
    root: UUID
    model_config = {"frozen": True}

class OrderId(RootModel[UUID]):
    root: UUID
    model_config = {"frozen": True}

# Don't wrap simple strings - use Field
class Order(BaseModel):
    id: OrderId                                    # Wrapped
    user_id: UserId                                # Wrapped
    description: str = Field(max_length=500)      # Not wrapped
```

### 4. Smart Enums

**Rule**: Enums contain behavior, not external if/else.

```python
class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

    def is_cancellable(self) -> bool:
        """Business logic in enum."""
        return self in {self.PENDING, self.CONFIRMED}

    def can_transition_to(self, target: OrderStatus) -> bool:
        """State machine logic."""
        transitions = {
            self.PENDING: {self.CONFIRMED, self.CANCELLED},
            self.CONFIRMED: {self.SHIPPED, self.CANCELLED},
            self.SHIPPED: set(),
            self.CANCELLED: set(),
        }
        return target in transitions[self]
```

### 5. Computed Properties

**Rule**: Derive values on-demand, don't store them.

```python
class Order(BaseModel):
    items: tuple[OrderItem, ...]

    @property
    def total(self) -> Money:
        """Computed from items."""
        return sum(item.subtotal for item in self.items)

    @property
    def is_empty(self) -> bool:
        """Computed boolean."""
        return len(self.items) == 0
```

---

## When to Use This Pattern

**Always.** This is the foundation for all domain logic.

Rich domain entities are appropriate for:
- Business rules on single concepts (`Order.cancel()`, `User.authenticate()`)
- State transitions (`OrderStatus.can_transition_to()`)
- Validations (`Email.is_valid()`)
- Computed properties (`Order.total`, `User.full_name`)

**Not appropriate for**:
- Multi-step workflows (use domain services - see `app-service.md`)
- Cross-entity coordination (use domain services)
- Infrastructure concerns (repositories, HTTP clients, databases)

---

## Minimal Example

```python
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel, Field, RootModel

# Value objects
class OrderId(RootModel[UUID]):
    root: UUID
    model_config = {"frozen": True}

# Smart enums
class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"

    def is_cancellable(self) -> bool:
        return self == self.PENDING or self == self.CONFIRMED

# Rich domain model
class Order(BaseModel):
    model_config = {"frozen": True}

    id: OrderId
    status: OrderStatus
    total: float = Field(gt=0)

    @property
    def can_cancel(self) -> bool:
        return self.status.is_cancellable()

    def cancel(self) -> Order:
        if not self.can_cancel:
            raise ValueError("Cannot cancel")
        return self.model_copy(update={"status": OrderStatus.CANCELLED})

    def confirm(self) -> Order:
        if self.status != OrderStatus.PENDING:
            raise ValueError("Can only confirm pending orders")
        return self.model_copy(update={"status": OrderStatus.CONFIRMED})
```

---

## Key Takeaways

1. **Business logic in models** - Not in services or utils
2. **Immutable** - `frozen=True`, operations return new instances
3. **Type-safe** - Wrap IDs, use smart enums, Pydantic Field
4. **Self-contained** - Models know their own rules and behavior

## Next

- **app-service.md** - How domain services orchestrate workflows
- **app-service-db.md** - How to persist with SQL and repositories
