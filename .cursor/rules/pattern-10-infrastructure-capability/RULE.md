---
description: "Pattern 10: Infrastructure — Capability as Data. Domain declares abstract needs, Service binds to technology."
globs: ["**/service/**/*.py", "**/domain/**/store.py", "**/domain/**/failure.py"]
alwaysApply: false
---

# Pattern 10: Infrastructure Capability as Data

## Valid Code Structure

```python
# DOMAIN: Active Capability Model (Holds Client)
class EventStore(BaseModel):
    """
    Active Domain Model.
    Encapsulates the Infrastructure Client and Logic.
    """
    model_config = {"frozen": True, "arbitrary_types_allowed": True}
    
    # Configuration
    topic_name: TopicName
    
    # Injected Tool (Client)
    client: NatsClient

    async def publish(self, event: DomainEvent) -> EventResult:
        """
        The Domain Model executes the capability.
        "The thing is the thing."
        """
        # Direct Execution (No defensive try/catch for structural failure)
        # If NATS is down, let it crash or handle at higher level.
        # If we need Railway result for "Network Error", we handle it here.
        
        try:
            await self.client.publish(
                self.topic_name, 
                event.model_dump_json()
            )
            return EventStored(kind=EventResultKind.STORED)
        except NatsError:
            # Expected Business Failure (Network) -> Result
            return EventFailed(kind=EventResultKind.FAILED)
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| **Capability is an Injected Model** | **Capability is an Interface/Protocol** |
| **Model holds the Client** | **Model holds only Config (Passive)** |
| **Model executes Logic** | **Service executes Logic (Anemic)** |
| **Direct Construction/Casting** | **Manual Mapper Functions** |
| Failure modes as abstract `StrEnum` | Technology-specific configs in domain |
| All fields explicit, no defaults | Side effects on model init |
| **Real Clients (or Test Doubles)** | **Mocks** |
