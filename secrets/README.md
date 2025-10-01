# API Keys & Secrets Setup

This directory stores sensitive credentials that power the AI-native application. **Nothing in this directory is committed to git** (see `.gitignore`).

## Quick Start

**Add your API keys in 3 steps:**

```bash
# 1. Add Anthropic API key (for Claude models)
echo "sk-ant-your-key-here" > secrets/api/anthropic

# 2. Add OpenAI API key (for GPT models)
echo "sk-your-key-here" > secrets/api/openai

# 3. Add Tavily API key (for web search)
echo "tvly-your-key-here" > secrets/api/tavily
```

**Then start the stack:**

```bash
make dev
```

The configuration generation script automatically loads these keys and makes them available to the application with full type safety.

---

## Obtaining API Keys

### 1. Anthropic API Key (Claude Models)

**Claude Sonnet 4.5** is used for complex reasoning, long context analysis, and creative tasks.

**Steps to obtain:**

1. **Create an Anthropic account:**
   - Visit https://console.anthropic.com/login
   - Sign up with email or SSO

2. **Generate an API key:**
   - After logging in, navigate to **"API Keys"** in the console
   - Click **"Create Key"**
   - Give it a descriptive name (e.g., "ai-native-app-dev")
   - Copy the key immediately (it's only shown once!)

3. **Add to project:**
   ```bash
   echo "sk-ant-api03-your-key-here" > secrets/api/anthropic
   ```

**API key format:** Starts with `sk-ant-`

**Pricing:** Pay-as-you-go. Free tier available with rate limits.  
**Docs:** https://docs.anthropic.com/en/docs/initial-setup

---

### 2. OpenAI API Key (GPT Models)

**GPT-4** and variants are used for general-purpose reasoning and fast inference.

**Steps to obtain:**

1. **Create an OpenAI account:**
   - Visit https://platform.openai.com/signup
   - Sign up with email or existing account

2. **Generate an API key:**
   - Log in to https://platform.openai.com/api-keys
   - Click **"Create new secret key"**
   - Give it a name (e.g., "ai-native-app-dev")
   - Copy the key immediately (it's only shown once!)

3. **Add to project:**
   ```bash
   echo "sk-proj-your-key-here" > secrets/api/openai
   ```

**API key format:** Starts with `sk-proj-` or `sk-`

**Pricing:** Pay-as-you-go. Requires adding payment method.  
**Docs:** https://platform.openai.com/docs/quickstart

---

### 3. Tavily API Key (Web Search)

**Tavily** provides AI-optimized web search for retrieving current information, news, and facts.

**Steps to obtain:**

1. **Create a Tavily account:**
   - Visit https://tavily.com
   - Sign up for free

2. **Generate an API key:**
   - After logging in, go to **"API Keys"** in account settings
   - Click **"Create API Key"**
   - Copy the key immediately

3. **Add to project:**
   ```bash
   echo "tvly-your-key-here" > secrets/api/tavily
   ```

**API key format:** Starts with `tvly-`

**Pricing:** Free tier available (1,000 searches/month). Paid plans for higher usage.  
**Docs:** https://docs.tavily.com

---

## Directory Structure

```
secrets/
├── README.md              # This file
├── env-template.txt       # Source of truth for configuration
├── api/                   # LLM provider API keys
│   ├── anthropic          # Claude models
│   ├── openai             # GPT models
│   └── tavily             # Web search
└── infra/                 # Infrastructure passwords
    ├── db-password        # PostgreSQL (auto-generated)
    ├── neo4j-password     # Neo4j (auto-generated)
    ├── redis-password     # Redis (auto-generated)
    ├── minio-access-key   # MinIO (auto-generated)
    └── minio-secret-key   # MinIO (auto-generated)
```

---

## How It Works

### The Four-Layer System

1. **Template** (`env-template.txt`) - Source of truth with `NEED-API-KEY` placeholders
2. **Secrets** (`api/*` files) - Your actual API keys (git-ignored)
3. **Generation** (`infra/generate-config.sh`) - Reads secrets, generates `.env`
4. **Validation** (`src/app/config.py`) - Type-safe Pydantic settings

**The flow:**

```
secrets/api/anthropic → generate-config.sh → .env → Settings class → Application
    (your key)            (automation)      (envs)   (validation)    (type-safe)
```

### What Gets Auto-Generated

You only need to provide **API keys**. Everything else is auto-generated:

- ✅ **Auto-generated:** Database passwords, Redis password, MinIO credentials
- ❌ **You provide:** Anthropic, OpenAI, Tavily API keys

**Why?** API keys require external accounts. Infrastructure secrets can be random-generated locally.

---

## Working Without API Keys

**The stack works without any API keys!**

If you skip adding API keys, the application will:
- ✅ Use **Ollama** for local LLM inference (free, private)
- ✅ Still run all infrastructure (PostgreSQL, Redis, Neo4j, etc.)
- ❌ Cannot use Claude or GPT models
- ❌ Cannot use Tavily web search

**To use only local models:**

```bash
# Just start the stack
make dev

# Ollama will be available at http://localhost:11434
```

The model registry automatically detects which API keys are present and only enables those providers.

---

## Verification

### Check if your API keys are loaded:

```bash
# 1. Verify files exist
ls -la secrets/api/

# 2. Check they have content (without revealing keys)
wc -l secrets/api/*

# 3. Verify they're loaded into .env (after make dev)
grep "API_KEY=" .env

# 4. Test in running application
docker compose exec api python -c "from app.config import settings; print('Anthropic:', bool(settings.anthropic_api_key and settings.anthropic_api_key != 'NEED-API-KEY'))"
```

### Expected output:

```bash
$ ls -la secrets/api/
-rw------- 1 user user  108 Jan 15 10:30 anthropic
-rw------- 1 user user   92 Jan 15 10:31 openai
-rw------- 1 user user   76 Jan 15 10:32 tavily

$ grep "API_KEY=" .env
ANTHROPIC_API_KEY=sk-ant-api03-abc123...
OPENAI_API_KEY=sk-proj-xyz789...
TAVILY_API_KEY=tvly-def456...
```

---

## Security Best Practices

### ✅ DO:
- **Store keys in files** (this directory structure)
- **Use restrictive permissions:** `chmod 600 secrets/api/*`
- **Use different keys per environment** (dev vs prod)
- **Rotate keys periodically** (every 90 days recommended)
- **Use read-only keys** when possible (Anthropic/OpenAI support this)
- **Set spending limits** in provider dashboards

### ❌ DON'T:
- **Never commit API keys to git** (already in `.gitignore`, but verify!)
- **Never hardcode keys** in source code
- **Never log full keys** (log only "key present: yes/no")
- **Never share keys** in chat/email/docs
- **Never use production keys** in development

### File Permissions

API key files should be readable only by you:

```bash
# Set correct permissions
chmod 600 secrets/api/*

# Verify
ls -la secrets/api/
# Should show: -rw------- (owner read/write only)
```

---

## Troubleshooting

### Error: `ValidationError: anthropic_api_key field required`

**Cause:** API key file is empty or contains placeholder text.

**Fix:**
```bash
# Check content (don't commit this!)
cat secrets/api/anthropic

# Should contain actual key, not "NEED-API-KEY"
# If empty or wrong, re-add:
echo "sk-ant-your-actual-key" > secrets/api/anthropic

# Restart
make dev
```

---

### Error: `ANTHROPIC_API_KEY=NEED-API-KEY in .env`

**Cause:** API key file doesn't exist when `generate-config.sh` runs.

**Fix:**
```bash
# 1. Add the key
echo "sk-ant-your-key" > secrets/api/anthropic

# 2. Regenerate config
infra/generate-config.sh

# 3. Restart services
make restart
```

---

### Error: API requests fail with 401 Unauthorized

**Possible causes:**

1. **Invalid key format**
   ```bash
   # Check for extra quotes, whitespace, or newlines
   cat -A secrets/api/anthropic
   # Should show: sk-ant-api03-abc123$
   # NOT: "sk-ant-api03-abc123"$ or sk-ant-api03-abc123 $ (trailing space)
   ```

2. **Key expired or revoked**
   - Check provider dashboard
   - Generate a new key and update

3. **Spending limit reached**
   - Check usage in provider console
   - Add payment method or increase limit

---

### Keys not loading after adding them

**Cause:** Services were already running when you added keys.

**Fix:**
```bash
# Regenerate .env and restart
infra/generate-config.sh
make restart

# Or full clean restart
make clean
make dev
```

---

### Want to remove an API key?

```bash
# Option 1: Delete the file (provider disabled)
rm secrets/api/openai

# Option 2: Replace with empty sentinel
echo "NEED-API-KEY" > secrets/api/openai

# Then regenerate and restart
infra/generate-config.sh
make restart
```

The application will work with remaining providers. Model registry auto-detects available keys.

---

## Rotating API Keys

**Best practice:** Rotate keys every 90 days.

```bash
# 1. Generate new key in provider console
# 2. Update the file
echo "new-key" > secrets/api/anthropic

# 3. Regenerate config and restart
infra/generate-config.sh
make restart

# 4. Verify new key works
curl -X POST http://localhost:8000/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'

# 5. Revoke old key in provider console
```

**Zero-downtime rotation** (production):
1. Add new key to environment
2. Deploy
3. Verify new key works
4. Remove old key from environment
5. Revoke old key in console

---

## Production Considerations

### Environment-Specific Keys

Use different API keys for each environment:

```bash
# Development
secrets/api/anthropic → dev-team-key

# Staging
secrets/api/anthropic → staging-key

# Production
secrets/api/anthropic → production-key
```

**Why?** Spending controls, usage tracking, blast radius limitation.

### Secrets Management Services

For production, consider using:

- **HashiCorp Vault** - Secret storage and rotation
- **AWS Secrets Manager** - Managed secrets with IAM integration
- **Google Secret Manager** - GCP-native secrets
- **Azure Key Vault** - Azure-native secrets

**Integration example:**

```bash
# Fetch from Vault and write to local file structure
vault read secret/api/anthropic > secrets/api/anthropic

# Then use existing generation pipeline
infra/generate-config.sh
```

The four-layer system remains the same; you just change how secrets get into the `secrets/` directory.

---

## Learn More

- **Deep dive on configuration system:** [`docs/infra/configuration.md`](../docs/infra/configuration.md)
- **How secrets flow through the system:** [`docs/infra/configuration.md#the-four-layer-system`](../docs/infra/configuration.md)
- **Type-safe settings consumption:** [`src/app/config.py`](../src/app/config.py)
- **Model registry and API key detection:** [`src/app/domain/model_catalog.py`](../src/app/domain/model_catalog.py)

---

## Quick Reference

**Common commands:**

```bash
# Add API keys
echo "sk-ant-..." > secrets/api/anthropic
echo "sk-proj-..." > secrets/api/openai
echo "tvly-..." > secrets/api/tavily

# Verify keys exist
ls -la secrets/api/

# Regenerate config
infra/generate-config.sh

# Restart with new keys
make restart

# Full clean start
make clean && make dev

# Check which providers are enabled
docker compose exec api python -c "
from app.domain.model_catalog import ModelRegistry
from app.config import settings
registry = ModelRegistry.from_settings(settings)
print('Available vendors:', [v.value for v in registry.available_vendors])
"
```

**Need help?** Read [`docs/infra/configuration.md`](../docs/infra/configuration.md) for comprehensive documentation on the configuration system.

