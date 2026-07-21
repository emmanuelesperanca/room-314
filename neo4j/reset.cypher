// =============================================================================
// Room 314 — DEVELOPMENT reset
// Deletes ALL nodes and relationships in the current database.
// Use ONLY in the dedicated `room314` dev database. Never in production.
// After running this, re-run constraints.cypher (safe) and seed.cypher.
// =============================================================================

MATCH (n) DETACH DELETE n;
