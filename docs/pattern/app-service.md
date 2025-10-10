# Domain Service Pattern

> **Services are domain models that orchestrate business processes**

## File Structure

```
src/
  domain/
    user.py          # Entity models (User aggregate)
    order.py         # Entity models (Order aggregate)
    auth.py          # Service model (AuthService orchestrator)

  service/
    auth.py          # Infrastructure adapter (owns clients, calls domain service)
```

**Key principle**: Services are Pydantic models in `domain/` that orchestrate workflows. Infrastructure adapters in `service/` own infrastructure and delegate to domain services.

---

## The Problem: Orchestration in Infrastructure

Traditional approach puts workflow logic in infrastructure services:

```python
# Infrastructure service with orchestration logic
class OrderService:
    def __init__(self, db: Database):
        self.db = db  # Service owns infrastructure

    def cancel_order(self, order_id: UUID) -> Order:
        # ❌ Workflow orchestration in infrastructure layer!
        order = self.db.get(order_id)

        if order.status not in ["pending", "confirmed"]:
            raise ValueError("Cannot cancel")

        order.status = "cancelled"
        self.db.save(order)
        return order
```

**Problems**:
- Orchestration logic tied to infrastructure
- Can't test workflows without database
- Violates domain-driven design
- Services aren't data (can't serialize/log workflows)

---

## The Solution: Domain Services

Services are domain models (Pydantic) that orchestrate. Infrastructure adapters just provide dependencies:

```python
# domain/order.py
class OrderService(BaseModel):
    """Service IS a domain model - pure orchestration logic."""
    model_config = {"frozen": True}

    async def cancel_order(
        self,
        order_id: OrderId,
        order_repo: OrderRepositoryProtocol,  # Injected
    ) -> Order:
        # 1. Load (orchestration logic)
        order = await order_repo.get(order_id)

        # 2. Business logic (entity decides)
        cancelled = order.cancel()

        # 3. Save (orchestration logic)
        await order_repo.save(cancelled)

        return cancelled

# service/order.py
class OrderServiceRunner:
    """Infrastructure adapter - owns clients, delegates to domain."""
    def __init__(self, settings: Settings):
        # Service owns its DB infrastructure
        self.engine = settings.postgres_engine()
        self.session_factory = async_sessionmaker(self.engine)
        self.order_service = OrderService()  # Domain model

    async def cancel_order(self, order_id: OrderId) -> Order:
        # Create session, pass to domain service
        async with self.session_factory() as session:
            try:
                repo = OrderRepository(session)
                result = await self.order_service.cancel_order(order_id, repo)
                await session.commit()
                return result
            except:
                await session.rollback()
                raise
```

**Benefits**:
- Orchestration logic IS domain knowledge (in domain layer)
- Service is pure Pydantic (serializable, loggable)
- Infrastructure adapter is truly thin (just dependency injection)
- "The whole program is data"

---

## The Pattern

### Three Layers

1. **Domain Entities** - Business rules on single concepts (`Order.cancel()`)
2. **Domain Services** - Orchestration of workflows (Pydantic models in `domain/`)
3. **Infrastructure Adapters** - Own infrastructure clients, delegate to domain (in `service/`)

### The Standard Flow

```python
# domain/order.py - Domain service (Pydantic model)
class OrderService(BaseModel):
    model_config = {"frozen": True}

    async def cancel_order(
        self,
        order_id: OrderId,
        order_repo: OrderRepositoryProtocol,  # Protocol, not concrete
    ) -> Order:
        # Orchestration logic (domain knowledge)
        order = await order_repo.get(order_id)
        cancelled = order.cancel()  # Entity decides
        await order_repo.save(cancelled)
        return cancelled
```

This is the **Load → Entity.method() → Save** pattern in a domain service.

---

## Domain Service Responsibilities

### 1. Orchestrate Workflows

Domain services know the **sequence** of steps (business process knowledge):

```python
class AuthService(BaseModel):
    """Auth workflows are domain knowledge."""
    model_config = {"frozen": True}

    async def login_user(
        self,
        email: EmailAddress,
        password: PasswordPlain,
        user_repo: UserRepositoryProtocol,
        clock: ClockProtocol,
        crypto: CryptoProtocol,
    ) -> LoginResult:
        # Orchestration = business process
        user = await user_repo.get_by_email(email)
        auth_result = user.authenticate(password)  # Entity decides

        match auth_result:
            case ValidCredentials(user=user):
                now = clock.utc_now()
                token = crypto.sign_jwt(...)
                return LoginSuccess(user=user, token=token)
            case InvalidPassword():
                return LoginFailure(...)
```

### 2. Coordinate Multiple Entities

When workflows touch multiple entities:

```python
class OrderService(BaseModel):
    model_config = {"frozen": True}

    async def assign_order(
        self,
        order_id: OrderId,
        user_id: UserId,
        order_repo: OrderRepositoryProtocol,
        user_repo: UserRepositoryProtocol,
    ) -> tuple[Order, User]:
        # Orchestration logic
        order = await order_repo.get(order_id)
        user = await user_repo.get(user_id)

        # Entities decide business rules
        if not user.can_take_order(order):
            raise ValueError("User at capacity")

        assigned_order = order.assign_to(user_id)
        updated_user = user.add_order(order_id)

        # Orchestration coordinates saves
        await order_repo.save(assigned_order)
        await user_repo.save(updated_user)

        return assigned_order, updated_user
```

### 3. Infrastructure Adapters

Infrastructure adapters own clients and handle transactional boundaries:

```python
# service/order.py - Infrastructure adapter
class OrderServiceRunner:
    """Owns infrastructure, delegates to domain service."""

    def __init__(self, settings: Settings):
        # Service owns its DB infrastructure
        self.engine = settings.postgres_engine()
        self.session_factory = async_sessionmaker(self.engine)
        self.order_service = OrderService()  # Domain service

    async def assign_order(
        self,
        order_id: OrderId,
        user_id: UserId,
    ) -> tuple[Order, User]:
        # Infrastructure adapter handles transaction
        async with self.session_factory() as session:
            try:
                order_repo = OrderRepository(session)
                user_repo = UserRepository(session)

                # Delegate to domain service
                result = await self.order_service.assign_order(
                    order_id, user_id, order_repo, user_repo
                )
                await session.commit()
                return result
            except:
                await session.rollback()
                raise
```

---

## Minimal Example

```python
# domain/order.py - Domain service (Pydantic model)
class OrderService(BaseModel):
    """Domain service orchestrates order workflows."""
    model_config = {"frozen": True}

    async def cancel_order(
        self,
        order_id: OrderId,
        order_repo: OrderRepositoryProtocol,
    ) -> Order:
        """Cancel order workflow."""
        order = await order_repo.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")

        cancelled = order.cancel()  # Entity decides
        await order_repo.save(cancelled)
        return cancelled

# service/order.py - Infrastructure adapter
class OrderServiceRunner:
    """Infrastructure adapter delegates to domain service."""

    def __init__(self, settings: Settings):
        # Service owns its DB infrastructure
        self.engine = settings.postgres_engine()
        self.session_factory = async_sessionmaker(self.engine)
        self.order_service = OrderService()  # Domain model

    async def cancel_order(self, order_id: OrderId) -> Order:
        """Infrastructure entry point."""
        async with self.session_factory() as session:
            try:
                repo = OrderRepository(session)
                result = await self.order_service.cancel_order(order_id, repo)
                await session.commit()
                return result
            except:
                await session.rollback()
                raise
```

---

## Anti-Patterns

### ❌ Orchestration in Infrastructure Layer

```python
# WRONG - Infrastructure owns workflow logic
class OrderServiceRunner:
    def __init__(self, storage: Storage):
        self.storage = storage

    async def cancel_order(self, order_id: OrderId) -> Order:
        # ❌ Orchestration logic in infrastructure adapter!
        order = await self.load(order_id)
        cancelled = order.cancel()
        await self.save(cancelled)
        return cancelled
```

**Fix**: Move orchestration to domain service, adapter just delegates

### ❌ Domain Service Owns Infrastructure

```python
# WRONG - Domain service owns infrastructure
class OrderService(BaseModel):
    storage: StorageService  # ❌ Infrastructure in domain!

    async def cancel_order(self, order_id: OrderId) -> Order:
        order = await self.storage.load(order_id)
        ...
```

**Fix**: Accept infrastructure via method parameters (protocols)

### ❌ Business Logic in Infrastructure Adapter

```python
# WRONG - Infrastructure adapter contains business logic
class OrderServiceRunner:
    async def cancel_order(self, order_id: OrderId) -> Order:
        order = await self.load(order_id)
        # ❌ Business logic in adapter!
        if order.status not in [OrderStatus.PENDING]:
            raise ValueError("Cannot cancel")
        ...
```

**Fix**: Business logic goes in entity methods (`order.cancel()`)

---

## When to Use This Pattern

**Always.** Every orchestration workflow is a domain service.

Domain services are appropriate for:
- Multi-step workflows (login, register, checkout)
- Cross-entity coordination (transfer between accounts)
- Business processes (order fulfillment, approval flows)

Infrastructure adapters are needed when:
- You own infrastructure clients (databases, APIs, message queues)
- You need transaction management
- You integrate with external systems

---

## Key Takeaways

1. **Services ARE domain models** - Pydantic models in `domain/` directory
2. **Orchestration IS domain knowledge** - Workflow sequences are business logic
3. **Infrastructure adapters are thin** - Just dependency injection and delegation
4. **"The whole program is data"** - Services can be serialized, logged, traced (Logfire)
5. **Three layers**: Entities (decide) → Services (orchestrate) → Adapters (provide infra)

## Next

- **app.md** - Review rich domain entity foundations
- **app-service-db.md** - How to handle SQL databases with repositories
