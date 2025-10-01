#!/bin/bash
# =============================================================================
# Neo4j Initialization Script
# =============================================================================
# This script runs ONCE via the neo4j_setup container in docker-compose.yml
#
# Pattern: One-time setup container
#   1. Waits for Neo4j to be healthy (healthcheck in docker-compose)
#   2. Waits for Cypher interface to accept queries (loop with cypher-shell)
#   3. Executes init.cypher to set up schema/indexes/constraints
#   4. Creates sentinel file (/data/.initialized) to prevent re-runs
#   5. Exits (container state: service_completed_successfully)
#
# Why this approach?
#   - Neo4j healthcheck only confirms HTTP is up, not Cypher readiness
#   - Cypher-shell provides precise control over initialization
#   - Idempotent: Safe to restart (checks sentinel file)
#   - Explicit: init.cypher is version-controlled and auditable

set -e

echo "Starting Neo4j initialization..."

# =============================================================================
# Idempotency Check - Skip if Already Initialized
# =============================================================================
# Sentinel file on Neo4j's data volume ensures we only run once
if [ -f "/data/.initialized" ]; then
    echo "Neo4j already initialized (sentinel file found)"
    exit 0
fi

# =============================================================================
# Parse Authentication
# =============================================================================
# NEO4J_AUTH format: "username/password" (from docker-compose environment)
IFS='/' read -r NEO4J_USER NEO4J_PASS <<< "${NEO4J_AUTH}"
ENDPOINT="${NEO4J_URI:-bolt://neo4j:7687}"

echo "Connecting to Neo4j at ${ENDPOINT}"

# =============================================================================
# Wait for Cypher Interface Readiness
# =============================================================================
# Healthcheck confirms HTTP, but Cypher might not be ready yet
# Loop until we can execute a simple RETURN query
echo "Waiting for Neo4j Cypher interface..."
until cypher-shell -a "$ENDPOINT" --username "$NEO4J_USER" --password "$NEO4J_PASS" "RETURN 1;" > /dev/null 2>&1; do
    echo "Neo4j Cypher not ready - waiting 5s..."
    sleep 5
done

echo "Neo4j Cypher interface ready"

# =============================================================================
# Execute Initialization Script
# =============================================================================
# Run init.cypher (constraints, indexes, seed data)
echo "Running initialization Cypher script..."
if cypher-shell -a "$ENDPOINT" --username "$NEO4J_USER" --password "$NEO4J_PASS" --file "/infra/init.cypher"; then
    echo "Neo4j initialization completed successfully"
    # Create sentinel file to prevent re-runs
    touch "/data/.initialized"
else
    echo "Neo4j initialization failed"
    exit 1
fi
