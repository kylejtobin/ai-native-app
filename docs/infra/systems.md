# Infrastructure Systems

**Modern AI applications require specialized databases and services, each optimized for specific workloads.**

This template assembles a polyglot persistence stack where each system excels at its particular job. No single database can do everything well—but together, they create a powerful foundation for AI-native applications.

> **Principle: Every Database is Specialized**
>
> No single database can excel at everything. PostgreSQL's ACID guarantees come at a cost Redis doesn't pay. Qdrant's vector search capabilities require trade-offs Neo4j doesn't make. This is polyglot persistence—using the right tool for each job, not forcing everything into one system that does nothing well.
>
> See: [philosophy.md](../philosophy.md) "Every Database is Specialized"

---

## Decision Framework: When to Add vs Reuse a Service

Before adding a new database to this stack, consider:

**Add a specialized service when:**
- ✅ Different access patterns (OLTP vs OLAP, key-value vs graph traversal)
- ✅ Different durability requirements (cache vs source of truth)
- ✅ Different query capabilities (semantic search, relationship traversal)
- ✅ Performance critical and existing tools can't match

**Reuse existing service when:**
- ✅ Same access pattern, just more data volume
- ✅ Can be modeled as table/collection/key in existing system  
- ✅ No specialized capability needed
- ✅ Operational complexity outweighs performance gain

**Examples from this stack:**
- We use **separate Redis AND PostgreSQL** even though PostgreSQL could cache, because Redis gives us microsecond access and pub/sub that PostgreSQL can't match
- We use **separate Qdrant AND Neo4j** even though both handle relationships, because vector similarity is fundamentally different from graph traversal
- We **don't** add Elasticsearch even though it has vector search, because Qdrant is purpose-built and more performant for our semantic search needs

**Cost of adding a service:**
- One more thing to run, monitor, back up
- More complexity in orchestration
- More secrets to manage
- More operational knowledge required

**When in doubt:** Start with what you have, measure the pain, then specialize.

---

## PostgreSQL - Relational Foundation

**Official Docs:** [PostgreSQL Documentation](https://www.postgresql.org/docs/)

PostgreSQL is your source of truth for structured, transactional data. When you need ACID guarantees, complex joins, foreign key constraints, and mature tooling, PostgreSQL delivers.

**What it's for in this stack:**
- User accounts, authentication, authorization
- Transactional business data (orders, invoices, audit logs)
- Structured application state
- Complex relational queries that require JOIN operations

**Why PostgreSQL 17:** Recent versions (15-17) have dramatically improved parallel query performance, added MERGE statements for upsert operations, and enhanced JSON handling. The `pg_trgm` extension provides powerful fuzzy text search, while `uuid-ossp` handles identifier generation. For an AI application, PostgreSQL is where your "facts" live—the canonical records that everything else references.

**Key PostgreSQL extensions in this stack:**
- `uuid-ossp` - Generate UUIDs natively in SQL
- `pg_trgm` - Trigram-based fuzzy text matching (autocomplete, typo tolerance)
- `unaccent` - Accent-insensitive search (café → cafe)

---

## Redis - The Nervous System

**Official Docs:** [Redis Documentation](https://redis.io/docs/)

Redis is an in-memory data structure store that operates at microsecond latency. In an AI application, it serves as the high-speed connective tissue between components.

**What it's for in this stack:**
- **Conversation history**: LLM context needs to be retrieved instantly. Redis streams make this seamless.
- **Caching**: Expensive LLM API calls? Cache responses by input hash.
- **Rate limiting**: Protect your API budget by tracking request counts per user/key.
- **Session storage**: User authentication state, WebSocket connections.
- **Pub/Sub**: Real-time updates, background job queues.

**Modern AI use case:** When building conversational AI, Redis is often the state store for agent memory. Each conversation turn needs the previous N messages—Redis delivers them in under a millisecond. The alternative (hitting PostgreSQL or disk) adds 10-100ms latency per request, which kills the conversational feel.

Redis Streams (added in Redis 5.0) are particularly powerful for event sourcing and building AI agent workflows. You can replay conversation history, implement retry logic, and maintain audit trails—all at Redis speed.

---

## Qdrant - Vector Search Engine

**Official Docs:** [Qdrant Documentation](https://qdrant.tech/documentation/)

Qdrant is a purpose-built vector database for semantic search and RAG (Retrieval Augmented Generation). It's not a general-purpose database with vector support bolted on—it's engineered from the ground up for billion-scale similarity search.

**What it's for in this stack:**
- **Semantic document search**: "Find documents similar to this query" (RAG)
- **Conversation memory**: "What did we discuss about X?" (semantic recall)
- **Recommendation systems**: "Users who liked this also liked..."
- **Anomaly detection**: "Find outliers in high-dimensional space"

**Why Qdrant over alternatives:** Qdrant implements HNSW (Hierarchical Navigable Small World) indexing, which enables sub-linear search time even with millions of vectors. But the killer feature is **hybrid search**—combining dense embeddings (semantic similarity) with sparse vectors (keyword matching) in a single query.

**Hybrid search explained:** Dense vectors (from models like `text-embedding-3-large`) capture semantic meaning, but they struggle with proper nouns, acronyms, and exact phrase matching. Sparse vectors (BM25-style) handle keywords brilliantly but miss semantic relationships. Qdrant's hybrid search combines both:

```python
# Example: Search for "GraphRAG implementation"
# Dense: Finds "knowledge graph retrieval", "entity-based RAG"
# Sparse: Matches exact term "GraphRAG"
# Hybrid: Best of both → precise and semantic
```

Qdrant also supports **payload filtering** (filter by metadata before search), **quantization** (compress vectors for efficiency), and **distributed deployments** (shard across nodes). For AI applications doing RAG at scale, Qdrant is the gold standard.

---

## Neo4j - Knowledge Graph Engine

**Official Docs:** [Neo4j Documentation](https://neo4j.com/docs/)  
**GraphRAG Context:** [GraphRAG Manifesto](https://neo4j.com/blog/genai/graphrag-manifesto/)

Neo4j is a native graph database optimized for relationship traversal. In the AI era, knowledge graphs have moved from "nice to have" to "essential for accuracy"—and Neo4j is the engine that powers them.

**What it's for in this stack:**
- **GraphRAG**: Entity relationships that reduce LLM hallucinations
- **Domain ontologies**: Model your application's conceptual structure
- **Knowledge graphs**: Entities, relationships, and context for AI reasoning
- **Recommendation engines**: Multi-hop traversals (friends-of-friends, co-purchase patterns)

**Why graphs matter for AI:** Microsoft's GraphRAG research demonstrated that LLMs augmented with knowledge graphs produce significantly more accurate responses than pure vector search (RAG). The key insight: **relationships matter**. Vector search finds similar documents, but graph traversal finds *how things relate*.

**Example use cases:**
- Medical AI: Drug → interacts-with → Drug, Patient → has-condition → Disease
- Legal AI: Case → cites → Case, Statute → applies-to → Jurisdiction  
- Business AI: Customer → purchased → Product, Product → competes-with → Product

**Engineering ontologies:** Neo4j's Cypher query language makes it natural to model domain knowledge. Instead of forcing everything into tables (SQL) or documents (MongoDB), you model concepts as nodes and relationships as edges. When your LLM needs context, it can traverse the graph: "Find all cases that cite Supreme Court precedent *and* involve constitutional issues."

**The GraphRAG pattern:**
1. Extract entities from documents (NER, LLM extraction)
2. Build knowledge graph in Neo4j
3. User query → Vector search (Qdrant) for relevant documents
4. Graph traversal (Neo4j) for entity relationships
5. Combine both contexts → LLM generates answer

Neo4j's APOC library (included in this stack) provides graph algorithms (PageRank, community detection, shortest path) that make sophisticated graph analytics accessible. For AI applications modeling complex domains, Neo4j transforms unstructured knowledge into structured reasoning.

---

## MinIO - Object Storage

**Official Docs:** [MinIO Documentation](https://min.io/docs/minio/linux/index.html)

MinIO provides S3-compatible object storage that you control. In AI/ML workflows, you're constantly dealing with large artifacts—model weights, datasets, document corpora, embeddings—and traditional filesystems don't cut it.

**What it's for in this stack:**
- **Document corpus**: PDFs, images, videos for RAG pipelines
- **Model artifacts**: Fine-tuned model weights, checkpoints, LoRA adapters
- **Dataset storage**: Training data, evaluation sets, benchmark corpora
- **Embeddings backup**: Precomputed vectors for bulk re-indexing
- **Media storage**: User-uploaded files, generated images/audio

**Why object storage matters:** Object storage gives you S3 semantics (buckets, versioning, lifecycle policies) without AWS. This means:
- **Versioning**: Track every change to documents/models
- **Lifecycle policies**: Auto-delete old training runs after 30 days
- **Access control**: Per-bucket policies (public read, private write)
- **S3 API compatibility**: Use boto3, AWS SDKs, any S3 tool

**AI-specific use cases:** When you fine-tune a model, you're generating gigabytes of checkpoints. MinIO stores them with versioning, so you can rollback to any training step. When you build a RAG system, your document corpus lives in MinIO—easily accessible, versioned, and backed up.

The MinIO setup in this stack creates three buckets: `documents/` (RAG corpus), `models/` (ML artifacts), `reports/` (generated outputs). This separation makes lifecycle management simple and provides clear organizational boundaries.

---

## Ollama - Local LLM Inference

**Official Docs:** [Ollama Documentation](https://github.com/ollama/ollama/tree/main/docs)

Ollama is a local LLM runtime that makes running models like Llama 3.2, Mistral, and CodeLlama as easy as `ollama pull llama3.2`. For AI-native applications, having local inference capability is increasingly essential.

**What it's for in this stack:**
- **Development/testing**: Iterate without burning API credits
- **Privacy-sensitive workloads**: PHI, PII, confidential data never leaves your infrastructure
- **Offline capability**: Deploy to air-gapped environments
- **Cost optimization**: Simple queries on local models, complex queries on API

**The hybrid approach:** Modern AI applications increasingly use a hybrid strategy:
- **Local (Ollama)**: Fast models (Llama 3.2 1B, Mistral 7B) for classification, routing, simple queries
- **API (Anthropic/OpenAI)**: Frontier models (Claude Opus, GPT-4) for complex reasoning, long context

This template demonstrates this pattern in the conversation system—a fast local model classifies intent and routes to the appropriate API model. You get the speed and cost benefits of local inference where it makes sense, and the capability of frontier models where you need it.

**Hardware considerations:** Ollama works on CPU (slow but functional) or GPU (fast). For development, CPU inference with smaller models (1B-7B parameters) is sufficient. For production, GPU inference or dedicated API endpoints are recommended.

---

## FastAPI - Modern Python Web Framework

**Official Docs:** [FastAPI Documentation](https://fastapi.tiangolo.com/)

FastAPI is the de facto standard for building Python APIs in 2024-2025, and it's particularly well-suited for AI applications.

**Why FastAPI for AI:**
- **Async/await native**: Critical for LLM streaming responses (tokens as they're generated)
- **Pydantic integration**: Type-safe request/response validation, perfect for LLM structured outputs
- **Automatic OpenAPI docs**: Every endpoint self-documents (Swagger UI at `/docs`)
- **WebSocket support**: Real-time streaming for conversational AI
- **Dependency injection**: Clean architecture for passing configs, database clients, LLM clients

**AI-specific patterns:** When building LLM applications, you're constantly dealing with:
1. **Streaming responses**: Users expect to see tokens as they're generated (not wait 30s for full response)
2. **Structured outputs**: LLMs generate JSON, you validate with Pydantic models
3. **Background tasks**: Embeddings generation, document processing happen async
4. **Rate limiting**: Protect API budgets (FastAPI middleware makes this simple)

FastAPI's async capabilities shine when orchestrating multiple LLM calls. You can fire off embedding generation, vector search, and graph queries in parallel, then combine results—all with clean, readable async code.

**Developer experience:** The automatic documentation alone justifies FastAPI. Every endpoint shows up in `/docs` with example requests, validation rules, and response schemas. For AI APIs that often have complex nested structures, this is invaluable.

---

## The Polyglot Persistence Philosophy

**Why multiple specialized systems?** Each is optimized for its specific workload:

**Data Layer:**
- **PostgreSQL**: ACID transactions, relational integrity
- **Redis**: Microsecond latency, ephemeral state
- **Qdrant**: Billion-scale vector similarity, hybrid search
- **Neo4j**: Graph traversal, relationship-first modeling
- **MinIO**: Object storage, S3 semantics

**Services Layer:**
- **Ollama**: Local LLM inference
- **FastAPI**: Your application (async HTTP, streaming, type safety)

**The alternative** (one database for everything) means:
- Slow vector search (relational DBs aren't built for this)
- Expensive graph queries (joins don't scale to multi-hop traversals)
- Complex object storage (BLOBs in databases are painful)
- No local LLM option (fully API-dependent)

This stack demonstrates **composable infrastructure**—each piece does one thing exceptionally well, and they compose into a system greater than the sum of parts.

**For AI-native applications**, this architecture provides:
- RAG with Qdrant (semantic search)
- GraphRAG with Neo4j (relationship reasoning)
- Hybrid local/API inference with Ollama
- Fast state management with Redis
- Structured data integrity with PostgreSQL
- Artifact management with MinIO
- Modern async APIs with FastAPI

**One command starts everything:**
```bash
make dev  # Complete stack: data layer, LLM inference, and your API
```

---

## Anti-Patterns: What NOT to Do

❌ **DON'T try to use one database for everything**
- "PostgreSQL has JSON support, we don't need separate vector DB"
- Reality: PostgreSQL's pgvector is 10-100x slower than Qdrant for similarity search
- Use specialized tools or accept degraded performance

❌ **DON'T bypass the stack and connect directly to external services**
- "I'll just use OpenAI directly instead of through the model pool"
- Reality: No caching, no rate limiting, no fallback, no local dev option
- The abstraction exists for resilience and flexibility

❌ **DON'T store large files (>1MB) in relational databases**
- "I'll just base64 encode PDFs and put them in PostgreSQL"
- Reality: Slow queries, bloated backups, memory issues
- Use MinIO for objects, store references in PostgreSQL

❌ **DON'T add services without understanding the operational cost**
- "Let's add Elasticsearch AND Qdrant for search"
- Reality: More monitoring, more backups, more points of failure
- Justify each addition with performance measurements

❌ **DON'T ignore Redis expiration for cache**
- "I'll just cache everything forever in Redis"
- Reality: Redis fills up, becomes swap-heavy, slows down
- Always set TTL on cached data

❌ **DON'T use Neo4j like a relational database**
- "I'll store user records in Neo4j because it's cool"
- Reality: Neo4j excels at relationships, not simple CRUD
- Use the right tool: tables in PostgreSQL, graphs in Neo4j

---

## Next Steps

- See [Orchestration](orchestration.md) for how these systems start and coordinate
- See [Configuration](configuration.md) for secrets and environment management
- See [IaC](iac.md) for Docker, containers, and infrastructure principles

