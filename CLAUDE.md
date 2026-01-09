# CLAUDE.md

---

# PART I: EMDCA Architecture (Generic)

This section applies to **any project** using Explicitly Modeled Data-Centric Architecture. Copy this entire Part I to new EMDCA projects.

## Philosophy: "The Thing IS The Thing"

EMDCA rejects enterprise layering. Domain Models are not passive data containers—they are **Active agents** that hold infrastructure clients and execute their own capabilities.

```
WRONG: Service holds Client → Service takes Model → Service calls Client
RIGHT: Model holds Client → Model calls Client directly
```

### The Deeper Truth: Curry-Howard in Practice

EMDCA leverages the Curry-Howard correspondence: **types are propositions, values are proofs**.

- If you can construct a `ShippedOrder`, that IS proof it has a `tracking_id`
- If you have a `StreamEnsured`, that IS proof the stream exists
- Invalid states aren't "handled"—they're **unrepresentable**

This transforms your type system into a **logic engine**. Algebraic Data Types (Sum Types + Product Types) make illegal states uncompilable. The compiler becomes your proof assistant.

### Structural Colocation

Logic lives with the data it operates on:

| Concern | Lives On |
|---------|----------|
| Serialization | The Value Object (`@model_serializer`) |
| State transitions | The source state type (`def ship() -> ShippedOrder`) |
| Intent resolution | The Intent (`def resolve() -> Outcome`) |
| Validation | The type definition (Pydantic validators) |

No logic scattered across service layers. Each type is a complete, self-sufficient unit.

---

## The 10 Mandates

### 1. Construction: Crash on Invalid Input

Invalid input is a structural failure—crash with `ValidationError`, don't branch.

```python
# EMDCA: Type system enforces validity
class Email(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: EmailStr  # Pydantic validates, crashes if invalid

# WRONG: Manual validation branching
def create_email(s: str) -> Email | None:
    if "@" in s: return Email(value=s)  # NO
```

### 2. State: Sum Types Make Invalid States Unrepresentable

Each state is its own type. Data only exists in states where it's valid.

```python
class OrderStatus(StrEnum):
    PENDING = "pending"
    SHIPPED = "shipped"

class PendingOrder(BaseModel):
    kind: Literal[OrderStatus.PENDING]
    items: tuple[Item, ...]
    # No tracking_id - doesn't exist yet

class ShippedOrder(BaseModel):
    kind: Literal[OrderStatus.SHIPPED]
    items: tuple[Item, ...]
    tracking_id: TrackingId  # MUST exist - not Optional

Order = PendingOrder | ShippedOrder  # Discriminated union
```

### 3. Control Flow: Railway-Oriented Results

Structural failures crash. Business failures return typed results.

```python
# Value Object does the logic, returns result
class Balance(BaseModel):
    value: Decimal

    def subtract(self, amount: Decimal) -> Balance | InsufficientFunds:
        if amount > self.value:
            return InsufficientFunds(requested=amount, available=self.value)
        return Balance(value=self.value - amount)

# Domain Model delegates, matches result
class Account(BaseModel):
    balance: Balance

    def withdraw(self, amount: Decimal) -> WithdrawnAccount | WithdrawalFailed:
        match self.balance.subtract(amount):
            case Balance() as new_balance:
                return WithdrawnAccount(balance=new_balance)
            case InsufficientFunds() as failure:
                return WithdrawalFailed(reason=failure)
```

### 4. Execution: Active Models Hold Capabilities

Domain Models hold infrastructure clients and execute directly.

```python
class NatsEventStore(BaseModel):
    """Active Model - holds client, executes capabilities."""
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    kind: Literal["nats"]
    client: Client           # The actual NATS client
    js: JetStreamContext     # The actual JetStream context

    async def publish(self, op: PublishEvent) -> EventPublished:
        # Model executes its own capability
        ack = await self.js.publish(
            subject=op.subject.value,
            payload=op.payload,
        )
        return op.resolve(sequence=SequenceNumber(value=ack.seq))
```

### 5. Configuration: AppConfig is Environment Schema

Single `BaseSettings` subclass. Crashes on missing config.

```python
class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    database_url: PostgresDsn = Field(alias="DATABASE_URL")
    nats_url: str = Field(alias="NATS_URL")

    # No defaults for required config - crash if missing
```

### 6. Storage: Stores are Active Domain Models

Stores hold DB clients, execute queries, return domain types.

```python
class OrderStore(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    kind: Literal["postgres"]
    pool: asyncpg.Pool

    async def find(self, order_id: OrderId) -> Order | NotFound:
        row = await self.pool.fetchrow("SELECT ...", order_id.value)
        if not row:
            return NotFound(entity="Order", id=order_id)
        return DbOrder.model_validate(dict(row)).to_domain()
```

### 7. Translation: Foreign Models at Boundaries

External data enters through Foreign Models that mirror external schema exactly.

```python
# Foreign Model - mirrors external API exactly
class CoinbaseTickerRaw(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str = Field(alias="product_id")
    price: str  # Coinbase sends strings

    def to_domain(self) -> Ticker:
        return Ticker(
            symbol=Symbol(value=self.product_id),
            price=Price(value=Decimal(self.price)),
        )

# Translation chain
ticker = CoinbaseTickerRaw.model_validate(raw_json).to_domain()
```

### 8. Coordination: Runtimes are Domain Models

Orchestrators are frozen Pydantic models that coordinate other models.

```python
class OrderRuntime(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    store: OrderStore
    gateway: PaymentGateway

    async def process(self, command: ProcessOrder) -> OrderProcessed | OrderFailed:
        # Load
        order = await self.store.find(command.order_id)
        # Decide (delegate to domain)
        match order.process(command):
            case (new_state, intent):
                # Save
                await self.store.save(new_state)
                # Execute
                return await self.gateway.execute(intent)
```

### 9. Workflow: State Machine Transitions

Transition methods live on source states, return `(NewState, Intent)`.

```python
class PendingOrder(BaseModel):
    kind: Literal[OrderStatus.PENDING]
    items: tuple[Item, ...]

    def ship(self, tracking: TrackingId) -> tuple[ShippedOrder, NotifyCustomerIntent]:
        """Transition from Pending → Shipped with side-effect intent."""
        new_state = ShippedOrder(
            kind=OrderStatus.SHIPPED,
            items=self.items,
            tracking_id=tracking,
        )
        intent = NotifyCustomerIntent(tracking=tracking)
        return (new_state, intent)
```

### 10. Infrastructure: Inject Real Clients

No Protocol abstractions. Inject actual clients into models.

```python
# EMDCA: Real client injected
class EmailCapability(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    client: smtplib.SMTP  # The actual SMTP client

    async def send(self, email: Email) -> Sent | SendFailed:
        # Execute directly
        ...

# WRONG: Protocol abstraction
class EmailProtocol(Protocol):  # NO - unnecessary indirection
    def send(self, email: Email) -> ...: ...
```

---

## What NOT To Do

| Anti-Pattern | Why | Instead |
|--------------|-----|---------|
| `try/except` in domain | Hides structural failures | Let it crash, fix the bug |
| `Optional[field]` for state data | Invalid states become representable | Use Sum Types |
| Default field values | Implicit construction | Explicit construction always |
| `return None` | Unclear semantics | `NotFound`, `NoOp`, explicit types |
| `typing.Protocol` | Enterprise ceremony | Inject real clients |
| Service classes with logic | Anemic models | Active Domain Models |
| Layer-based filenames | Meaningless organization | Concept-based: `order.py`, `pricing.py` |
| Standalone utility functions | Logic scattered | Logic lives on models |

---

## File Naming: Concepts, Not Patterns

Files describe **business concepts** or **specific roles**.

```
WRONG                          RIGHT
─────                          ─────
model.py                       order.py (the aggregate)
service.py                     fulfillment.py (workflow)
utils.py                       pricing.py (logic)
helpers.py                     notification.py (capability)
intent.py                      contract.py (intents/results)
```

Allowed technical names (when they ARE the concept):
- `api.py` - API contract boundary
- `store.py` - Storage capability
- `config.py` - Environment schema
- `main.py` - Composition root

---

## Value Objects: Self-Serializing Types

Value Objects use `@model_serializer` to auto-unwrap:

```python
class StreamName(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: str = Field(min_length=1, max_length=255)

    @model_serializer
    def ser_model(self) -> str:
        return self.value

# Now: StreamName(value="test").model_dump() → "test"
# Not: {"value": "test"}
```

This enables Response models to hold domain types directly—serialization is colocated with the type.

---

## Intent → Outcome Pattern

Intents carry all data needed to resolve to Outcomes:

```python
class PublishEvent(BaseModel):
    """Intent to publish."""
    kind: Literal[IntentKind.PUBLISH]
    stream: StreamName
    subject: EventSubject
    payload: bytes

    def resolve(self, *, sequence: SequenceNumber) -> EventPublished:
        """Resolve with infrastructure-provided data."""
        return EventPublished(
            kind=PublishResultKind.PUBLISHED,
            stream=self.stream,
            sequence=sequence,  # Only new info from infra
            subject=self.subject,
        )
```

If Intent has all data: `resolve()` takes no args.
If infra provides new data: `resolve()` takes only that data.

---

## Smart Enums: Behavior on State Discriminators

Smart Enums (StrEnum) carry behavior:

```python
class OrderStatus(StrEnum):
    PENDING = "pending"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {OrderStatus.SHIPPED, OrderStatus.CANCELLED}

    @property
    def can_cancel(self) -> bool:
        return self == OrderStatus.PENDING
```

---

## Service Factories: Wiring Only

Services connect to I/O and construct Active Models. No orchestration.

```python
class EventService:
    """Factory - constructs Active Models, nothing else."""

    async def connect(self, op: ConnectBus) -> NatsEventStore:
        client = await nats.connect(op.url.value)
        return NatsEventStore(
            kind="nats",
            client=client,
            js=client.jetstream(),
        )
```

---

## Summary: The EMDCA Mindset

1. **Types are proofs** - If it compiles, it's valid
2. **Models are active** - They hold capabilities, execute logic
3. **State is explicit** - Each state is its own type
4. **Boundaries translate** - Foreign → Domain at entry, Domain → Response at exit
5. **Logic is colocated** - With the data it operates on
6. **Failure is explicit** - `Success | Failure`, never exceptions for business logic
7. **Construction crashes** - Invalid input is a bug, not a branch

## Architectural Mirror

A scanner runs after edits. Check `.cursor/mirror-feedback.md` for violations:

```bash
python3 .cursor/hooks/mirror.py <path/to/file.py>
```

## Rules Reference

Detailed patterns in `.cursor/rules/`:
- `pattern-00-master-architecture/` - Full EMDCA overview
- `pattern-01` through `pattern-10` - Individual mandates
- `naming-conventions/` - Concept-based file naming
- `markdown-diagrams/` - Mermaid syntax rules
