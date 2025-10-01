#!/bin/bash
# =============================================================================
# MinIO Initialization Script
# =============================================================================
# This script runs ONCE via the minio_setup container in docker-compose.yml
#
# Pattern: One-time setup container (same pattern as Neo4j setup)
#   1. Waits for MinIO to be healthy (healthcheck in docker-compose)
#   2. Configures mc (MinIO Client) with credentials
#   3. Creates buckets (organized object storage namespaces)
#   4. Sets bucket policies (public/private, versioning, lifecycle)
#   5. Exits (container state: service_completed_successfully)
#
# Why buckets?
#   - Logical separation (documents vs models vs reports)
#   - Different access policies per bucket
#   - S3-compatible organization (familiar mental model)
#
# MinIO Client (mc):
#   - CLI tool for MinIO/S3 operations
#   - Simpler than boto3 for setup scripts
#   - Installed in minio/mc Docker image

set -e

echo "Setting up MinIO buckets..."

# =============================================================================
# Configure MinIO Client Alias
# =============================================================================
# Create named alias "an-app" pointing to our MinIO instance
# All subsequent `mc` commands use this alias
mc alias set an-app http://minio:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"

# =============================================================================
# Verify MinIO Readiness
# =============================================================================
# Double-check MinIO is actually ready (belt and suspenders with healthcheck)
if ! mc admin info an-app > /dev/null 2>&1; then
    echo "❌ MinIO not ready (healthcheck passed but admin info failed)"
    echo "This should not happen - check MinIO container logs"
    exit 1
fi

# =============================================================================
# Create Buckets (Idempotent)
# =============================================================================
# --ignore-existing: Safe to re-run, won't fail if bucket exists
echo "Creating buckets (organized object storage namespaces)..."

# Bucket: documents
# Use for: PDFs, transcripts, business documents, user uploads
mc mb an-app/documents --ignore-existing

# Bucket: models
# Use for: LLM fine-tunes, embeddings, model artifacts, checkpoints
mc mb an-app/models --ignore-existing

# Bucket: reports
# Use for: Generated reports, analytics exports, visualizations
mc mb an-app/reports --ignore-existing

# =============================================================================
# Set Bucket Policies
# =============================================================================
# Development mode: Public read access (no auth required)
# Production: Change to 'download' or use IAM policies for fine-grained control
echo "Setting bucket policies (public read for development)..."
mc anonymous set public an-app/documents
mc anonymous set public an-app/models
mc anonymous set public an-app/reports

echo "✅ MinIO setup completed successfully"
echo "   Buckets: an-app/{documents,models,reports}"
echo "   Access: Public read (development mode)"
