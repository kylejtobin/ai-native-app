# Configuration & Secrets Management

**Configuration is how your application adapts to different environments without changing code.**

This template implements a sophisticated configuration system that handles API keys, database passwords, connection strings, and application settings—all type-safe, all version-controlled (except the secrets themselves), and all generated from a single source of truth.

---

## The Problem: Configuration Hell

Most projects handle configuration poorly:

**Anti-Pattern #1: Hardcoded values**
```python
DATABASE_URL = "postgresql://localhost:5432/mydb"
API_KEY = "sk-abc123..."  # 😱 Committed to git!
```

**Anti-Pattern #2: Manual .env files**
```bash
# Developer A's .env
DATABASE_PASSWORD=password123

# Developer B's .env  
DATABASE_PASSWORD=securepass456

# Different passwords = different behavior = debugging nightmare
```

**Anti-Pattern #3: Copy-paste config**
```bash
# Oh, you need a new API key?
# 1. Update .env
# 2. Update docker-compose.yml
# 3. Update config.py
# 4. Hope you didn't miss anything
```

**Anti-Pattern #4: Secrets in version control**
```bash
git log | grep -i "password"
# commit a3f2b1c: "Updated production database password"
# 💀 Your secrets are now in git history FOREVER
```

---

## The Solution: Four-Layer Configuration

We use a sophisticated system with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SOURCE OF TRUTH                                          │
│    secrets/env-template.txt (version-controlled)            │
│    - Defines all variables                                  │
│    - Documents structure                                    │
│    - Never contains real secrets                            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. SECRET STORAGE                                           │
│    secrets/api/* (git-ignored)                              │
│    secrets/infra/* (git-ignored, auto-generated)            │
│    - API keys provided by developer                         │
│    - Infrastructure passwords cached                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CONFIG GENERATION                                        │
│    infra/generate-config.sh                                 │
│    - Reads template                                         │
│    - Loads secrets from files                               │
│    - Generates connection strings                           │
│    - Writes .env (git-ignored)                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. TYPE-SAFE CONSUMPTION                                    │
│    src/app/config.py                                        │
│    - Validates all variables exist                          │
│    - Parses types (int, bool, etc.)                         │
│    - Provides IDE autocomplete                              │
│    - Single source of truth in code                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: The Template (Source of Truth)

**File:** [`secrets/env-template.txt`](../../secrets/env-template.txt)

This file is **checked into git** and defines the structure of all configuration. It's the contract between infrastructure and application.

### The Four Sections

The template is organized into four sections, each with different purposes:

#### Section 1: User API Keys (Developer-Provided)

```bash
# LLM Provider API Keys
OPENAI_API_KEY=NEED-API-KEY       # OpenAI GPT models
ANTHROPIC_API_KEY=NEED-API-KEY    # Claude models
TAVILY_API_KEY=NEED-API-KEY       # Search API
```

**Purpose:** External service credentials that developers must provide.

**Value:** `NEED-API-KEY` is a **sentinel value**
- Makes missing keys obvious (app fails fast with clear error)
- Better than empty string (which might be silently ignored)
- Shows which keys are required

**How to provide:**
```bash
# Create files in secrets/api/ (git-ignored)
echo "sk-ant-api-key-here" > secrets/api/anthropic
echo "sk-openai-key" > secrets/api/openai
echo "tvly-key" > secrets/api/tavily
```

**Convention:** `secrets/api/<service>` → `<SERVICE>_API_KEY`

#### Section 2: Auto-Generated Secrets (Script-Created)

```bash
# Leave these BLANK - script will populate them
DATABASE_PASSWORD=      # PostgreSQL appuser password
REDIS_PASSWORD=         # Redis authentication password
NEO4J_PASSWORD=         # Neo4j database password
```

**Purpose:** Random passwords for infrastructure services.

**Value:** Left blank in template (script generates 32-char random strings)

**Caching:** Stored in `secrets/infra/` after first generation
```
secrets/infra/db-password
secrets/infra/redis-password
secrets/infra/neo4j-password
```

**Why cache?**
- PostgreSQL won't start if password changes (data encrypted with old password)
- Redis connections break if password changes
- Stability across `make dev` runs

#### Section 3: Derived Values (Computed)

```bash
# Leave these BLANK - script computes from other values
DATABASE_URL=           # postgresql+asyncpg://appuser:${PASSWORD}@postgres:5432/appdb
REDIS_URL=              # redis://:${PASSWORD}@redis:6379
```

**Purpose:** Complex values built from components.

**Why derive?**
- Single source of truth (password + host + port → URL)
- No chance of password mismatch between `DATABASE_PASSWORD` and `DATABASE_URL`
- Easy to update (change password once, URL updates automatically)

**Format examples:**
```bash
# PostgreSQL with asyncpg driver
postgresql+asyncpg://user:password@host:port/database

# Redis with password auth
redis://:password@host:port
```

#### Section 4: Static Configuration (Rarely Changes)

```bash
# Database Configuration (PostgreSQL)
DATABASE_HOST=postgres              # Docker service name
DATABASE_PORT=5432                  # Standard PostgreSQL port
DATABASE_NAME=appdb                 # Database name
DATABASE_USER=appuser               # Application user

# FastAPI Configuration
API_HOST=0.0.0.0                    # Listen on all interfaces
API_PORT=8000                       # HTTP port
LOG_LEVEL=INFO                      # Logging verbosity
```

**Purpose:** Defaults that rarely change, documented for clarity.

**When to modify:**
- Changing service names in docker-compose.yml
- Using non-standard ports
- Adjusting performance settings (pool sizes, timeouts)

---

## Layer 2: Secret Storage (Git-Ignored)

Secrets never go in git. They live in the filesystem, ignored by version control.

### Directory Structure

```
secrets/
├── .gitignore              # Ensures secrets/ contents ignored
├── env-template.txt        # ✅ VERSION CONTROLLED (no secrets)
├── api/                    # 🔒 GIT-IGNORED (user secrets)
│   ├── anthropic           # Contains: sk-ant-api-...
│   ├── openai              # Contains: sk-proj-...
│   └── tavily              # Contains: tvly-...
└── infra/                  # 🔒 GIT-IGNORED (generated secrets)
    ├── db-password         # Auto-generated, cached
    ├── redis-password      # Auto-generated, cached
    ├── neo4j-password      # Auto-generated, cached
    ├── minio-access-key    # Auto-generated, cached
    └── minio-secret-key    # Auto-generated, cached
```

### secrets/api/* - User-Provided Secrets

**Format:** One secret per file, no quotes, no variable name

```bash
# ✅ Good
$ cat secrets/api/anthropic
sk-ant-api03-abc123xyz...

# ❌ Bad (don't include quotes)
$ cat secrets/api/anthropic
"sk-ant-api03-abc123xyz..."

# ❌ Bad (don't include variable name)
$ cat secrets/api/anthropic
ANTHROPIC_API_KEY=sk-ant-api03-abc123xyz...
```

**How to add a new API key:**
1. Create file in `secrets/api/` (lowercase service name)
2. Add corresponding variable to `secrets/env-template.txt`
3. Add corresponding field to `src/app/config.py`
4. Run `make config`

**Example:**
```bash
# 1. Create secret file
echo "your-groq-key" > secrets/api/groq

# 2. Add to template (if not already there)
echo "GROQ_API_KEY=NEED-API-KEY" >> secrets/env-template.txt

# 3. Add to config.py
# groq_api_key: str = Field(..., alias="GROQ_API_KEY")

# 4. Generate .env
make config
```

### secrets/infra/* - Auto-Generated Secrets

**Lifecycle:**
1. First `make config` → Script generates random 32-char strings
2. Written to `secrets/infra/<service>-password`
3. Subsequent runs → Script reads from cache (stable!)
4. `make clean` → Deleted, regenerated on next `make config`

**Why this matters:**

**Without caching:**
```bash
make dev              # DB password: abc123
# ... work work work ...
make restart          # DB password: xyz789
# PostgreSQL: "Password changed, cannot decrypt data!"
# 💀 All your local data is now inaccessible
```

**With caching:**
```bash
make dev              # DB password: abc123 (generated, cached)
# ... work work work ...
make restart          # DB password: abc123 (read from cache)
# PostgreSQL: "Welcome back!" ✅
```

---

## Layer 3: Config Generation (The Magic)

**File:** [`infra/generate-config.sh`](../../infra/generate-config.sh)

This script orchestrates everything. It's called by `make config` (which is called by `make dev`).

### What It Does (Step-by-Step)

#### Step 1: Copy Template to .env

```bash
cp secrets/env-template.txt .env
```

**Why:** Start with the source of truth, then populate it.

#### Step 2: Load User API Keys

```bash
# For each file in secrets/api/
for file in secrets/api/*; do
    service_name=$(basename "$file")            # "anthropic"
    env_key="${service_name^^}_API_KEY"         # "ANTHROPIC_API_KEY"
    value=$(cat "$file")                        # "sk-ant-..."
    
    # Replace in .env: ANTHROPIC_API_KEY=NEED-API-KEY → ANTHROPIC_API_KEY=sk-ant-...
    sed -i "s|^${env_key}=.*|${env_key}=${value}|" .env
done
```

**Convention:** Filename → Environment variable
- `secrets/api/anthropic` → `ANTHROPIC_API_KEY`
- `secrets/api/openai` → `OPENAI_API_KEY`
- `secrets/api/tavily` → `TAVILY_API_KEY`

**Dynamic detection:** No hardcoding! Drop a new file in `secrets/api/`, it's automatically loaded.

#### Step 3: Generate/Load Infrastructure Secrets

```bash
# Generate random password or read from cache
ensure_secret() {
    local path="$1"
    local generator="$2"
    
    if [ ! -f "$path" ]; then
        eval "$generator" > "$path"  # Generate new
    fi
    
    cat "$path"  # Return (cached or fresh)
}

# Use it
DB_PASSWORD=$(ensure_secret "secrets/infra/db-password" "random_ascii")
```

**Idempotent:** Safe to run multiple times
- First run: Generates random password, writes to `secrets/infra/db-password`
- Subsequent runs: Reads from `secrets/infra/db-password`

**Reset:** Only `make clean` deletes cached secrets

#### Step 4: Compute Connection Strings

```bash
# Build PostgreSQL URL from components
DATABASE_URL="postgresql+asyncpg://appuser:${DB_PASSWORD}@postgres:5432/appdb"

# Build Redis URL from components
REDIS_URL="redis://:${REDIS_PASSWORD}@redis:6379"

# Replace in .env
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" .env
sed -i "s|^REDIS_URL=.*|REDIS_URL=${REDIS_URL}|" .env
```

**Single source of truth:**
- Password lives in ONE place (`secrets/infra/db-password`)
- Used to build `DATABASE_PASSWORD` (standalone)
- Used to build `DATABASE_URL` (connection string)
- Impossible for them to mismatch

#### Step 5: Validate

```bash
# Extract all ${VAR} references from docker-compose.yml
required_vars=$(grep -o '\${[A-Z0-9_]*}' docker-compose.yml | tr -d '${}'  | sort -u)

# Check each one exists in .env
for var in $required_vars; do
    if ! grep -q "^$var=" .env; then
        echo "Missing: $var"
    fi
done
```

**Why:** Catch missing variables BEFORE Docker tries to start

**Result:** `.env` file ready for `docker compose up`

---

## Layer 4: Type-Safe Consumption

**File:** [`src/app/config.py`](../../src/app/config.py)

This is where configuration meets your application code. Using Pydantic Settings, we get type-safe parsing with validation.

### The Settings Class

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    """Type-safe application configuration"""
    
    # Application
    app_name: str = Field(..., alias="APP_NAME")
    app_version: str = Field(..., alias="APP_VERSION")
    
    # Database
    database_url: str = Field(..., alias="DATABASE_URL")
    database_port: int = Field(..., alias="DATABASE_PORT")  # Parsed as int!
    
    # API Keys
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    
    model_config = {"env_file": ".env"}
```

### What Pydantic Settings Does

**1. Loads from .env automatically**
```python
settings = Settings()  # Reads .env, no manual loading needed
```

**2. Type parsing and validation**
```bash
# In .env
DATABASE_PORT=5432
DB_POOL_SIZE=5
API_RELOAD=true
```

```python
# In code
settings.database_port  # int (5432)
settings.db_pool_size   # int (5)
settings.api_reload     # bool (True)
```

**3. Fails fast on missing required fields**
```python
# If ANTHROPIC_API_KEY is missing or "NEED-API-KEY"
Settings()  # ValidationError: anthropic_api_key field required
```

**4. IDE autocomplete**
```python
settings.data  # IDE shows: database_url, database_port, database_name...
```

**5. Type safety**
```python
settings.database_port + 1  # ✅ Works (int + int)
settings.app_name + 1       # ❌ Type error caught by mypy
```

### Using Configuration in Code

```python
from app.config import settings

# Direct access
print(f"Starting {settings.app_name} v{settings.app_version}")

# Pass to clients
redis_client = redis.from_url(settings.redis_url)
pg_pool = create_engine(settings.database_url)

# Conditional logic
if settings.environment == "production":
    logger.setLevel(settings.log_level)
```

### Adding New Configuration

**Step 1:** Add to template
```bash
# secrets/env-template.txt
NEW_SERVICE_URL=http://newservice:9000
NEW_SERVICE_TIMEOUT=30
```

**Step 2:** Add to config.py
```python
# src/app/config.py
class Settings(BaseSettings):
    new_service_url: str = Field(..., alias="NEW_SERVICE_URL")
    new_service_timeout: int = Field(..., alias="NEW_SERVICE_TIMEOUT")
```

**Step 3:** Regenerate and use
```bash
make config  # Regenerates .env with new values
```

```python
# Now available everywhere
from app.config import settings
client = SomeClient(url=settings.new_service_url)
```

---

## The Configuration Flow (End-to-End)

Let's trace a single configuration value from creation to usage:

### Example: Anthropic API Key

**1. Developer provides secret**
```bash
$ echo "sk-ant-api03-xyz..." > secrets/api/anthropic
```

**2. Template defines structure**
```bash
# secrets/env-template.txt
ANTHROPIC_API_KEY=NEED-API-KEY
```

**3. Script generates .env**
```bash
$ make config
Scanning for API keys in secrets/api/...
  ✓ ANTHROPIC_API_KEY from secrets/api/anthropic
```

**Result: `.env` file**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xyz...
```

**4. Docker Compose uses it**
```yaml
# docker-compose.yml
services:
  api:
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}  # Reads from .env
```

**5. Pydantic validates it**
```python
# src/app/config.py
class Settings(BaseSettings):
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

settings = Settings()  # Validates ANTHROPIC_API_KEY exists and is non-empty
```

**6. Application uses it**
```python
# src/app/domain/conversation.py
from app.config import settings

client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
```

**Type safety at every step:**
- File exists (shell script checks)
- Variable in .env (validation step)
- Docker has it (compose interpolates)
- Python has it (Pydantic validates)
- Code uses it (type-checked)

---

## Security Best Practices

### ✅ DO: Keep secrets in files, not templates

```bash
# ✅ Good
$ echo "my-secret-key" > secrets/api/myservice
$ git status
# secrets/api/ is ignored ✅

# ❌ Bad
# secrets/env-template.txt
MYSERVICE_API_KEY=my-secret-key  # 💀 Committed to git!
```

### ✅ DO: Use different secrets per environment

```bash
# Development
secrets/api/anthropic          # Personal dev key

# Production (separate server)
secrets/api/anthropic          # Production key (different!)
```

### ✅ DO: Rotate secrets regularly

```bash
# Get new key from provider
echo "new-key" > secrets/api/anthropic

# Regenerate config
make config

# Restart services
make restart
```

### ✅ DO: Use sentinel values in templates

```bash
# Good
ANTHROPIC_API_KEY=NEED-API-KEY  # Fails loudly if missing

# Bad
ANTHROPIC_API_KEY=                # Silently breaks
```

### ❌ DON'T: Commit .env or secrets/

```bash
# .gitignore (already configured)
.env
secrets/api/*
secrets/infra/*
```

### ❌ DON'T: Share secrets in chat/email

```bash
# Bad: "Hey, the API key is sk-ant-..."
# Good: "I put the API key in secrets/api/anthropic on the server"
```

### ❌ DON'T: Log secrets

```python
# Bad
logger.info(f"Using API key: {settings.anthropic_api_key}")

# Good
logger.info("Anthropic API key configured")
```

---

## Common Workflows

### First-Time Setup (New Developer)

```bash
# 1. Clone repository
git clone <repo>
cd <repo>

# 2. Add API keys
echo "your-anthropic-key" > secrets/api/anthropic
echo "your-openai-key" > secrets/api/openai

# 3. Generate config and start
make dev

# ✅ Stack starts with your keys, generated passwords
```

### Adding a New API Key

```bash
# 1. Get key from provider
echo "new-service-key" > secrets/api/newservice

# 2. Add to template
echo "NEWSERVICE_API_KEY=NEED-API-KEY" >> secrets/env-template.txt

# 3. Add to config.py
# newservice_api_key: str = Field(..., alias="NEWSERVICE_API_KEY")

# 4. Regenerate and restart
make restart
```

### Rotating Secrets

```bash
# 1. Update secret file
echo "new-rotated-key" > secrets/api/anthropic

# 2. Regenerate config
make config

# 3. Restart services
make restart
```

### Debugging Missing Configuration

```bash
# Check what's in .env
grep ANTHROPIC_API_KEY .env

# Check if secret file exists
ls -la secrets/api/anthropic

# Regenerate config with verbose output
make config

# Check if app can load it
docker compose exec api python -c "from app.config import settings; print(settings.anthropic_api_key)"
```

### Reset Everything

```bash
# Wipe all generated config and secrets
make clean

# Remove user-provided keys (be careful!)
rm secrets/api/*

# Start fresh
echo "new-key" > secrets/api/anthropic
make dev
```

---

## Troubleshooting

### "NEED-API-KEY" in error messages

**Symptom:**
```python
ValidationError: ANTHROPIC_API_KEY: Value is 'NEED-API-KEY'
```

**Cause:** API key not provided

**Fix:**
```bash
echo "your-actual-key" > secrets/api/anthropic
make config
make restart
```

### "Field required" validation error

**Symptom:**
```python
ValidationError: anthropic_api_key field required
```

**Cause:** Variable missing from .env entirely

**Fix:**
```bash
# Check if variable is in template
grep ANTHROPIC_API_KEY secrets/env-template.txt

# If not, add it
echo "ANTHROPIC_API_KEY=NEED-API-KEY" >> secrets/env-template.txt

# Regenerate
make config
```

### Password changed, PostgreSQL won't start

**Symptom:**
```
postgres-1  | FATAL: password authentication failed for user "appuser"
```

**Cause:** Cached password changed but volume still has old data

**Fix:**
```bash
# Nuclear option: wipe everything
make clean

# Then start fresh
make dev
```

### Secret file has wrong format

**Symptom:**
```bash
# grep shows quotes in .env
ANTHROPIC_API_KEY="sk-ant-..."  # Extra quotes!
```

**Cause:** Secret file contains quotes

**Fix:**
```bash
# Bad (has quotes)
echo '"sk-ant-key"' > secrets/api/anthropic

# Good (no quotes)
echo 'sk-ant-key' > secrets/api/anthropic

# Regenerate
make config
```

---

## Advanced Patterns

### Environment-Specific Configuration

```bash
# Have multiple templates
secrets/env-template.dev.txt
secrets/env-template.prod.txt

# Generate for specific environment
TEMPLATE=secrets/env-template.prod.txt infra/generate-config.sh
```

### Shared Secrets Across Team

```bash
# Use a shared secrets manager (not in repo)
# 1. Fetch from vault
vault read secret/api/anthropic > secrets/api/anthropic

# 2. Generate config
make config

# 3. Start stack
make dev
```

### Docker Build-Time Secrets

```dockerfile
# Dockerfile
RUN --mount=type=secret,id=anthropic \
    ANTHROPIC_API_KEY=$(cat /run/secrets/anthropic) \
    python setup.py
```

```bash
# Build with secret
docker build --secret id=anthropic,src=secrets/api/anthropic .
```

---

## Summary

**Configuration is a pipeline:**

```
Template (git) → Secrets (filesystem) → Generation (script) → Validation (Pydantic) → Usage (code)
```

**Key principles:**
1. **Template is source of truth** (defines structure)
2. **Secrets never in git** (filesystem only)
3. **Generation is automatic** (`make config`)
4. **Validation is type-safe** (Pydantic Settings)
5. **Usage is simple** (`settings.database_url`)

**One command starts everything:**
```bash
make dev  # Generates config → Starts services → You're coding
```

**Next Steps:**
- See [Orchestration](orchestration.md) for how config integrates with Docker
- See [Systems](systems.md) for what each configured service does
- See [IaC](iac.md) for how Docker uses these environment variables

