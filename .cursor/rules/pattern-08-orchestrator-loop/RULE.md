---
description: "Pattern 08: Coordination — Dumb Orchestrator that moves data, doesn't think."
globs: ["**/service/**/*.py", "**/orchestrator.py"]
alwaysApply: false
---

# Pattern 08: Orchestrator Loop

## Valid Code Structure

```python
# Result Types (Smart Enum)
class PaymentResultKind(StrEnum):
    NOT_FOUND = "not_found"
    PROCESSED = "processed"
    VERIFICATION_REQUIRED = "verification_required"

# The Runtime: Smart Domain Model (Active Orchestrator)
class PaymentRuntime(BaseModel):
    """
    Active Domain Model.
    Drives the process by coordinating other Smart Models.
    Lives in the Domain.
    """
    model_config = {"frozen": True, "arbitrary_types_allowed": True}
    
    # Injected Smart Capabilities
    store: PaymentStore
    gateway: PaymentGateway

    async def run(self, payment_id: PaymentId, event: PaymentEvent) -> ProcessPaymentResult:
        # 1. Load State (Active Store)
        state = await self.store.load(payment_id)
        if not state:
            return PaymentNotFound(kind=PaymentResultKind.NOT_FOUND, payment_id=payment_id)

        # 2. Pure Step (Domain Logic)
        new_state, intent = state.handle(event)

        # 3. Save State (Active Store)
        await self.store.save(payment_id, new_state)

        # 4. Execute Intent (Active Gateway)
        await self.gateway.execute(intent)
        
        return PaymentProcessed(kind=PaymentResultKind.PROCESSED, payment_id=payment_id)
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| **Runtime is a Domain Model** | **Runtime is a Service Class** |
| Logic delegated to Domain `state.handle()` | Logic inside `run()` |
| **Reactive Loop Pattern** | **Procedural Script Pattern** |
| Injected Capabilities (`store`) | Implicit Globals |
| `match/case` for flow control | `raise` for control flow |
| **Smart Enums for Result Kinds** | **Magic Strings for Result Kinds** |
| **Typed IDs (PaymentId)** | **String IDs (str)** |
