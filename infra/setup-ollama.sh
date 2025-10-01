#!/bin/bash
# =============================================================================
# Ollama Model Initialization Script
# =============================================================================
# This script pulls LLM models into the Ollama container
#
# Pattern: On-demand initialization (NOT run automatically)
#   1. User runs: make ollama-setup (after stack is running)
#   2. Script executes inside running ollama container (docker exec)
#   3. Parses OLLAMA_PULL_MODELS from .env (comma-separated list)
#   4. Pulls each model using `ollama pull` (can take minutes per model)
#
# Why not automatic?
#   - Models are LARGE (1GB - 70GB each)
#   - Slow to download (minutes to hours)
#   - Optional (not required for API-based LLM usage)
#   - User should explicitly opt-in
#
# Model format: <name>:<tag>
#   Examples: llama3.2:1b, mistral:latest, codellama:13b
#   See: https://ollama.com/library for available models
#
# Where models are stored:
#   - Container: /root/.ollama/models
#   - Host: ollama_models Docker volume (persists across restarts)

set -euo pipefail

echo "Setting up Ollama models..."

# =============================================================================
# Wait for Ollama API Readiness
# =============================================================================
# Ollama healthcheck confirms process is running, but API might not be ready
echo "Verifying Ollama API is ready..."
until curl -f http://ollama:11434/api/version >/dev/null 2>&1; do
    echo "Waiting for Ollama API..."
    sleep 2
done
echo "Ollama API ready"

# =============================================================================
# Pull Models from Environment Variable
# =============================================================================
# OLLAMA_PULL_MODELS format: "model1:tag,model2:tag,model3:tag"
# Example: "llama3.2:1b,nomic-embed-text"

if [ -n "${OLLAMA_PULL_MODELS:-}" ]; then
    echo "Pulling models: $OLLAMA_PULL_MODELS"
    
    # Split comma-separated list into array
    IFS=',' read -ra MODELS <<< "$OLLAMA_PULL_MODELS"
    
    for model in "${MODELS[@]}"; do
        # Trim whitespace
        model=$(echo "$model" | xargs)
        
        echo "----------------------------------------"
        echo "Pulling model: $model"
        echo "This may take several minutes..."
        echo "----------------------------------------"
        
        # Pull model (or skip if pull fails)
        if ollama pull "$model"; then
            echo "✅ Successfully pulled: $model"
        else
            echo "⚠️  Failed to pull: $model (continuing with next model)"
        fi
    done
    
    echo "=========================================="
    echo "Ollama setup complete!"
    ollama list  # Show all installed models
else
    echo "No models specified in OLLAMA_PULL_MODELS"
    echo "Edit .env or secrets/env-template.txt to add models"
    echo "Example: OLLAMA_PULL_MODELS=llama3.2:1b,mistral:latest"
fi