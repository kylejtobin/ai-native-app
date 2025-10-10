# Graph Store Repository Pattern

> **Graph traversal operations with observability**

## Overview

Graph stores handle relationship-based queries and graph traversal. Repository hides query language (Cypher) from domain.

**Current implementation:** Neo4j
**Future options:** ArangoDB, TigerGraph

---

## Repository Interface

```python
from typing import Protocol

class GraphRepository(Protocol):
    async def find_related(
        self,
        node: NodeId,
        relationship: RelationType,
        depth: int
    ) -> list[Node]:
        """Find related nodes."""
        ...
    
    async def create_relationship(
        self,
        from_node: NodeId,
        to_node: NodeId,
        rel_type: RelationType
    ) -> Relationship:
        """Create relationship."""
        ...
```

---

## Neo4j Implementation

```python
import logfire
from neo4j import AsyncDriver

class Neo4jGraphRepository:
    def __init__(self, driver: AsyncDriver):
        self.driver = driver
    
    async def find_related(
        self,
        node: NodeId,
        relationship: RelationType,
        depth: int
    ) -> list[Node]:
        with logfire.span(
            "repo.graph.traverse",
            node_id=str(node.value),
            rel_type=relationship.value,
            depth=depth
        ) as span:
            # Cypher hidden from domain
            query = """
                MATCH (n)-[r:%s*1..%d]->(m)
                WHERE n.id = $node_id
                RETURN m
            """ % (relationship.value, depth)
            
            result = await self.driver.execute_query(query, node_id=str(node.value))
            nodes = [self._to_domain(record) for record in result]
            span.set_attribute("results_count", len(nodes))
            return nodes
```

---

## Related Patterns

- **app-repo.md** - Generic repository pattern
- **app-persistence.md** - Storage strategy overview

---

*This file will be expanded when implementing graph domain.*
