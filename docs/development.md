# Development Guide

**Daily workflow and practices that reinforce the architecture**

This guide shows you how to work with the codebase. More importantly, it shows you *why* each practice reinforces the architectural principles: immutability, explicitness, and type safety.

> **Philosophy:** Every action teaches. When you edit a frozen domain model → hot reload shows the change → commit captures the transformation → git tracks the history, you're living the architecture's principle of explicit, traceable state changes.

---

## Git Workflow

### Branch Strategy

**Never commit directly to `main`.** Always work on a feature branch.

```bash
# Start new work
git checkout -b feat/add-user-auth

# Make changes, test locally
make dev
# ... do your work ...

# Commit with clear messages
git add .
git commit -m "Add user authentication endpoints"

# Push to remote
git push origin feat/add-user-auth

# Merge back to main (after review/testing)
git checkout main
git pull origin main
git merge feat/add-user-auth
git push origin main

# Clean up
git branch -d feat/add-user-auth
```

### Branch Naming Conventions

- `feat/` - New features (e.g., `feat/add-vector-search`)
- `fix/` - Bug fixes (e.g., `fix/redis-connection-leak`)
- `docs/` - Documentation (e.g., `docs/update-install-guide`)
- `refactor/` - Code refactoring (e.g., `refactor/simplify-conversation-model`)
- `test/` - Adding tests (e.g., `test/add-conversation-tests`)

### Commit Messages

**Good commits:**
```
Add conversation history persistence to Redis
Fix model router selection for multi-vendor scenarios
Update type-system.md with RootModel examples
Refactor Conversation aggregate to use frozen models
```

**Bad commits:**
```
fix stuff
wip
updates
asdf
```

Be specific. Future you (and your team) will thank you.

---

## Development Workflow

### 1. Start the Stack

```bash
# First time setup
make setup          # Install uv and dependencies
make config         # Generate .env from secrets
make dev            # Start all services

# Verify everything is running
docker compose ps
```

**Why start fresh?** Each `make dev` proves our infrastructure is **disposable**—a core principle. If you can destroy and rebuild in seconds, nothing is hidden. All knowledge needed to run the system is explicit in code.

Visit:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474
- MinIO Console: http://localhost:9001

### 2. Make Changes

The stack supports **hot reload**—edit files in `src/`, changes apply immediately (no restart needed).

```bash
# Edit a domain model (always frozen=True)
vim src/app/domain/conversation.py

# Check logs if something breaks
make logs

# Or tail specific service
docker compose logs -f api
```

**Working with Domain Models:** Our domain models use `frozen=True` (immutable). When you edit `Conversation.send_message()`, you're changing behavior, not data structure. The method returns a new `Conversation` instance—the original is never modified.

```python
# This is how our code works (from conversation.py):
async def send_message(self, text: str) -> Conversation:
    """Returns NEW Conversation with updated history."""
    # ... process message ...
    return self.model_copy(update={"history": final_history})
```

Every state change is a traceable transformation. This isn't academic—it eliminates race conditions and makes debugging possible (compare old vs new instance).

### 3. Test Changes

```bash
# Manual testing via API docs
open http://localhost:8000/docs

# Or curl
curl -X POST http://localhost:8000/conversations \
  -H "Content-Type: application/json" \
  -d '{"initial_message": "Hello!"}'

# Run tests (when you add them)
uv run pytest
```

### 4. Commit and Push

```bash
# Check what changed
git status
git diff

# Stage changes
git add src/app/domain/conversation.py
git add docs/app/domain-models.md

# Commit with clear message
git commit -m "Add conversation persistence with Redis"

# Push to your branch
git push origin feat/your-feature
```

### 5. Clean Up

```bash
# Stop stack (preserves data)
make down

# Nuclear option: wipe everything
make clean
make dev    # Fresh start
```

**Why `make clean`?** This enforces "disposable infrastructure." Never debug yesterday's state. Start clean, stay sane. If you can't rebuild from scratch in 60 seconds, you have implicit dependencies that need to be made explicit.

---

## The Pattern in Practice

Your daily workflow embodies the architecture:

**When you edit a domain model:**
- Model is `frozen=True` → You're forced to return new instances
- Methods have clear signatures → You can't hide mutations
- Types validate automatically → Invalid states can't be constructed
- Hot reload shows immediate feedback → Fast iteration on correct code

**When you commit changes:**
- Clear commit messages → Explicit transformations (like our domain methods)
- Small, focused commits → Same principle as pure functions (one responsibility)
- Git tracks every change → Immutable history (like our frozen models)
- Branch strategy → Safe state transitions (like our status enums)

**When you work with the stack:**
- `make dev` rebuilds everything → Disposable infrastructure
- Services coordinate automatically → Declared dependencies (no tribal knowledge)
- Logs show explicit events → Traceable data flow
- Configuration is generated → Derived from source of truth

See the pattern? **Make the implicit explicit. Make the hidden visible. Everything teaches.**

---

## Command Cheat Sheet

### Stack Management

```bash
make dev              # Start all services
make down             # Stop services (keeps data)
make restart          # Quick restart
make logs             # Tail all logs
make clean            # Wipe everything (data + volumes)
make rebuild          # Clean + dev (fresh start)
```

### Configuration

```bash
make config           # Regenerate .env from secrets

# Add API key
echo "sk-ant-..." > secrets/api/anthropic
make config           # Auto-detects and adds to .env
```

### Ollama (Optional)

```bash
# After stack is running
make ollama-setup     # Pulls models from OLLAMA_PULL_MODELS

# Or manually
docker compose exec ollama ollama pull llama3.2
docker compose exec ollama ollama list
```

### Git

```bash
# Branch management
git checkout -b feat/new-thing        # Create branch
git branch                            # List branches
git branch -d feat/old-thing          # Delete branch

# Staging
git add .                             # Stage all
git add src/app/domain/*.py           # Stage specific files
git reset HEAD file.py                # Unstage file

# Committing
git commit -m "message"               # Commit staged changes
git commit --amend                    # Fix last commit message

# Syncing
git pull origin main                  # Get latest from main
git push origin feat/branch           # Push your branch
git fetch --all                       # Fetch all branches

# Merging
git checkout main
git merge feat/your-feature           # Merge branch into main

# Undoing things
git checkout -- file.py               # Discard changes to file
git reset --hard HEAD                 # Discard ALL changes (dangerous!)
git revert <commit-hash>              # Create new commit that undoes a commit
```

### Docker

```bash
# Container management
docker compose ps                     # List running services
docker compose logs -f api            # Tail specific service
docker compose restart api            # Restart specific service
docker compose exec api bash          # Shell into container

# Database shells
make shell-db                         # PostgreSQL (psql)
docker compose exec redis redis-cli -a $REDIS_PASSWORD
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD

# Cleanup
docker compose down -v                # Remove containers + volumes
docker system prune -a                # Clean up unused images/containers
```

### Python/uv

```bash
# Dependency management
uv add package-name                   # Add dependency
uv remove package-name                # Remove dependency
uv sync                               # Install from lockfile
uv lock                               # Update lockfile

# Running commands
uv run python script.py               # Run script in venv
uv run pytest                         # Run tests
uv run mypy src/                      # Type checking
```

---

## Best Practices

### Development Habits

1. **Start fresh daily** - `make down && make dev` ensures clean state
2. **Check logs early** - When something breaks, `make logs` first
3. **Commit often** - Small, focused commits are easier to review and revert
4. **Test locally** - Use the API docs at `/docs` to test endpoints manually
5. **Clean up branches** - Delete merged branches to keep repo tidy

### Code Quality

1. **Types everywhere** - Use Pydantic models, avoid `dict[str, Any]`
2. **Immutable domain models** - Always `frozen=True`
3. **Thin services** - No business logic in service layer
4. **Document domain code** - Rich docstrings on domain models
5. **Follow existing patterns** - Read existing code before adding new patterns

### Infrastructure

1. **Never edit `.env` directly** - Use `secrets/` and `make config`
2. **Never commit secrets** - Check `.gitignore` before committing
3. **Use volumes for data** - Don't store state in containers
4. **One service per concern** - Don't merge databases

---

## Troubleshooting

### Port already in use

```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or stop all containers
make down
```

### Container won't start

```bash
# Check logs for specific service
docker compose logs postgres

# Rebuild container
docker compose up -d --build api

# Nuclear option
make rebuild
```

### Hot reload not working

```bash
# Ensure volume mount is correct
docker compose exec api ls /app/src

# Restart with rebuild
make restart
```

### Database connection errors

```bash
# Check if services are healthy
docker compose ps

# Regenerate config
make config
make restart
```

### Git conflicts

```bash
# Update main first
git checkout main
git pull origin main

# Rebase your branch
git checkout feat/your-branch
git rebase main

# Resolve conflicts in files, then
git add .
git rebase --continue
```

---

## Next Steps

- Read [Type System](app/type-system.md) to understand domain modeling patterns
- Read [Service Patterns](app/service-patterns.md) to understand layer boundaries
- Read [Orchestration](infra/orchestration.md) to understand how the stack works
- Read [Configuration](infra/configuration.md) to understand secrets management

**Questions?** Check the existing code—it's designed to teach. Every domain model has rich docstrings, every infra script has explanatory comments.

