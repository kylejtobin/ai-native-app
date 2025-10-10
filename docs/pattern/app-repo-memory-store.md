# Memory Store Repository Pattern

> **Cache and queue operations with observability**

## Overview

Memory stores handle fast key-value operations (cache) and queue operations. Repository provides observability and semantic operations.

**Current implementation:** Redis
**Future options:** Memcached, Valkey, KeyDB

---

## Repository Interface

```python
from typing import Protocol

class CacheRepository(Protocol):
    async def get(self, key: CacheKey) -> bytes | None:
        """Get cached value."""
        ...
    
    async def set(self, key: CacheKey, value: bytes, ttl: Duration) -> None:
        """Set with TTL."""
        ...

class QueueRepository(Protocol):
    async def push(self, queue: QueueName, message: Message) -> None:
        """Push to queue."""
        ...
    
    async def pop(self, queue: QueueName) -> Message | None:
        """Pop from queue."""
        ...
```

---

## Redis Implementation

```python
import logfire
from redis.asyncio import Redis

class RedisQueueRepository:
    def __init__(self, client: Redis):
        self.client = client
    
    async def push(self, queue: QueueName, message: Message) -> None:
        with logfire.span(
            "repo.queue.push",
            queue=queue.value,
            size=len(message.model_dump_json())
        ):
            await self.client.rpush(
                queue.value,
                message.model_dump_json()
            )
```

---

## Related Patterns

- **app-repo.md** - Generic repository pattern
- **app-persistence.md** - Storage strategy overview

---

*This file will be expanded when implementing message/cache domains.*
