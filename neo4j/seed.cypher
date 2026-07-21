// =============================================================================
// Room 314 — NEKG canonical world seed
// Narrative Epistemic Knowledge Graph (NEKG).
// Idempotent: every node is MERGE-d by id. Safe to run multiple times.
// No APOC. Neo4j Community / Neo4j Desktop compatible.
//
// The seed encodes ONLY the shared, canonical world. Per-session mutable state
// (Player, Session, discovered evidence, Mara's psychological deltas) is created
// at runtime by the backend and is NEVER written here.
// =============================================================================

// -----------------------------------------------------------------------------
// 1. NPC — Mara Doyle. Initial psychological baseline lives on the canonical
//    node and is COPIED into each Session at start (world state is not mutated).
// -----------------------------------------------------------------------------
MERGE (mara:NPC {id: 'mara_doyle'})
SET mara.name = 'Mara Doyle',
    mara.age = 55,
    mara.role = 'Proprietária da Pensão Vesper',
    mara.persona = 'Pragmática, exausta, protetora dos hóspedes, culpada e assustada.',
    mara.trust = 35,
    mara.fear = 70,
    mara.guilt = 76,
    mara.sanity = 58,
    mara.occult_exposure = 64;

// -----------------------------------------------------------------------------
// 2. Locations
// -----------------------------------------------------------------------------
MERGE (reception:Location {id: 'reception'})
SET reception.name = 'Recepção',
    reception.description = 'A recepção da Pensão Vesper. A chuva castiga as janelas. Um relógio de parede parado, velas trêmulas e um livro de hóspedes aberto sobre o balcão. Mara observa você em silêncio.';

MERGE (corridor:Location {id: 'corridor'})
SET corridor.name = 'Corredor',
    corridor.description = 'O corredor do terceiro andar. O ar é frio e cheira a maresia. Ao fundo, a porta do quarto 314 — selada há dez anos — parece pulsar com uma luz fraca, azul-esverdeada.',
    corridor.locked = true;

MERGE (room314:Location {id: 'room_314'})
SET room314.name = 'Quarto 314',
    room314.description = 'O quarto 314. Não deve ser resolvido nesta investigação.',
    room314.sealed = true;

MERGE (reception)-[:LEADS_TO]->(corridor)
MERGE (corridor)-[:LEADS_TO]->(room314)
MERGE (mara)-[:AT]->(reception);

// -----------------------------------------------------------------------------
// 3. Items
// -----------------------------------------------------------------------------
MERGE (key:Item {id: 'corridor_key'})
SET key.name = 'Chave do corredor',
    key.description = 'Uma chave de ferro pesada, fria como o ar da noite. Abre o acesso ao corredor do terceiro andar.';

// -----------------------------------------------------------------------------
// 4. Evidence — discoverable observations. Discovery is PER-SESSION via
//    (:Player)-[:DISCOVERED]->(:Evidence); there is NO global mutable `discovered`.
// -----------------------------------------------------------------------------
MERGE (clock:Evidence {id: 'stopped_clock_0217'})
SET clock.name = 'Relógio parado às 02:17',
    clock.description = 'O relógio de parede da recepção parou exatamente às 02:17.';

MERGE (ledger:Evidence {id: 'guest_ledger_elian'})
SET ledger.name = 'Livro de hóspedes',
    ledger.description = 'Um livro de hóspedes com o nome "Elian Voss" parcialmente apagado.';

MERGE (doormark:Evidence {id: 'door_314_mark'})
SET doormark.name = 'Marca na porta 314',
    doormark.description = 'Um símbolo incomum, quase orgânico, gravado na porta do quarto 314.';

// -----------------------------------------------------------------------------
// 5. Facts — canonical truth. `canonical: true` cannot be altered by the LLM
//    or by normal gameplay. `spoiler_level` grades sensitivity (1 = public,
//    5 = deepest secret). The identity behind the figure is intentionally
//    NOT resolvable in this PoC.
// -----------------------------------------------------------------------------
MERGE (f_bell:Fact {id: 'bell_0217'})
SET f_bell.statement = 'O sino do farol tocou às 02:17.',
    f_bell.canonical = true, f_bell.spoiler_level = 1;

MERGE (f_awake:Fact {id: 'mara_awake_0217'})
SET f_awake.statement = 'Mara estava acordada na recepção às 02:17.',
    f_awake.canonical = true, f_awake.spoiler_level = 2;

MERGE (f_sealed:Fact {id: 'door_was_sealed'})
SET f_sealed.statement = 'O quarto 314 estava selado antes daquela noite.',
    f_sealed.canonical = true, f_sealed.spoiler_level = 2;

MERGE (f_light:Fact {id: 'figure_blue_green_light'})
SET f_light.statement = 'A figura carregava/emitia uma luz azul-esverdeada.',
    f_light.canonical = true, f_light.spoiler_level = 3;

MERGE (f_saw:Fact {id: 'mara_saw_figure'})
SET f_saw.statement = 'Mara viu uma figura entrar no quarto 314.',
    f_saw.canonical = true, f_saw.spoiler_level = 3;

// The deepest secret. No rule in the engine ever grants this to the player.
MERGE (f_allowed:Fact {id: 'mara_allowed_entry'})
SET f_allowed.statement = 'Mara não impediu a entrada da figura.',
    f_allowed.canonical = true, f_allowed.spoiler_level = 5;

MERGE (f_elian:Fact {id: 'elian_voss_disappearance'})
SET f_elian.statement = 'Elian Voss desapareceu ligado ao quarto 314 há dez anos.',
    f_elian.canonical = true, f_elian.spoiler_level = 2;

// -----------------------------------------------------------------------------
// 6. Event — what physically happened. Mara OBSERVED it (with fallible memory).
// -----------------------------------------------------------------------------
MERGE (e_entry:Event {id: 'entry_314_0217'})
SET e_entry.description = 'Uma figura entrou no quarto 314 às 02:17.',
    e_entry.canonical = true, e_entry.time = '02:17';

// -----------------------------------------------------------------------------
// 7. Hypothesis — non-canonical interpretation. Belief, not truth. Cannot be
//    promoted to canonical automatically.
// -----------------------------------------------------------------------------
MERGE (h_elian:Hypothesis {id: 'elian_identity_hypothesis'})
SET h_elian.statement = 'A figura pode estar ligada a Elian Voss.',
    h_elian.canonical = false;

// -----------------------------------------------------------------------------
// 8. Epistemic relations — the heart of the NEKG.
//    KNOWS: private knowledge (Mara knows a fact; knowing != revealing).
//    CONCEALS: deliberate hiding, with motive + reveal policy.
//    BELIEVES: interpretation of a non-canonical hypothesis.
//    OBSERVED: fallible sensory memory of an event.
// -----------------------------------------------------------------------------

// Mara privately KNOWS these canonical facts.
MERGE (mara)-[k1:KNOWS]->(f_bell)   SET k1.certainty = 0.95, k1.reveal_policy = 'if_evidence_clock';
MERGE (mara)-[k2:KNOWS]->(f_awake)  SET k2.certainty = 1.00, k2.reveal_policy = 'if_evidence_clock';
MERGE (mara)-[k3:KNOWS]->(f_sealed) SET k3.certainty = 0.90, k3.reveal_policy = 'if_asked';
MERGE (mara)-[k4:KNOWS]->(f_saw)    SET k4.certainty = 0.85, k4.reveal_policy = 'if_confronted';
MERGE (mara)-[k5:KNOWS]->(f_light)  SET k5.certainty = 0.80, k5.reveal_policy = 'if_confronted';
MERGE (mara)-[k6:KNOWS]->(f_elian)  SET k6.certainty = 0.70, k6.reveal_policy = 'if_evidence_ledger';
MERGE (mara)-[k7:KNOWS]->(f_allowed) SET k7.certainty = 1.00, k7.reveal_policy = 'never';

// Mara deliberately CONCEALS the sensitive facts. `never` = the buried secret.
MERGE (mara)-[c1:CONCEALS]->(f_awake)   SET c1.motive = 'medo de ser responsabilizada', c1.reveal_policy = 'if_evidence_clock';
MERGE (mara)-[c2:CONCEALS]->(f_saw)     SET c2.motive = 'culpa e medo',                 c2.reveal_policy = 'if_confronted';
MERGE (mara)-[c3:CONCEALS]->(f_light)   SET c3.motive = 'medo do sobrenatural',         c3.reveal_policy = 'if_confronted';
MERGE (mara)-[c4:CONCEALS]->(f_allowed) SET c4.motive = 'culpa esmagadora',             c4.reveal_policy = 'never';

// Mara BELIEVES a non-canonical hypothesis, with low certainty.
MERGE (mara)-[b1:BELIEVES]->(h_elian)
SET b1.certainty = 0.40, b1.source = 'intuição e o livro de hóspedes';
MERGE (h_elian)-[:CONCERNS]->(e_entry);

// Mara OBSERVED the entry event — high confidence, imperfect memory.
MERGE (mara)-[o1:OBSERVED]->(e_entry)
SET o1.confidence = 0.85,
    o1.memory_stability = 0.60,
    o1.sensory_detail = 'luz azul-esverdeada, passos molhados no corredor';

// -----------------------------------------------------------------------------
// 9. Evidence -> Fact support (weights indicate probative strength).
// -----------------------------------------------------------------------------
MERGE (clock)-[s1:SUPPORTS]->(f_bell)     SET s1.weight = 0.9;
MERGE (clock)-[s2:SUPPORTS]->(f_awake)    SET s2.weight = 0.6;
MERGE (ledger)-[s3:SUPPORTS]->(f_elian)   SET s3.weight = 0.9;
MERGE (doormark)-[s4:SUPPORTS]->(f_light) SET s4.weight = 0.5;
MERGE (doormark)-[s5:SUPPORTS]->(f_sealed) SET s5.weight = 0.5;

// Evidence physical placement in the world.
MERGE (clock)-[:AT]->(reception);
MERGE (ledger)-[:AT]->(reception);
MERGE (doormark)-[:AT]->(room314);

// -----------------------------------------------------------------------------
// 10. Rule catalogue — deterministic rules are IMPLEMENTED in Python
//     (rules_engine.py). These nodes exist purely for traceability/documentation
//     inside the graph. The engine, not the graph, decides state changes.
// -----------------------------------------------------------------------------
MERGE (r1:Rule {id: 'R1_EXAMINE_CLOCK'})   SET r1.description = 'Examinar relógio na recepção -> descobre stopped_clock_0217, conhece bell_0217.';
MERGE (r2:Rule {id: 'R2_EXAMINE_LEDGER'})  SET r2.description = 'Examinar livro na recepção -> descobre guest_ledger_elian, conhece elian_voss_disappearance.';
MERGE (r3:Rule {id: 'R3_ASK_314'})         SET r3.description = 'Perguntar sobre o 314; sem relógio Mara evade; com relógio pode admitir mara_awake_0217.';
MERGE (r4:Rule {id: 'R4_CONFRONT_MARA'})   SET r4.description = 'Confrontar com relógio + livro -> revela mara_saw_figure. Figura permanece sem identidade.';
MERGE (r5:Rule {id: 'R5_REQUEST_KEY'})     SET r5.description = 'Pedir a chave requer mara_saw_figure -> entrega corridor_key, libera corridor.';
MERGE (r6:Rule {id: 'R6_EXAMINE_DOOR'})    SET r6.description = 'Examinar porta requer corredor + chave -> door_314_mark e evento door_opens (fim).';
MERGE (r7:Rule {id: 'R7_FREE_TEXT'})       SET r7.description = 'Texto livre classificado em enum fechada; nunca gera ação livre.';
MERGE (r8:Rule {id: 'R8_AUTHORITY'})       SET r8.description = 'Somente o rule engine altera o Neo4j; a LLM só fornece linguagem.';

// =============================================================================
// End of seed. The canonical world is now in place.
// =============================================================================
