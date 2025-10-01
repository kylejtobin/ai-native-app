-- =============================================================================
-- PostgreSQL Database Initialization
-- =============================================================================
-- This script runs ONCE when the postgres container starts for the first time
-- Mounted via: ./infra/init-db.sql:/docker-entrypoint-initdb.d/init.sql
--
-- Purpose: Install PostgreSQL extensions for advanced features
--
-- Extensions Explained:
--   uuid-ossp: Generate UUIDs (v1, v4, v5) natively in SQL
--   pg_trgm:   Trigram-based fuzzy text search (similarity, LIKE '%pattern%')
--   unaccent:  Remove accents for case-insensitive search (café → cafe)
--
-- Why extensions?
--   - Keep logic in database when appropriate (UUIDs, text search)
--   - Better performance than application-level implementations
--   - Standard PostgreSQL features (not vendor lock-in)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS "unaccent";   -- Accent-insensitive search

SELECT 'AI-Native App database initialized with extensions' AS status;
