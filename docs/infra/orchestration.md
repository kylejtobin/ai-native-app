# Infrastructure Orchestration

**Orchestration is the art of coordinating many moving parts to work together as a coherent system.**

In this template, we orchestrate 7 databases, an API server, and several initialization scripts. They need to start in the right order, wait for each other to be ready, run setup scripts once, and clean up gracefully. This document explains how we achieve that.

---

## The Problem: Complexity

Modern applications aren't single processes—they're ecosystems:

- PostgreSQL needs to be running before the API tries to connect
- Neo4j needs to be healthy before we can run Cypher initialization scripts
- MinIO needs buckets created before the API tries to upload files
- Redis needs authentication configured before the API can cache data
- The API needs ALL infrastructure ready before it starts

**Without orchestration, you get:**
- Race conditions (API starts before database is ready → crash)
- Manual setup steps (developer has to remember 15 commands in order)
- Inconsistent state (some services running, some not)
- No clear way to start, stop, or reset the stack

**With orchestration, you get:**
- One command to start everything: `make dev`
- Services start in dependency order automatically
- Setup scripts run once, then never again
- Clean state management (what persists, what doesn't)

---

## The Orchestration Stack

We use two complementary tools:

### 1. **Make** - The User Interface

**What it is:** A 1970s build tool that's perfect for defining common workflows.

**Why we use it:**
- **Single command interface** - `make dev`, `make clean`, `make logs`
- **Composable** - `rebuild: clean dev` chains commands
- **Self-documenting** - `make help` shows all available commands
- **Shell-native** - Can call any script or Docker command
- **Universal** - Works on Linux, Mac, Windows (with WSL)

**What it does for us:**
```bash
make dev        # Generate config → Start all services → Show status
make down       # Graceful shutdown (keep data)
make clean      # Nuclear option (wipe everything)
make logs       # Tail all container logs
```

See [`Makefile`](../../Makefile) for the implementation (well-commented!)

### 2. **docker-compose** - The Service Coordinator

**What it is:** A tool for defining and running multi-container Docker applications.

**Why we use it:**
- **Declarative** - Define WHAT you want, not HOW to achieve it
- **Dependency management** - Services wait for each other automatically
- **Networking** - All services can talk to each other by name
- **Volume management** - Persistent storage that survives restarts
- **Health checking** - Know when services are actually ready (not just running)

**What it does for us:**
```yaml
services:
  postgres:
    healthcheck: pg_isready ...  # PostgreSQL is READY
    
  api:
    depends_on:
      postgres:
        condition: service_healthy  # Wait for PostgreSQL to be READY
```

See [`docker-compose.yml`](../../docker-compose.yml) for the full stack definition.

---

## How Orchestration Works: The Startup Sequence

When you run `make dev`, here's what happens:

### Phase 1: Configuration Generation

```bash
# Makefile calls this first
infra/generate-config.sh
```

**What it does:**
1. Reads `secrets/env-template.txt` (the source of truth)
2. Loads API keys from `secrets/api/*` files
3. Generates random passwords for databases (cached in `secrets/infra/`)
4. Computes connection strings from components
5. Writes `.env` file (used by docker-compose)

**Why first?**
- Docker Compose needs environment variables BEFORE starting containers
- Secrets must exist before services try to use them
- Idempotent: Safe to run multiple times (cached secrets don't change)

See [`infra/generate-config.sh`](../../infra/generate-config.sh) for the implementation.

### Phase 2: Core Services Start

```yaml
# docker-compose.yml
services:
  postgres:    # No dependencies - starts immediately
  redis:       # No dependencies - starts immediately
  neo4j:       # No dependencies - starts immediately
  minio:       # No dependencies - starts immediately
  qdrant:      # No dependencies - starts immediately
  ollama:      # No dependencies - starts immediately
```

**Parallel startup:** All core services start simultaneously (faster!)

**Healthchecks run:** Docker monitors each service until it's READY:
```yaml
postgres:
  healthcheck:
    test: pg_isready -U appuser -d appdb
    interval: 10s
    retries: 5
```

**Status progression:**
- `starting` → Service container is launching
- `healthy` → Healthcheck passed, service is ready
- `unhealthy` → Healthcheck failed (container might still be running!)

### Phase 3: One-Time Setup Containers

Once core services are healthy, setup containers run:

```yaml
neo4j_setup:
  depends_on:
    neo4j:
      condition: service_healthy  # Waits for Neo4j to be ready
  entrypoint: ["/bin/bash", "/setup-neo4j.sh"]
  restart: "no"  # Exits after running (not a long-running service!)
```

**Pattern: One-time setup container**

This is a powerful pattern for initialization:

1. **Wait for service to be healthy** (`depends_on` with `condition: service_healthy`)
2. **Run initialization script** (create buckets, run Cypher queries, etc.)
3. **Create sentinel file** (e.g., `/data/.initialized`) to prevent re-runs
4. **Exit cleanly** (`restart: "no"` means container disappears)

**Why this pattern?**
- Idempotent: Safe to restart (checks sentinel file)
- Explicit: Initialization is visible in logs
- Version-controlled: `init.cypher` and `init-db.sql` are in git
- Testable: Can run setup scripts standalone for debugging

See:
- [`infra/setup-neo4j.sh`](../../infra/setup-neo4j.sh) - Neo4j initialization
- [`infra/setup-minio.sh`](../../infra/setup-minio.sh) - MinIO bucket creation
- [`infra/init.cypher`](../../infra/init.cypher) - Cypher queries to run
- [`infra/init-db.sql`](../../infra/init-db.sql) - PostgreSQL extensions

### Phase 4: Application Start

Finally, the API starts:

```yaml
api:
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    neo4j_setup:
      condition: service_completed_successfully  # Setup FINISHED
    minio_setup:
      condition: service_completed_successfully  # Setup FINISHED
```

**Why last?**
- All databases must be READY (not just running)
- All initialization must be COMPLETE (buckets exist, extensions installed)
- API can start safely, knowing its dependencies are configured

**Result:**
```
✅ Services ready at http://localhost:8000
   API docs: http://localhost:8000/docs
```

---

## State Management: What Persists, What Doesn't

Understanding state is critical for orchestration. Different things have different lifecycles:

### Persistent State (Survives Restarts)

**Docker Volumes** - Managed by Docker, stored on host
```yaml
volumes:
  postgres_data:    # Tables, indexes, data
  redis_data:       # Cached values, queues
  neo4j_data:       # Graph nodes, relationships
  minio_data:       # Object storage buckets
```

**Lifecycle:**
- Created: First `docker compose up`
- Persists: Through `docker compose down` (stop containers)
- Persists: Through `docker compose restart` (restart containers)
- Persists: Through Docker image rebuilds
- **DESTROYED ONLY BY:** `docker compose down -v` or `make clean`

**Cached Secrets** - Stored in `secrets/infra/` on host
```
secrets/infra/db-password
secrets/infra/redis-password
secrets/infra/neo4j-password
```

**Lifecycle:**
- Created: First `make config` run
- Persists: Across all commands except `make clean`
- **DESTROYED ONLY BY:** `make clean` or manual `rm secrets/infra/*`

**Why cache?**
- PostgreSQL won't start if password changes (data encrypted with old password)
- Stability: Same password every `make dev` run
- Explicit reset: Must run `make clean` to regenerate

### Ephemeral State (Lost on Restart)

**Containers** - Running processes
- Created: `docker compose up`
- Destroyed: `docker compose down`
- Rebuilt: `docker compose up --build`

**Generated `.env` file**
- Created: Every `make config` run
- Destroyed: `make clean`
- Regenerated: Every `make dev` (calls `make config`)

**Why regenerate?**
- Always fresh from template (source of truth)
- Picks up new API keys from `secrets/api/`
- Rebuilds connection strings from cached secrets

---

## Common Orchestration Workflows

### Starting the Stack

```bash
make dev
```

**What happens:**
1. Runs `make config` (generates `.env`)
2. Runs `docker compose up -d` (starts all services in background)
3. Shows success message

**When to use:** Daily development, after pulling new code

---

### Stopping the Stack

```bash
make down
```

**What it does:**
- Stops all containers gracefully
- **Keeps volumes** (data persists)
- **Keeps secrets** (cached passwords stay)

**When to use:** End of work day, switching branches

---

### Restarting Services

```bash
make restart
```

**What it does:**
- `docker compose down` (stop containers)
- `docker compose up -d` (start containers)
- **Keeps volumes and data**

**When to use:**
- After changing `docker-compose.yml`
- After rebuilding Docker image
- **Rarely needed** - hot reload handles most code changes

---

### Full Reset (Nuclear Option)

```bash
make clean    # or make rebuild (clean + dev)
```

**What it does:**
- Stops and removes all containers
- **DELETES ALL VOLUMES** (all data lost!)
- Deletes `.env` file
- Deletes cached secrets (`secrets/infra/*`)

**When to use:**
- Docker state is corrupted
- Need truly fresh start
- Testing initialization scripts
- Before committing (ensure clean bootstrap works)

**⚠️ WARNING:** You will lose all local data (PostgreSQL tables, Redis cache, etc.)

---

### Viewing Logs

```bash
make logs                    # All services, live tail
docker compose logs api      # Just API logs
docker compose logs postgres # Just PostgreSQL logs
```

**When to use:**
- Debugging startup issues
- Investigating errors
- Watching initialization scripts run

---

### Debugging a Service

```bash
# Check service status
docker compose ps

# Inspect specific service
docker compose logs postgres --tail 50

# Shell into running container
docker compose exec postgres bash
docker compose exec api bash

# Check healthcheck status
docker inspect an-app-postgres-1 | jq '.[0].State.Health'
```

---

## The Sentinel File Pattern

You'll see this pattern in our setup scripts:

```bash
# Check if already initialized
if [ -f "/data/.initialized" ]; then
    echo "Already initialized"
    exit 0
fi

# Do initialization work
cypher-shell --file init.cypher

# Mark as complete
touch "/data/.initialized"
```

**Why this pattern?**

Without it:
- Restart stack → setup runs again → duplicate constraints/indexes → ERROR
- Race conditions if setup script is slow
- No way to know if initialization completed

With it:
- Idempotent: Safe to run setup container multiple times
- Fast: Checks sentinel file and exits immediately if done
- Explicit: Can inspect sentinel file to debug initialization issues
- Persistent: Sentinel lives on volume, survives restarts

**Where it's used:**
- `neo4j_setup`: `/data/.initialized`
- `minio_setup`: Buckets themselves are idempotent (`--ignore-existing`)

---

## Dependency Graph Visualization

Here's how services depend on each other:

```
Configuration Generation (make config)
         ↓
    .env created
         ↓
Core Services (parallel start)
├── postgres → [healthy] → neo4j_setup → [completed]
├── redis    → [healthy]                             ↘
├── neo4j    → [healthy] ────────────────────────────→ API
├── minio    → [healthy] → minio_setup → [completed] ↗
├── qdrant   → [started]
└── ollama   → [started]

Legend:
→ depends_on
[healthy] = healthcheck passed
[completed] = exited successfully
[started] = container running
```

**Key insights:**
- API is the "leaf node" - depends on everything
- Setup containers are "middleware" - bridge between services and API
- Core services have no dependencies - can start in parallel

---

## Troubleshooting Orchestration Issues

### "Port already allocated"

**Symptom:**
```
Bind for 0.0.0.0:5432 failed: port is already allocated
```

**Cause:** Old containers still running (from previous project name or manual docker runs)

**Fix:**
```bash
docker ps -a | grep -E "5432|6379|7687"  # Find containers using ports
docker stop <container_id>
docker rm <container_id>
```

### "Unhealthy" service

**Symptom:**
```
postgres-1  Up 30 seconds (unhealthy)
```

**Cause:** Healthcheck failing (service running but not ready)

**Fix:**
```bash
# Check healthcheck command
docker inspect an-app-postgres-1 | jq '.[0].State.Health'

# View logs to see why service isn't ready
docker compose logs postgres
```

### Setup container keeps running

**Symptom:**
```
neo4j_setup-1  Up 5 minutes
```

**Cause:** Setup script hung, waiting for something, or crashed

**Fix:**
```bash
# View logs
docker compose logs neo4j_setup

# Common issues:
# - Neo4j not actually ready (Cypher interface not up)
# - Syntax error in init.cypher
# - Credentials mismatch
```

### Services start but API crashes immediately

**Symptom:**
```
api-1  Exited (1) 2 seconds ago
```

**Cause:** Missing environment variable, database connection failed, or code error

**Fix:**
```bash
# Check API logs for error
docker compose logs api

# Common issues:
# - NEED-API-KEY in .env (missing required API key)
# - Database connection string wrong
# - Import error in Python code
```

---

## Best Practices

### 1. Always Use Make Commands

**Good:**
```bash
make dev
make down
make clean
```

**Why:**
- Ensures config is generated first
- Consistent interface for all developers
- Self-documenting (see `make help`)

### 2. Check Status Before Debugging

```bash
docker compose ps
```

**Look for:**
- `(healthy)` next to databases
- `Exited (0)` for setup containers (good!)
- `Exited (1)` for anything (bad - check logs)

### 3. Clean State Regularly

**During active development:**
```bash
make clean && make dev
```

**Why:**
- Ensures initialization scripts work
- Catches issues with fresh bootstrap
- Prevents accumulation of test data

### 4. Commit After Major Changes

After changing `docker-compose.yml`, setup scripts, or `Makefile`:
```bash
make rebuild  # Test full bootstrap
git add ...
git commit
```

**Why:**
- Ensures changes don't break fresh setup
- Catches missing files or broken dependencies
- Other developers can clone and `make dev` successfully

---

## Summary

**Orchestration = Automation + Coordination + State Management**

This template orchestrates:
- **7 databases** with different purposes
- **3 setup scripts** that run once
- **1 API service** that depends on everything
- **Configuration generation** that runs first
- **State management** that persists the right things

**Result:** One command (`make dev`) gives you a working stack. One command (`make clean`) resets everything. The complexity is hidden behind simple, composable commands.

**Next Steps:**
- See [Systems](systems.md) for what each database does
- See [IaC](iac.md) for Docker/container deep dive
- See [Secrets](secrets.md) for credential management
- See [Configuration](configuration.md) for environment variable structure

