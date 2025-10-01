// =============================================================================
// Neo4j Graph Database Initialization
// =============================================================================
// This Cypher script runs ONCE via setup-neo4j.sh when Neo4j first starts
//
// Purpose: Initialize graph schema, indexes, constraints
//
// Examples of what you might add here:
//   - Constraints: CREATE CONSTRAINT user_email IF NOT EXISTS FOR (u:User) REQUIRE u.email IS UNIQUE
//   - Indexes: CREATE INDEX user_name IF NOT EXISTS FOR (u:User) ON (u.name)
//   - Seed data: CREATE (:User {id: "admin", name: "Admin", role: "admin"})
//
// Neo4j Best Practices:
//   - Define unique constraints on ID fields
//   - Index frequently-queried properties
//   - Use meaningful relationship types (not just "RELATED_TO")
//   - Label nodes for query performance

// Health check - confirms Cypher execution works
RETURN "AI-Native App Neo4j initialized" as status;
