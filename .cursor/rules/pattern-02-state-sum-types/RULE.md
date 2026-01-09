---
description: "Pattern 02: State — Sum Types over Product Types. Make invalid states unrepresentable."
globs: ["**/domain/**/*.py", "**/entity.py", "**/process.py"]
alwaysApply: false
---

# Pattern 02: State Sum Types

## Valid Code Structure

```python
# Smart Enum (State Engine)
class OrderStatus(StrEnum):
    PENDING = "pending"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (self.SHIPPED, self.CANCELLED)

# Each state is its own type with only valid data for that state
class PendingOrder(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[OrderStatus.PENDING]
    id: OrderId
    items: tuple[OrderItem, ...]
    
    def ship(self, tracking_id: TrackingId, shipped_at: datetime) -> "ShippedOrder":
        """Transition: Pending → Shipped. Pure Calculation."""
        return ShippedOrder(
            kind=OrderStatus.SHIPPED,
            id=self.id,
            items=self.items,
            tracking_id=tracking_id,
            shipped_at=shipped_at,  # Passed in, not read from clock
        )
    
    def cancel(self, reason: CancellationReason) -> "CancelledOrder":
        """Transition: Pending → Cancelled."""
        return CancelledOrder(kind=OrderStatus.CANCELLED, id=self.id, reason=reason)

class ShippedOrder(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[OrderStatus.SHIPPED]
    id: OrderId
    items: tuple[OrderItem, ...]
    tracking_id: TrackingId  # Structural proof: MUST exist in shipped state
    shipped_at: datetime

class CancelledOrder(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[OrderStatus.CANCELLED]
    id: OrderId
    reason: CancellationReason

# Sum Type
type Order = Annotated[
    PendingOrder | ShippedOrder | CancelledOrder,
    Field(discriminator="kind")
]
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| Separate type per state | One class with `status: str` field |
| **Smart Enum for Kind** | **String Literal for Kind** |
| Transition methods on source state | Standalone `def ship_order()` functions |
| Structural proof (data exists only in valid states) | `Optional[tracking_id]` on all states |
| `match/case` for handling | `if order.status == "shipped"` |
| **Pass Data (timestamp), not Services (Clock)** | **Injecting Clock/Service into Domain** |
| **Value Objects (TrackingId)** | **Primitives (str)** |
