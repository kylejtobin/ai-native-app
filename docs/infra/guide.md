# Infrastructure Documentation Guide

**How to navigate this section effectively**

The infrastructure docs are organized by **operational concern** (what each part does), not by learning path. This matches how the system actually works and makes them excellent reference material. But real tasks often span multiple concerns.

This guide helps you traverse the documentation based on **what you're trying to do**.

---

## The Four Core Documents

Each document covers one architectural concern:

| Document | What It Covers | When To Read It |
|----------|----------------|-----------------|
| **[systems.md](systems.md)** | What exists and why it's specialized | Adding/understanding databases |
| **[iac.md](iac.md)** | How declarative infrastructure works | Understanding Docker/containers |
| **[orchestration.md](orchestration.md)** | How services coordinate automatically | Debugging startup/dependencies |
| **[configuration.md](configuration.md)** | How secrets flow and derive | Managing API keys/passwords |

---

## Common Scenarios: Where to Start

### "I want to add a new database"

**Learning path:**
1. Read [systems.md](systems.md) → Understand polyglot persistence philosophy
   - See "When to Add vs Reuse" decision framework
   - Understand why specialized beats general-purpose
2. Read [iac.md](iac.md) → Understand container patterns
   - See "The Anatomy of a Service Definition"
   - Understand volumes for persistence
3. Read [orchestration.md](orchestration.md) → Understand dependencies
   - See "Healthchecks and Readiness"
   - Understand startup coordination
4. Read [configuration.md](configuration.md) → Understand secrets
   - See how to add connection strings
   - Understand derivation over duplication

**Then:** Look at `docker-compose.yml` for complete examples of each pattern.

### "Something won't start / Services timing out"

**Debugging path:**
1. Start with [orchestration.md](orchestration.md)
   - Check "Common Orchestration Issues"
   - Understand healthcheck patterns
2. Check [iac.md](iac.md)
   - See "Healthcheck Patterns" section
   - Understand service readiness vs running
3. Check [configuration.md](configuration.md)
   - Verify connection strings are correct
   - Regenerate with `make config`

**Key commands:**
```bash
docker compose ps       # Check actual status
docker compose logs     # See what's failing
make config && make restart  # Regenerate config and restart
```

### "I need to add a new API key / Change configuration"

**Quick Start:** See [API Keys Setup](../../secrets/README.md) for step-by-step instructions on obtaining and adding Anthropic, OpenAI, and Tavily keys.

**Configuration path:**
1. Read [configuration.md](configuration.md)
   - See "The Four-Layer System"
   - Understand why we don't edit .env directly
2. Follow the workflow:
   ```bash
   # Add your key
   echo "your-key" > secrets/api/provider-name
   
   # Regenerate config (reads all secrets)
   make config
   
   # Restart to pick up changes
   make restart
   ```

### "I want to understand how the whole thing works"

**Complete learning path:**
1. Start with [systems.md](systems.md) → What components exist
2. Then [iac.md](iac.md) → How they're defined as code
3. Then [orchestration.md](orchestration.md) → How they coordinate
4. Finally [configuration.md](configuration.md) → How they're configured

This mirrors the actual execution order: define → orchestrate → configure → run.

### "I'm deploying to production"

**Production readiness path:**
1. [systems.md](systems.md) → Understand production topologies
   - See "Production Considerations" in each section
   - Understand replication, failover, scaling
2. [iac.md](iac.md) → Understand persistence and volumes
   - See "Volumes and Data Persistence"
   - Understand backup strategies
3. [orchestration.md](orchestration.md) → Understand dependency management
   - See "Production Orchestration"
   - Understand health monitoring
4. [configuration.md](configuration.md) → Understand secrets in production
   - See "Production Secret Management"
   - Understand secrets stores (Vault, AWS Secrets Manager)

**Key principle:** Everything in this stack is production-ready *patterns*. The docker-compose is for dev convenience, but the patterns (healthchecks, dependencies, derived config) apply everywhere.

### "I'm debugging a specific service"

**Quick reference by service:**

| Service | Primary Doc | Key Sections | Common Issues |
|---------|-------------|--------------|---------------|
| PostgreSQL | [systems.md](systems.md) | "PostgreSQL - Relational Foundation" | Connection refused → check healthcheck |
| Redis | [systems.md](systems.md) | "Redis - The Nervous System" | Auth failed → check password in .env |
| Neo4j | [systems.md](systems.md), [orchestration.md](orchestration.md) | "Neo4j - Knowledge Graph", "One-Time Initialization" | Init fails → check sentinel pattern |
| Qdrant | [systems.md](systems.md) | "Qdrant - Vector Search" | Port conflict → check docker compose ps |
| MinIO | [systems.md](systems.md), [orchestration.md](orchestration.md) | "MinIO - Object Storage", "Setup Containers" | Buckets missing → check setup-minio.sh |
| Ollama | [systems.md](systems.md) | "Ollama - Local LLM Inference" | Model missing → run `make ollama-setup` |
| API | [orchestration.md](orchestration.md) | "Dependency Graph" | Won't start → check all depends_on |

---

## Cross-Cutting Concepts

Some concepts appear in multiple documents because they're fundamental:

### Healthchecks
- **Defined in:** [iac.md](iac.md) "Healthcheck Patterns"
- **Used in:** [orchestration.md](orchestration.md) "Service Dependencies"
- **Purpose:** Know when services are truly ready, not just running

### Volumes & Persistence
- **Defined in:** [iac.md](iac.md) "Volumes and Data Persistence"
- **Used in:** [systems.md](systems.md) throughout
- **Purpose:** What survives restarts vs what's ephemeral

### Secrets & Derivation
- **Defined in:** [configuration.md](configuration.md) "Four-Layer System"
- **Used in:** All services in docker-compose.yml
- **Purpose:** Single source of truth, nothing duplicated

### Dependency Coordination
- **Defined in:** [orchestration.md](orchestration.md) "The Startup Sequence"
- **Implemented via:** healthchecks ([iac.md](iac.md)) + depends_on (docker-compose)
- **Purpose:** Services start in correct order automatically

---

## Philosophy Connection

Every pattern in these docs traces back to principles in [philosophy.md](../philosophy.md):

| Infrastructure Pattern | Philosophy Principle |
|------------------------|----------------------|
| Declarative service definitions | "Every service is declarative" |
| Specialized databases | "Every database is specialized" |
| Healthchecks + depends_on | "Every startup is orchestrated" |
| Configuration generation | "Every secret is derived" |
| `make clean && make dev` | "Every environment is disposable" |

When you're making decisions about infrastructure, reference [Philosophy](../philosophy.md) to understand the **why** behind the patterns.

---

## Quick Command Reference

The most common operations:

```bash
# Start everything
make dev

# Stop everything (keep data)
make down

# Nuclear option (wipe all data)
make clean

# Regenerate configuration
make config

# View all logs
make logs

# View specific service logs
docker compose logs -f postgres

# Check service status
docker compose ps

# Restart a specific service
docker compose restart api

# Shell into a container
docker compose exec api bash

# Database shells
make shell-db  # PostgreSQL
docker compose exec redis redis-cli
docker compose exec neo4j cypher-shell
```

See the [Makefile](../../Makefile) for all available commands with detailed comments.

---

## When These Docs Don't Apply

This infrastructure setup is optimized for:
- **Development** on local machines
- **Learning** infrastructure patterns
- **Prototyping** AI applications

It is NOT optimized for:
- Massive scale (billions of requests/day)
- Multi-region deployments
- High-availability requirements
- Compliance-heavy environments (HIPAA, PCI-DSS)

**For production at scale**, you'd typically:
- Use managed services (RDS, ElastiCache, Aura)
- Add orchestration (Kubernetes, ECS)
- Implement service mesh (Istio, Linkerd)
- Add observability (Prometheus, Grafana, traces)

But the **patterns remain the same**:
- Healthcecks still coordinate startup
- Secrets still derive from source
- Services still specialize
- Infrastructure still declarative

The principles scale. The docker-compose doesn't (by design).

---

## Next Steps

After understanding the infrastructure:

1. **Explore the API** - http://localhost:8000/docs
2. **Read application docs** - [docs/app/](../app/) for domain patterns
3. **Read philosophy** - [docs/philosophy.md](../philosophy.md) for the "why"
4. **Read actual code** - Start with [docker-compose.yml](../../docker-compose.yml)

The infrastructure exists to support the application. Once you understand how services coordinate, the interesting patterns are in the application layer: rich domain models, immutability, type safety, and LLM integration.

**Remember:** These docs are reference material. You don't need to read them linearly. Jump to the section that answers your current question, follow links to related concepts, and use this guide to navigate back when you need broader context.

