# AI-Native App Architecture

**Enterprise-grade architecture template for building intelligent, type-safe AI applications**

This is both a **fully functional stack** and a **teaching resource**. It demonstrates modern patterns for building AI-native applications where infrastructure is code, data models embody business intelligence, and correctness emerges from types. Everything you need to build production AI systems—explained, documented, and ready to run.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Infrastructure Architecture](#infrastructure-architecture)
  - [Getting Started](#getting-started)
  - [The Stack](#the-stack)
  - [Containers & Infrastructure as Code](#containers--infrastructure-as-code)
  - [Orchestration](#orchestration)
  - [Configuration & Secrets](#configuration--secrets)
- [Application Architecture](#application-architecture)
  - [Foundation: The Type System](#foundation-the-type-system)
  - [Rich Domain Models](#rich-domain-models)
  - [Immutability & Safety](#immutability--safety)
  - [Service Layer: Thin Orchestration](#service-layer-thin-orchestration)
  - [Data Flow & Traceability](#data-flow--traceability)
  - [LLM Integration](#llm-integration)
- [The Gestalt](#the-gestalt)

---

## Quick Start

**Get running in 5 minutes:**

1. **Install** → [Installation Guide](docs/install.md) (Linux, macOS, Windows)
2. **Develop** → [Development Guide](docs/development.md) (workflows, debugging, best practices)
3. **Run** → `make dev` (starts entire stack: 7 databases, API, LLM inference)

**What you get:** A complete AI-native architecture with RAG (Qdrant), GraphRAG (Neo4j), local LLM inference (Ollama), object storage (MinIO), and a production-ready FastAPI application—all orchestrated with Docker and documented thoroughly.

**Who this is for:**
- Developers learning modern architecture patterns
- Teams building AI applications that need to scale
- Anyone who wants to understand how enterprise systems really work
- Engineers tired of "hello world" examples that don't reflect reality

This isn't a toy. It's a **real architecture** you can deploy, extend, and learn from.

---

## Infrastructure Architecture

Modern applications are ecosystems, not monoliths. This stack demonstrates polyglot persistence, infrastructure as code, and container orchestration—the foundations of scalable systems.

### Getting Started

**Ready to dive in?** Start here.

The installation process is streamlined for all platforms. Docker handles consistency, Make provides simple commands, and the entire stack starts with one command. No manual database setup, no wiki of tribal knowledge, no "works on my machine" problems.

→ [**Installation Guide**](docs/install.md) - Cross-platform setup (Linux, macOS, Windows)

### The Stack

**Seven specialized databases working as one system.**

Modern AI applications need different capabilities: ACID transactions (PostgreSQL), microsecond caching (Redis), semantic search (Qdrant), knowledge graphs (Neo4j), object storage (MinIO), local LLM inference (Ollama)—all coordinated by FastAPI. Each excels at its job. Together, they create a powerful foundation.

No single database can do everything well. PostgreSQL can't match Qdrant's vector search performance. Redis can't model relationships like Neo4j. MinIO gives you S3 semantics for storing model artifacts and document corpora. This stack demonstrates **polyglot persistence**—using the right tool for each job, not forcing everything into one system.

The AI-native pattern: RAG with Qdrant (semantic search), GraphRAG with Neo4j (relationship reasoning), hybrid local/API inference with Ollama, fast state management with Redis, structured data integrity with PostgreSQL, artifact management with MinIO.

→ [**Infrastructure Systems**](docs/infra/systems.md) - What each database does, when to use it, and why it matters

### Containers & Infrastructure as Code

**Everything as version-controlled, reproducible code.**

Containers solve "works on my machine" by packaging applications with their dependencies. Infrastructure as Code (IaC) makes your entire stack reproducible—no manual setup, no configuration drift, no tribal knowledge. The Dockerfile defines how to build the application image. The docker-compose file defines what services run and how they connect.

This approach transforms infrastructure from manual toil into declarative code. Want to upgrade PostgreSQL? Change one line in a YAML file. Need to reset everything? One command wipes and rebuilds from scratch. The infrastructure becomes testable, reviewable, and disposable.

Key concepts: containers vs VMs, image layers and caching, volumes for persistence, networks for service discovery, multi-stage builds for security. All explained with real examples from this codebase.

→ [**Infrastructure as Code**](docs/infra/iac.md) - Docker, containers, images, volumes, and IaC principles

### Orchestration

**How seven databases start in perfect harmony.**

Orchestration coordinates multiple services so they start in the right order, wait for dependencies, run initialization scripts once, and self-heal when things break. When you run `make dev`, PostgreSQL starts and becomes healthy before the API tries to connect. Neo4j runs initialization scripts once, then marks itself complete. MinIO creates buckets automatically. Everything "just works."

This isn't magic—it's careful design using healthchecks, dependency declarations, and one-time setup containers. The Makefile provides the interface (simple commands). Docker Compose provides the coordination (startup order, networking). Shell scripts provide the automation (configuration generation, initialization).

The dependency graph, sentinel file pattern, state management (what persists, what doesn't), and troubleshooting common orchestration issues—all covered in depth.

→ [**Orchestration**](docs/infra/orchestration.md) - Dependencies, healthchecks, startup order, and Make/docker-compose patterns

### Configuration & Secrets

**Type-safe configuration from filesystem to code.**

Configuration is a four-layer system: template (source of truth), secrets (filesystem storage), generation (script automation), and validation (type-safe consumption). API keys live in files, never committed to git. Database passwords are auto-generated and cached. Connection strings are derived from components. Everything flows into a validated Pydantic Settings class that gives you type safety and IDE autocomplete.

This approach eliminates configuration hell: no hardcoded secrets, no manual .env files that drift, no "did I update all three places?" problems. Change a password once, and all connection strings update automatically. Add a new API key by dropping a file in a directory—the system auto-detects and loads it.

The philosophy: secrets in files (not templates), generation over hand-editing, derivation over duplication, validation over runtime failures.

→ [**Configuration & Secrets**](docs/infra/configuration.md) - Template system, secrets management, generation pipeline, and type-safe consumption

---

## Application Architecture

The application layer demonstrates domain-driven design with modern Python. Types encode business rules. Domain models own their behavior. Services are thin orchestrators. Everything is immutable, traceable, and type-safe.

### Foundation: The Type System

**Types that teach the domain.**

Most codebases use primitive types everywhere—strings, ints, dicts—that tell you nothing about business meaning. This architecture uses smart enums for constrained choices, RootModel wrappers for semantic meaning, computed properties for derived values, and composition for complex structures.

A `MessageId` isn't a string—it's a type that guarantees validity. An `AIModelVendor` isn't a string—it's an enum that prevents typos. A `ConversationHistory` isn't a list—it's a frozen model with methods that understand conversation semantics. Types become self-documenting, invalid states become impossible, and the domain logic lives with the data.

The shift from primitive obsession to semantic types, from runtime validation to compile-time safety, from documentation that goes stale to types that can't lie.

→ [**Type System**](docs/app/type-system.md) - Smart enums, RootModel wrappers, computed properties, and composition patterns

### Rich Domain Models

**Business logic lives in domain models, not services.**

Domain models are the heart of the application. They're not anemic data bags passed to service classes—they're rich objects that encapsulate both data and behavior. The `Conversation` aggregate manages history, routes to models, executes LLMs, and handles persistence. It doesn't delegate this to services; it owns it.

Aggregate roots orchestrate clusters of related models. Factory methods provide clear construction semantics. Domain-owned persistence means models define their own save/load strategy, taking infrastructure clients as dependencies. This inversion keeps the domain pure while allowing practical persistence.

The philosophy: behavior near data, aggregates over scattered entities, factories over constructors, domain-owned persistence over repository patterns.

→ [**Domain Models**](docs/app/domain-models.md) - Aggregates, factories, domain-owned persistence, and rich behavior

### Immutability & Safety

**Frozen models eliminate entire classes of bugs.**

Every domain model uses `frozen=True`. Operations don't mutate—they return new instances. This eliminates race conditions, hidden state changes, and "who modified this?" debugging sessions. Collections use tuples (immutable), not lists. State transitions are explicit transformations, not mutations.

The practical benefits are immediate: concurrent systems become safe (no shared mutable state), operations become traceable (compare before/after), testing becomes simple (pure functions), and debugging becomes sane (data doesn't change underneath you).

This isn't academic purity—it's engineering pragmatism that makes production systems robust and maintainable.

→ [**Immutability**](docs/app/immutability.md) - Frozen models, functional updates, safety guarantees, and practical patterns

### Service Layer: Thin Orchestration

**Services orchestrate; domain models implement.**

Services have exactly four responsibilities: parse input from HTTP, load domain aggregates, call domain methods, persist results. That's it. Zero business logic. No conditionals based on domain state. No calculations. No validations.

This creates clear boundaries: the API layer handles HTTP concerns, domain models handle business logic, services connect them with minimal translation. A service retrieves a `Conversation`, calls `send_message()`, persists the result, returns an API response. The `send_message` method contains all the routing, tool selection, and LLM execution logic.

The anti-patterns to avoid, the four-responsibility rule, dependency injection patterns, and why thin services lead to testable, maintainable systems.

→ [**Service Patterns**](docs/app/service-patterns.md) - Thin orchestration, clear boundaries, and anti-patterns

### Data Flow & Traceability

**Every transformation is explicit and typed.**

The data flow is a pipeline: HTTP JSON → Pydantic contract → Domain model → Domain operation → New domain state → API response. Each arrow is explicit. Each transformation has a type signature. Each step is independently testable.

This creates natural audit trails. You can inspect state at any point. You can compare before/after. You can trace exactly what happened and why. No hidden mutations, no unclear data lineage, no "what changed this?" debugging.

End-to-end traceability from HTTP request to database write, showing every transformation with types and boundaries clearly marked.

→ [**Data Flow**](docs/app/data-flow.md) - Explicit transformations, traceability, and audit trails

### LLM Integration

**Type-safe, production-ready AI patterns.**

The LLM integration demonstrates modern patterns: streaming responses, structured outputs validated with Pydantic, tool definitions as async functions, model pooling for performance, and two-phase classification for cost optimization.

The two-phase pattern: a fast model classifies which strong model to use and which tools to load, then the execution happens with optimal model and minimal tool context. This optimizes both cost (cheap classification) and quality (right model, focused tools). Model pooling caches expensive-to-create clients and reuses them across thousands of requests.

The integration uses Pydantic AI's types directly—no unnecessary wrappers, no impedance mismatch, just clean integration between type systems.

→ [**LLM Integration**](docs/app/llm-integration.md) - Structured outputs, tool definitions, and Pydantic AI patterns  
→ [**Conversation System**](docs/app/conversation-system.md) - Two-phase classification, model pooling, and tool routing

---

## The Gestalt

**Infrastructure and application—unified by the same principles:**

**Infrastructure Layer:**
- **Every service is declarative** → Infrastructure as reviewable code
- **Every database is specialized** → Right tool for each job (polyglot persistence)
- **Every startup is orchestrated** → Services coordinate automatically
- **Every secret is derived** → Configuration flows from source of truth
- **Every environment is disposable** → Rebuild from scratch with one command

**Application Layer:**
- **Every type teaches** → Self-documenting domain models
- **Every transformation is explicit** → Traceable data flow
- **Every state change returns new data** → Immutability eliminates bugs
- **Every business rule lives with its data** → Cohesive domain logic
- **Every boundary is type-safe** → Correctness by construction

**The Pattern:** From infrastructure to domain models, this architecture eliminates implicit behavior. Docker Compose declares what runs. Domain models declare what's valid. Configuration generation declares how secrets flow. Type signatures declare what transforms.

Nothing is magic. Nothing is hidden. Everything teaches.

**The Result:**

At the infrastructure level:
- Services start in perfect order without manual intervention
- Configuration changes propagate automatically
- The entire stack rebuilds from a clean slate in minutes
- Every dependency is explicit in version-controlled files

At the application level:
- Invalid states cannot be constructed
- Business rules cannot be violated
- Every operation leaves an audit trail
- LLMs can understand and work with your models

**The Virtuous Cycle:**

**Explicit infrastructure** → Fast, confident iteration  
**Rich domain types** → Clear semantics  
**Clear semantics** → AI comprehension  
**AI comprehension** → Better tooling  
**Better tooling** → More time for architecture  
**More time** → Richer systems

This is modern full-stack architecture: where infrastructure is code, types are documentation, and correctness emerges from design rather than testing. Every layer—from Docker Compose to domain models—follows the same principle: make the implicit explicit, make the hidden visible, make the system teach itself.
