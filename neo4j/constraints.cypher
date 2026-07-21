// =============================================================================
// Room 314 — NEKG constraints
// Neo4j Community / Neo4j Desktop compatible. No APOC required.
// Run this ONCE against the `room314` database before seed.cypher.
// =============================================================================

// Every node in the NEKG carries a unique `id`. These constraints guarantee
// idempotent MERGE seeding and safe per-session writes.

CREATE CONSTRAINT npc_id        IF NOT EXISTS FOR (n:NPC)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT player_id     IF NOT EXISTS FOR (n:Player)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT session_id    IF NOT EXISTS FOR (n:Session)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT location_id   IF NOT EXISTS FOR (n:Location)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT item_id       IF NOT EXISTS FOR (n:Item)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT evidence_id   IF NOT EXISTS FOR (n:Evidence)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT fact_id       IF NOT EXISTS FOR (n:Fact)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT event_id      IF NOT EXISTS FOR (n:Event)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT belief_id     IF NOT EXISTS FOR (n:Belief)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT secret_id     IF NOT EXISTS FOR (n:Secret)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT claim_id      IF NOT EXISTS FOR (n:Claim)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT hypothesis_id IF NOT EXISTS FOR (n:Hypothesis) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT rule_id       IF NOT EXISTS FOR (n:Rule)       REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT trace_id      IF NOT EXISTS FOR (n:Trace)      REQUIRE n.id IS UNIQUE;
