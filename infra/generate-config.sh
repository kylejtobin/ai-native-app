#!/bin/bash
# =============================================================================
# Configuration Generator - Secrets & Environment Management
# =============================================================================
# This script generates .env from secrets/env-template.txt with smart defaults
#
# Strategy:
#   1. User-provided secrets (secrets/api/*) are loaded dynamically
#   2. Infrastructure secrets are auto-generated once and cached
#   3. Connection strings are derived from secrets (single source of truth)
#   4. Template is never modified - .env is always generated fresh
#
# File Structure:
#   secrets/api/anthropic    → ANTHROPIC_API_KEY (user-provided, git-ignored)
#   secrets/infra/*          → Auto-generated passwords (cached, git-ignored)
#   secrets/env-template.txt → The template (checked into git)
#   .env                     → Generated output (git-ignored)
#
# Usage:
#   ./infra/generate-config.sh     # Run directly
#   make config                    # Run via Makefile
#
# Why this approach?
#   - API keys stay in files (not pasted into templates)
#   - Infra secrets are stable across rebuilds (cached)
#   - Adding new API keys is automatic (just drop file in secrets/api/)
#   - Type safety in config.py still enforced (template has all keys)

set -euo pipefail

TEMPLATE="secrets/env-template.txt"
ENV_FILE=".env"
SECRETS_DIR="secrets/infra"

# Ensure secrets directory exists
mkdir -p "$SECRETS_DIR"

# =============================================================================
# Helper Functions
# =============================================================================

# Generate random alphanumeric string (32 chars)
# Used for database passwords, MinIO keys, etc.
random_ascii() {
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32
}

# Escape special characters for sed replacement
# Handles backslashes, ampersands, newlines safely
escape_sed() {
    local value="$1"
    value="${value//\\/\\\\}"    # Escape backslashes
    value="${value//&/\&}"        # Escape ampersands
    value="${value//$'\n'/\n}"    # Escape newlines
    printf '%s' "$value"
}

# Replace a line in .env file (cross-platform sed)
# Args: KEY VALUE
replace_line() {
    local key="$1"
    local raw_value="$2"
    local value=$(escape_sed "$raw_value")
    # macOS uses 'sed -i ""', Linux uses 'sed -i'
    if [[ "$(uname)" == "Darwin" ]]; then
        sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    fi
}

# Generate secret once and cache to file, or read existing
# This ensures secrets don't change between rebuilds (stable infra state)
# Args: PATH GENERATOR_COMMAND
ensure_secret() {
    local path="$1"
    local generator="$2"
    if [ ! -f "$path" ]; then
        eval "$generator" > "$path"
    fi
    tr -d '\n\r' < "$path"  # Strip whitespace/newlines
}

# =============================================================================
# Step 1: Copy Template to .env
# =============================================================================
# Start fresh - always generate from template
cp "$TEMPLATE" "$ENV_FILE"

# =============================================================================
# Step 2: Load User API Keys Dynamically
# =============================================================================
# Convention: secrets/api/<service> → <SERVICE>_API_KEY
# Example: secrets/api/anthropic → ANTHROPIC_API_KEY
#
# Why this works:
#   - User drops API key file into secrets/api/
#   - Script auto-detects and loads it
#   - No need to update this script for new providers
#   - Git ignores secrets/api/* (keys never committed)

echo "Scanning for API keys in secrets/api/..."
if [ -d "secrets/api" ]; then
    for file_path in secrets/api/*; do
        if [ -f "$file_path" ]; then
            service_name=$(basename "$file_path")
            # Convert filename to uppercase + append _API_KEY
            # Example: "anthropic" → "ANTHROPIC_API_KEY"
            env_key="${service_name^^}_API_KEY"
            
            # Read key from file (strip whitespace)
            value=$(tr -d '\n\r' < "$file_path")
            
            # Only replace if key exists in template (type safety!)
            # This ensures config.py knows about the key
            if grep -q "^${env_key}=" "$ENV_FILE"; then
                replace_line "$env_key" "$value"
                echo "  ✓ $env_key from secrets/api/$service_name"
            else
                echo "  ⚠ $env_key found in secrets/api/ but not in template (skipping)"
            fi
        fi
    done
fi

# Set any remaining API keys to NEED-API-KEY sentinel value
# This makes missing keys obvious (app will fail fast with clear error)
for key in OPENAI_API_KEY ANTHROPIC_API_KEY GROQ_API_KEY TOGETHER_API_KEY TAVILY_API_KEY; do
    if grep -q "^${key}=$" "$ENV_FILE" || grep -q "^${key}=NEED-API-KEY$" "$ENV_FILE"; then
        replace_line "$key" "NEED-API-KEY"
    fi
done

# =============================================================================
# Step 3: Generate Infrastructure Secrets (Cached)
# =============================================================================
# These are auto-generated once and persisted to secrets/infra/
# Why cache? So database passwords don't change between `make dev` runs

echo "Ensuring infrastructure secrets..."

DB_PASSWORD=$(ensure_secret "$SECRETS_DIR/db-password" "random_ascii")
REDIS_PASSWORD=$(ensure_secret "$SECRETS_DIR/redis-password" "random_ascii")
NEO4J_PASSWORD=$(ensure_secret "$SECRETS_DIR/neo4j-password" "random_ascii")
MINIO_ACCESS_KEY=$(ensure_secret "$SECRETS_DIR/minio-access-key" "random_ascii")
MINIO_SECRET_KEY=$(ensure_secret "$SECRETS_DIR/minio-secret-key" "random_ascii")

# Replace in .env
replace_line "DATABASE_PASSWORD" "$DB_PASSWORD"
replace_line "REDIS_PASSWORD" "$REDIS_PASSWORD"
replace_line "NEO4J_PASSWORD" "$NEO4J_PASSWORD"
replace_line "MINIO_ACCESS_KEY" "$MINIO_ACCESS_KEY"
replace_line "MINIO_SECRET_KEY" "$MINIO_SECRET_KEY"

# =============================================================================
# Step 4: Generate Derived Connection Strings
# =============================================================================
# Build connection URLs from components (single source of truth)
# Format examples:
#   PostgreSQL: postgresql+asyncpg://user:pass@host:port/db
#   Redis: redis://:password@host:port

replace_line "DATABASE_URL" "postgresql+asyncpg://appuser:${DB_PASSWORD}@postgres:5432/appdb"
replace_line "REDIS_URL" "redis://:${REDIS_PASSWORD}@redis:6379"

# =============================================================================
# Step 5: Validate Required Variables
# =============================================================================
# Extract all ${VAR} references from docker-compose.yml
# Ensure each one exists in .env (catch missing config early)

missing_vars=()
required_vars=$(grep -o '\${[A-Z0-9_]*}' docker-compose.yml 2>/dev/null \
    | tr -d '${}' \
    | sort -u \
    | grep -v '^CONVERSATION_MODEL$' \
    | grep -v '^CONVERSATION_MODELS$' \
    || true)
for var in $required_vars; do
    if ! grep -q "^$var=" "$ENV_FILE"; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "Warning: Missing environment variables:"
    printf '  - %s\n' "${missing_vars[@]}"
fi

echo ".env generated successfully from template"