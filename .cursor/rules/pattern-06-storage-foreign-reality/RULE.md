---
description: "Pattern 06: Storage — Database as Foreign Reality with explicit translation."
globs: ["**/domain/**/*.py", "**/service/**/*.py"]
alwaysApply: false
---

# Pattern 06: Storage Foreign Reality

## Valid Code Structure

```python
# Smart Enum
class StorageResultKind(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"

# Foreign Model: Represents the database row shape
class DbOrder(BaseModel):
    model_config = {"frozen": True}
    
    id: OrderId
    status: OrderStatus
    amount_cents: PositiveInt
    
    def to_domain(self) -> Order:
        return Order(
            id=self.id,
            status=self.status,
            amount=Money.from_cents(self.amount_cents),
        )

# Query Result: Explicit Sum Type
class OrderFound(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[StorageResultKind.FOUND]  # NO DEFAULT
    order: Order

class OrderNotFound(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[StorageResultKind.NOT_FOUND]  # NO DEFAULT
    order_id: OrderId

type FetchOrderResult = OrderFound | OrderNotFound

# The Store: Active Domain Model (Capability)
class OrderStore(BaseModel):
    """
    Active Capability. Encapsulates the Database Client.
    Lives in the Domain (Schema + Logic).
    """
    model_config = {"frozen": True, "arbitrary_types_allowed": True}
    
    # Injected Tool (Client)
    db: Any 
    table_name: TableName
    
    async def load(self, order_id: OrderId) -> FetchOrderResult:
        # The Domain Model executes the query via the Tool.
        # "The thing is the thing."
        row = await self.db.fetch_one(
            select(self.table_name).where(id=order_id)
        )
        
        # Translation
        if not row:
            return OrderNotFound(kind=StorageResultKind.NOT_FOUND, order_id=order_id)
            
        return OrderFound(
            kind=StorageResultKind.FOUND, 
            order=DbOrder.model_validate(row).to_domain()
        )
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| `DbModel` with `.to_domain()` method | Repository pattern with abstract interface |
| `Found \| NotFound` Sum Type | `return None` for not found |
| **Store is a Domain Model** | **Store is a Service Class** |
| **Capability (DB) Injected into Store** | **Global DB Access** |
| `DbOrder.model_validate(row).to_domain()` | Raw dict passing |
| **Typed IDs (OrderId)** | **String IDs (str)** |
| **Smart Enums for Kinds** | **String Literals for Kinds** |
