# Infrastructure as Code (IaC)

**Infrastructure as Code means defining your servers, networks, and databases as version-controlled text files.**

This template uses Docker and docker-compose to define a complete development environment—polyglot persistence (PostgreSQL, Redis, Neo4j, Qdrant, MinIO), local LLM inference (Ollama), and your API—all declared in two files. No manual setup, no "works on my machine," no wiki documentation that goes stale. Just code.

> **Principle: Every Service is Declarative**
>
> Infrastructure as Code isn't just about version control—it's about declaring WHAT should exist rather than scripting HOW to create it. The docker-compose.yml doesn't say "run this command, then that command." It says "this is the complete system state." The orchestration engine figures out how to achieve it.
>
> When you declare what should be true, you eliminate an entire class of errors that come from executing steps in the wrong order, forgetting steps, or executing them twice.
>
> See: [philosophy.md](../philosophy.md) "Every Service is Declarative"

---

## The Problem: Manual Infrastructure

Let's rewind to how infrastructure used to work (and sadly, still works in many places):

### The "Works on My Machine" Problem

**Developer A's setup:**
```bash
# Install PostgreSQL manually
sudo apt install postgresql-14
sudo systemctl start postgresql

# Create database manually
psql -U postgres
CREATE DATABASE myapp;
CREATE USER appuser WITH PASSWORD 'password123';

# Install Redis manually
sudo apt install redis-server
sudo systemctl start redis

# Edit redis.conf manually to add password
sudo vim /etc/redis/redis.conf
# ... find the right line, uncomment it, set password ...
sudo systemctl restart redis

# Try to run app
python app.py
# Error: "Connection refused to Neo4j"
# Oh right, need to install Neo4j too...
```

**Developer B joins the team:**
```bash
# "Hey, how do I set up the dev environment?"
# Developer A: "Oh, you need PostgreSQL 14, Redis with auth, Neo4j..."
# Developer B: "What version of Neo4j?"
# Developer A: "Uh... 5? Maybe? Let me check..."
# Developer B: *spends 3 hours setting up, still doesn't work*
```

**Production deployment:**
```bash
# SSH into production server
ssh prod-server

# Manually install everything
sudo apt install postgresql-15  # Wait, different version than dev!
# ... 2 hours of setup ...

# Something breaks in production
# Dev: "Works on my machine though?" 🤷
```

### The Problems

1. **Inconsistent environments** - Dev has PostgreSQL 14, prod has 15, staging has 13
2. **Tribal knowledge** - Setup instructions in someone's head or outdated wiki
3. **Manual toil** - Every new developer spends days setting up
4. **Configuration drift** - Services get tweaked manually, no record of changes
5. **Impossible to reproduce** - "It worked yesterday, what changed?"
6. **Resource conflicts** - Port 5432 already in use, now what?
7. **No rollback** - Upgraded a service, broke everything, can't go back

---

## The Solution: Infrastructure as Code

**Define WHAT you want, not HOW to set it up.**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:17-alpine  # Exact version, always
    environment:
      POSTGRES_DB: appdb
      POSTGRES_PASSWORD: ${PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

**Result:**
```bash
make dev  # Everyone gets identical PostgreSQL 17, configured identically
```

### The Benefits

1. **Reproducible** - Same environment every time, on every machine
2. **Version controlled** - Infrastructure changes tracked in git
3. **Self-documenting** - The code IS the documentation
4. **Fast onboarding** - New developer: `make dev` → working environment in 2 minutes
5. **Isolated** - Services in containers, no port conflicts with host
6. **Disposable** - Broke something? `make clean && make dev` → fresh start
7. **Testable** - CI/CD can spin up identical environment for testing

---

## Containers Explained

**A container is a lightweight, isolated environment that packages your application with all its dependencies.**

Think of it like a shipping container:
- Standardized (works on ship, truck, train—works on laptop, server, cloud)
- Isolated (contents don't affect other containers)
- Portable (move it anywhere)
- Disposable (create new one if damaged)

### Containers vs. Virtual Machines

**Virtual Machine (Old Way):**
```
┌─────────────────────────────────────┐
│         Your Application            │
├─────────────────────────────────────┤
│         Full OS (Ubuntu)            │  ← Entire OS (GB)
├─────────────────────────────────────┤
│         Hypervisor (VMware)         │
├─────────────────────────────────────┤
│         Host OS (Windows/Mac)       │
└─────────────────────────────────────┘
```

**Heavy:** Each VM includes full OS (gigabytes)
**Slow:** Minutes to start
**Resource-intensive:** Each VM needs allocated RAM/CPU

**Container (Modern Way):**
```
┌─────────────────────────────────────┐
│      Your Application               │
├─────────────────────────────────────┤
│      App Dependencies Only          │  ← Just what you need (MB)
├─────────────────────────────────────┤
│      Docker Engine                  │
├─────────────────────────────────────┤
│      Host OS (Linux kernel)         │
└─────────────────────────────────────┘
```

**Lightweight:** Shares host kernel (megabytes, not gigabytes)
**Fast:** Starts in seconds
**Efficient:** Runs many containers on one machine

### How Containers Work

**Key concept: Namespaces & cgroups (Linux kernel features)**

**Namespaces** = Isolation
- **Process namespace:** Container sees only its own processes
- **Network namespace:** Container has its own network stack
- **Mount namespace:** Container has its own filesystem
- **User namespace:** Container users isolated from host

**cgroups** = Resource limits
- CPU: "This container can use max 50% CPU"
- Memory: "This container can use max 512MB RAM"
- I/O: "This container can write max 10MB/s to disk"

**Result:** Feels like a separate machine, but shares kernel with host

### Container Lifecycle

```bash
# 1. IMAGE: Template (blueprint for a container)
#    - Immutable
#    - Versioned (postgres:17-alpine)
#    - Shareable (Docker Hub, registries)

# 2. CONTAINER: Running instance of an image
docker run postgres:17-alpine
#    - Mutable (can write files, change state)
#    - Ephemeral (destroyed when stopped, unless volumes used)
#    - Isolated (own filesystem, network, processes)

# 3. STOPPED CONTAINER: Container exists but not running
docker stop <container>
#    - State preserved (can restart)
#    - No CPU/memory used
#    - Can be removed

# 4. REMOVED CONTAINER: Gone
docker rm <container>
#    - All changes lost (unless volumes used)
```

---

## Docker Images & Layers

**An image is a stack of read-only layers, each representing a filesystem change.**

### How Images Work

```dockerfile
FROM python:3.13-slim        # Layer 1: Base Python image
RUN apt-get update           # Layer 2: Update package lists
RUN apt-get install gcc      # Layer 3: Install compiler
COPY requirements.txt .      # Layer 4: Add requirements file
RUN pip install -r ...       # Layer 5: Install Python packages
COPY src/ ./src/             # Layer 6: Add application code
```

**Each instruction = New layer**

**Layer visualization:**
```
┌────────────────────────────┐
│  Layer 6: App code         │  ← Changes most often
├────────────────────────────┤
│  Layer 5: Python packages  │
├────────────────────────────┤
│  Layer 4: requirements.txt │
├────────────────────────────┤
│  Layer 3: GCC installed    │
├────────────────────────────┤
│  Layer 2: Apt updated      │
├────────────────────────────┤
│  Layer 1: Python base      │  ← Changes rarely
└────────────────────────────┘
```

### Why Layers Matter: Caching

**First build:**
```bash
docker build .
# Layer 1: Download (2 minutes)
# Layer 2: Apt update (30 seconds)
# Layer 3: Install gcc (1 minute)
# Layer 4: Copy requirements (instant)
# Layer 5: Pip install (3 minutes)
# Layer 6: Copy code (instant)
# Total: ~7 minutes
```

**Rebuild after code change:**
```bash
# Edit src/app.py
docker build .
# Layer 1-5: CACHED ✅ (instant!)
# Layer 6: Copy code (instant)
# Total: ~1 second
```

**Key insight:** Order matters!
- Put stable layers first (base image, system packages)
- Put volatile layers last (application code)
- This maximizes cache hits on rebuilds

### Image Naming & Tags

```
registry/repository:tag
   ↓         ↓        ↓
docker.io/postgres:17-alpine

registry: docker.io (Docker Hub, default)
repository: postgres (the image name)
tag: 17-alpine (version/variant)
```

**Tag best practices:**
- ✅ `postgres:17-alpine` - Specific version
- ❌ `postgres:latest` - Ambiguous, changes over time
- ✅ `myapp:v1.2.3` - Semantic versioning
- ❌ `myapp:prod` - Environment in tag (use same image everywhere!)

---

## Dockerfile Deep Dive

**A Dockerfile defines how to build an image.**

See our [`Dockerfile`](../../Dockerfile) for a production example with extensive comments. Let's break down key patterns:

### Multi-Stage Builds

```dockerfile
FROM python:3.13-slim AS base
# Install build dependencies
RUN apt-get install gcc

FROM base AS prod
# Only production dependencies
# Result: Smaller final image (no build tools)
```

**Why:** Build tools needed to compile, but not needed to run
- **base stage:** gcc, make, headers (for building)
- **prod stage:** Only runtime dependencies
- Final image doesn't include build tools → Smaller & more secure

### Build Context & .dockerignore

```dockerfile
COPY . /app  # ⚠️ Copies EVERYTHING in current directory
```

**Problem:** Copies `.git/`, `node_modules/`, test data, etc.

**Solution:** `.dockerignore`
```
.git
node_modules
*.log
.env
```

**Result:** Only relevant files copied → Faster builds, smaller images

### Cache Mounts (BuildKit)

```dockerfile
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
```

**What it does:** Shares pip cache across builds
- First build: Downloads packages, caches them
- Subsequent builds: Reuses cached packages
- Result: Faster builds, less network usage

### Bind Mounts (Build-Time Files)

```dockerfile
RUN --mount=type=bind,source=requirements.txt,target=requirements.txt \
    pip install -r requirements.txt
```

**What it does:** Temporarily mounts file during RUN
- File available during command execution
- Not copied into image layer
- Result: Smaller images, better caching

### Security: Non-Root User

```dockerfile
# Bad: Running as root
USER root
CMD ["python", "app.py"]  # 💀 If compromised, attacker is root!

# Good: Running as non-root
RUN adduser appuser
USER appuser
CMD ["python", "app.py"]  # ✅ If compromised, attacker is limited
```

**Why:** Defense in depth
- Container escape vulnerabilities exist
- Non-root user limits damage
- Required by many container platforms (Kubernetes)

### Our Dockerfile Patterns

See [`Dockerfile`](../../Dockerfile) for examples of:
1. **Multi-stage builds** (base → prod)
2. **Layer optimization** (stable layers first)
3. **Cache mounts** (uv cache, apt cache)
4. **Bind mounts** (build-time files)
5. **Non-root user** (uvuser for security)
6. **Editable install** (hot reload for development)

---

## Container Networking

**Containers need to talk to each other and the outside world.**

### Docker Networks

```bash
# Automatic network creation
docker-compose up
# Creates network: an-app_default

# All services on same network can talk by name
```

**Network types:**
- **bridge** (default): Isolated network for containers
- **host**: Use host's network directly (no isolation)
- **none**: No networking

### Service Discovery (DNS)

**Magic:** Containers can reach each other by service name

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:17-alpine
    # Accessible at: postgres:5432
    
  api:
    image: myapi
    # Can connect to: postgres:5432
```

**In application code:**
```python
# ✅ Good: Use service name
DATABASE_URL = "postgresql://postgres:5432/db"

# ❌ Bad: Use localhost (won't work in container!)
DATABASE_URL = "postgresql://localhost:5432/db"
```

**Why it works:**
- Docker runs DNS server for each network
- Service name → IP address mapping
- Automatic updates when containers restart (new IP? DNS updates)

### Port Mapping

**Problem:** Container port 5432 (PostgreSQL) needs to be accessible from host

**Solution: Port mapping**
```yaml
postgres:
  ports:
    - "5432:5432"  # host:container
```

**Format:** `HOST_PORT:CONTAINER_PORT`
```yaml
ports:
  - "8080:8000"  # Host port 8080 → Container port 8000
  - "5433:5432"  # Host port 5433 → Container port 5432 (avoid conflict)
```

**When to use:**
- External access (GUI tools, local testing)
- Development (IDE connecting to database)

**When NOT to use:**
- Container-to-container (use service names!)
- Production (use reverse proxy/ingress)

### Network Isolation

**Different networks = Can't talk to each other**

```yaml
# docker-compose.yml
networks:
  frontend:  # Web tier
  backend:   # Database tier

services:
  web:
    networks:
      - frontend
      - backend  # Can talk to both
  
  db:
    networks:
      - backend  # Isolated from direct internet access
```

**Security:** Multi-tier architecture
- Public-facing services on frontend network
- Databases on backend network only
- Web tier bridges both (controlled access point)

---

## Volumes & Persistence

**Problem:** Containers are ephemeral—stop container, lose data!

**Solution:** Volumes persist data outside container lifecycle

### Volume Types

#### 1. Named Volumes (Recommended)

```yaml
services:
  postgres:
    volumes:
      - postgres_data:/var/lib/postgresql/data  # Named volume

volumes:
  postgres_data:  # Declare it
```

**Managed by Docker:**
- Stored in Docker's data directory
- Survive container removal
- Can be backed up, migrated
- Best for production

#### 2. Bind Mounts (Development)

```yaml
services:
  api:
    volumes:
      - ./src:/app/src  # Host directory mounted into container
```

**Direct host mapping:**
- Edit file on host → Change reflected in container instantly
- Perfect for development (hot reload!)
- Not portable (path depends on host)

#### 3. tmpfs Mounts (Temporary)

```yaml
services:
  cache:
    tmpfs:
      - /tmp  # In-memory filesystem
```

**RAM-based:**
- Very fast
- Cleared on container stop
- Good for temporary files, caches

### Volume Lifecycle

```bash
# Create container with volume
docker run -v mydata:/data postgres

# Container writes data
# Data saved to volume: mydata

# Stop and remove container
docker stop <container>
docker rm <container>
# Container GONE, but volume persists ✅

# Start new container with same volume
docker run -v mydata:/data postgres
# Data still there! ✅

# Remove volume (explicit action required)
docker volume rm mydata
# NOW data is gone
```

**Key insight:** Volumes outlive containers by design

### Our Volume Strategy

See [`docker-compose.yml`](../../docker-compose.yml) for:

```yaml
volumes:
  postgres_data:    # Relational data, tables, indexes
  redis_data:       # Cache, queues, conversation history
  neo4j_data:       # Graph nodes, relationships
  qdrant_storage:   # Vector embeddings, indexes
  minio_data:       # Object storage buckets
```

**Pattern:**
- Databases use named volumes (data persists)
- Application uses bind mounts (code hot reload)
- Logs/temp use tmpfs (fast, ephemeral)

---

## docker-compose Deep Dive

**docker-compose orchestrates multiple containers as a cohesive system.**

See our [`docker-compose.yml`](../../docker-compose.yml) for a complete example with extensive comments. Let's break down key concepts:

### Service Definition

```yaml
services:
  postgres:                          # Service name (used for DNS)
    image: postgres:17-alpine        # What to run
    restart: unless-stopped          # Restart policy
    environment:                     # Environment variables
      POSTGRES_DB: appdb
    volumes:                         # Persistent storage
      - postgres_data:/var/lib/postgresql/data
    ports:                           # Port mapping
      - "5432:5432"
    healthcheck:                     # Readiness check
      test: pg_isready -U appuser
    depends_on:                      # Start order
      redis:
        condition: service_healthy
```

### Dependencies & Startup Order

**Problem:** API starts before database → crash

**Solution:** `depends_on` with healthchecks

```yaml
postgres:
  healthcheck:
    test: pg_isready -U appuser -d appdb
    interval: 10s    # Check every 10 seconds
    timeout: 5s      # Give up after 5 seconds
    retries: 5       # Try 5 times

api:
  depends_on:
    postgres:
      condition: service_healthy  # Wait for healthcheck to pass
```

**Startup sequence:**
1. postgres starts
2. Docker runs healthcheck every 10s
3. Once pg_isready succeeds → postgres is "healthy"
4. api starts (dependency satisfied)

### Environment Variable Interpolation

```yaml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}  # From .env file
```

**Sources:**
1. `.env` file (generated by `make config`)
2. `env_file:` directive
3. Host environment variables
4. Shell variables (`$DATABASE_PASSWORD`)

**Precedence:** Later sources override earlier ones

### Networking (Automatic)

```yaml
# No explicit network definition needed!
services:
  postgres:
    # Automatically added to: an-app_default network
  
  api:
    # Automatically added to: an-app_default network
    # Can connect to: postgres:5432
```

**Custom networks (optional):**
```yaml
networks:
  frontend:
  backend:

services:
  web:
    networks: [frontend, backend]
  db:
    networks: [backend]
```

### Resource Limits

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'       # Max 2 CPUs
          memory: 2G        # Max 2GB RAM
        reservations:
          cpus: '0.5'       # Guaranteed 0.5 CPU
          memory: 512M      # Guaranteed 512MB
```

**Why:**
- Prevent one service from hogging resources
- Ensure critical services get resources
- Better resource utilization

### Restart Policies

```yaml
restart: "no"                 # Never restart
restart: always               # Always restart (even after reboot)
restart: unless-stopped       # Restart unless explicitly stopped
restart: on-failure           # Restart only if exit code != 0
```

**Our choices:**
- `unless-stopped`: Long-running services (databases, API)
- `"no"`: One-time setup containers (neo4j_setup, minio_setup)

---

## Infrastructure as Code: Philosophy

### Version Control = Time Machine

```bash
# Git log shows infrastructure changes
git log docker-compose.yml

commit a1b2c3d
  Added Redis for caching

commit d4e5f6g
  Upgraded PostgreSQL 14 → 17

commit g7h8i9j
  Added Neo4j for graph relationships
```

**Benefits:**
- **History:** See what changed, when, why
- **Rollback:** `git revert` to undo infrastructure changes
- **Review:** Pull requests for infrastructure changes
- **Blame:** Who added this weird configuration? (git blame)

### Declarative > Imperative

**Imperative (Old way):**
```bash
# Manual steps
ssh server
apt install postgresql
systemctl start postgresql
createdb myapp
# ... 50 more steps ...
```

**Declarative (IaC):**
```yaml
# Desired state
services:
  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: myapp
```

**Result:**
```bash
docker-compose up  # Docker figures out HOW to achieve WHAT you declared
```

**Benefits:**
- **Idempotent:** Run 1 time or 100 times, same result
- **Self-healing:** Container crashes? Docker restarts it automatically
- **Simple:** Describe goal, not steps

### Immutable Infrastructure

**Problem (Mutable):**
```bash
# Server A
apt install postgres  # Version 14.1

# 6 months later... manual upgrade
apt upgrade postgres  # Version 14.8

# Now have: Modified, drifted infrastructure
# Hard to reproduce, unknown state
```

**Solution (Immutable):**
```yaml
# docker-compose.yml
postgres:
  image: postgres:14.1  # Explicit version
```

```bash
# Upgrade: Change image tag, redeploy
postgres:
  image: postgres:14.8

docker-compose up -d  # Recreates container with new image
```

**Benefits:**
- **Reproducible:** Same image = same behavior
- **Auditable:** Git shows exact version at any point in time
- **Testable:** Test new version, rollback if issues
- **Disposable:** Broke container? Delete and recreate, don't fix

---

## Best Practices

### 1. Pin Versions

```yaml
# ✅ Good: Specific version
image: postgres:17-alpine

# ❌ Bad: Moving target
image: postgres:latest
```

**Why:** `latest` changes over time → Different results for different developers

### 2. Use .dockerignore

```
# .dockerignore
.git
node_modules
*.log
.env
__pycache__
```

**Why:** Faster builds, smaller images, no secrets in images

### 3. Optimize Layer Order

```dockerfile
# ✅ Good: Stable layers first
FROM python:3.13-slim
RUN apt-get update && apt-get install gcc
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ ./src/              # Code changes don't rebuild dependencies

# ❌ Bad: Volatile layers first
FROM python:3.13-slim
COPY src/ ./src/              # Code change invalidates all layers below
COPY requirements.txt .
RUN pip install -r requirements.txt
```

### 4. Use Named Volumes for Data

```yaml
# ✅ Good: Named volume (managed, backed up)
volumes:
  - postgres_data:/var/lib/postgresql/data

# ❌ Bad: Bind mount for database (host path dependency)
volumes:
  - ./data:/var/lib/postgresql/data
```

### 5. Health Checks Required

```yaml
# ✅ Good: Health check ensures readiness
healthcheck:
  test: pg_isready -U appuser
  interval: 10s

# ❌ Bad: No health check (container "up" doesn't mean "ready")
```

### 6. Resource Limits in Production

```yaml
# ✅ Good: Prevents resource starvation
deploy:
  resources:
    limits:
      memory: 2G

# ⚠️ Development: Limits optional, allow flexibility
```

### 7. Use Build Secrets for Sensitive Data

```dockerfile
# ✅ Good: Build-time secrets (not in image)
RUN --mount=type=secret,id=github_token \
    git clone https://$(cat /run/secrets/github_token)@github.com/...

# ❌ Bad: Secret in environment variable (in image!)
ARG GITHUB_TOKEN
RUN git clone https://${GITHUB_TOKEN}@github.com/...
```

---

## Troubleshooting

### Container Exits Immediately

**Symptom:**
```bash
docker ps -a
# STATUS: Exited (1) 2 seconds ago
```

**Cause:** Application crashed on startup

**Fix:**
```bash
# View logs
docker logs <container_name>

# Common issues:
# - Missing environment variable
# - Port already in use
# - Database connection failed
# - Syntax error in code
```

### "Address already in use"

**Symptom:**
```
Error: bind: address already in use
```

**Cause:** Port conflict with host or other container

**Fix:**
```bash
# Find what's using port
lsof -i :5432
sudo netstat -tulpn | grep 5432

# Option 1: Stop conflicting process
# Option 2: Change port mapping
ports:
  - "5433:5432"  # Use different host port
```

### "No such image"

**Symptom:**
```
Error: image not found: myapp:latest
```

**Cause:** Image not built

**Fix:**
```bash
# Build image first
docker compose build

# Or rebuild specific service
docker compose build api
```

### Volume Permission Issues

**Symptom:**
```
Permission denied: '/data/file.txt'
```

**Cause:** Container user doesn't own volume files

**Fix:**
```dockerfile
# Dockerfile: Use correct user
USER 1000:1000  # Match host user ID

# Or: Change ownership
RUN chown -R appuser:appuser /data
```

### Network Connectivity Issues

**Symptom:**
```
Connection refused to postgres:5432
```

**Cause:** Services on different networks, or wrong hostname

**Fix:**
```bash
# Check networks
docker network ls
docker network inspect an-app_default

# Verify service names
docker compose ps

# Use service name, not localhost
# ✅ postgres:5432
# ❌ localhost:5432
```

---

## Anti-Patterns: What NOT to Do

❌ **DON'T run databases directly on your host machine for development**
- "I'll just install PostgreSQL locally and skip Docker"
- Reality: Version conflicts, port conflicts, different config than production
- Containers ensure everyone has identical environments

❌ **DON'T use `latest` tags in production**
- `image: postgres:latest` seems convenient
- Reality: Unpredictable updates break things, hard to rollback
- Always pin specific versions: `postgres:17-alpine`

❌ **DON'T store data inside containers without volumes**
- "I'll just write to `/data` inside the container"
- Reality: Data disappears when container restarts
- Always use named volumes for persistence

❌ **DON'T expose all ports to host**
- `ports: - "5432:5432"` for every service
- Reality: Port conflicts, security issues, unnecessary exposure
- Only expose what users/developers actually need (API, admin UIs)

❌ **DON'T hardcode secrets in docker-compose.yml**
- `POSTGRES_PASSWORD: mysecretpassword123`
- Reality: Secrets committed to git history forever
- Use environment variables: `POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}`

❌ **DON'T skip healthchecks**
- "The service is running, it must be ready"
- Reality: PostgreSQL process running ≠ ready to accept connections
- Always define healthchecks (see [Orchestration](orchestration.md))

❌ **DON'T manually edit files inside running containers**
- `docker compose exec api vim /app/config.py`
- Reality: Changes disappear on restart, not version controlled
- Edit source files, let hot reload pick them up

❌ **DON'T use `docker-compose` (with hyphen)**
- The old `docker-compose` v1 CLI is deprecated
- Use `docker compose` (space, v2 plugin) as shown in this repo
- v2 is faster, better integrated, and actively maintained

---

## Summary

**Infrastructure as Code = Automation + Reproducibility + Version Control**

**Key concepts:**
- **Containers:** Lightweight, isolated, portable runtime environments
- **Images:** Immutable templates built in layers, cached for speed
- **Volumes:** Persistent storage outside container lifecycle
- **Networks:** Automatic DNS-based service discovery
- **docker-compose:** Orchestrates multi-container systems declaratively

**This template demonstrates:**
- Multi-stage Dockerfile builds (see [`Dockerfile`](../../Dockerfile))
- docker-compose orchestration (see [`docker-compose.yml`](../../docker-compose.yml))
- Named volumes for persistence
- Healthchecks and dependencies
- Network isolation and service discovery

**Result:** `make dev` gives you a complete, reproducible infrastructure in minutes.

**Next Steps:**
- See [Orchestration](orchestration.md) for how everything starts up
- See [Configuration](configuration.md) for environment variables
- See [Systems](systems.md) for what each service does

