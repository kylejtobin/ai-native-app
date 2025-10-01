# Documentation Strategy

**How to maintain "architecture as curriculum" as the codebase evolves**

This repository's documentation isn't just reference material—it's a teaching system. When you add functionality, you're not just documenting what you did; you're teaching why, when, and when not to do it.

This guide explains how to maintain that teaching mission.

---

## The Three-Layer Update Pattern

When adding functionality, update docs in this order:

```
1. Technical Doc (detailed patterns, examples, anti-patterns)
   ↓
2. Guide (navigation, "I want to..." scenarios)
   ↓
3. README (awareness only if architecturally significant)
```

**Example:** Adding MongoDB for document storage

1. **First:** Update `docs/infra/systems.md` with MongoDB section, decision criteria, anti-patterns
2. **Second:** Update `docs/infra/guide.md` to link from "I want to add a new database"
3. **Third:** Update `docs/infra/iac.md` and `orchestration.md` with Docker/health check details
4. **Last (maybe):** Update README only if it's a paradigm shift (usually: skip)

---

## Workflow by Feature Type

### Adding Infrastructure (new database, cache, service)

**Files to update:**

1. **`docs/infra/systems.md`** ← Primary
   - Add to systems table with "Why this system?" section
   - Update "Decision Framework" with when to use it
   - Add anti-patterns specific to this system
   - Use real config examples from your Docker Compose

2. **`docs/infra/iac.md`**
   - Add Docker Compose declaration
   - Explain volume mounts, networks
   - Show the "declarative" principle in action

3. **`docs/infra/orchestration.md`**
   - Add health check configuration
   - Document startup dependencies
   - Add to "The Full Startup Sequence" section

4. **`docs/infra/guide.md`**
   - Add link from "I want to add a new database"
   - Create new scenario if it's a new category

5. **`README.md`** (only if major)
   - Update systems table if introducing new category
   - Otherwise: skip (guide handles navigation)

### Adding App Functionality (new domain model, LLM pattern, API endpoint)

**Files to update:**

1. **Relevant `docs/app/*.md`** ← Primary
   - `type-system.md` - For new type patterns
   - `domain-models.md` - For new domain models/aggregates
   - `immutability.md` - For state management patterns
   - `service-patterns.md` - For orchestration logic
   - `llm-integration.md` - For LLM/AI patterns
   - `data-flow.md` - For request/response flows

   **What to add:**
   - Real code example from the repo (never pseudocode)
   - Update decision framework with when to use this pattern
   - Add anti-patterns (what NOT to do)
   - Link to principle in `philosophy.md`

2. **`docs/app/guide.md`**
   - Add to relevant "I want to..." section
   - Link to the new pattern in technical docs
   - Create new scenario if needed

3. **`README.md`** (only if paradigm-shifting)
   - Example: Adding streaming responses → might update architecture overview
   - Example: Adding new domain model → skip (not significant enough)

### Adding Developer Tooling (Make targets, scripts, workflows)

**Files to update:**

1. **`docs/development.md`** ← Primary
   - Add command with explanation of what it does
   - Connect to architectural principle (why this workflow?)
   - Show real example from your workflow

2. **`Makefile`** (if adding Make target)
   - Add inline comments explaining the "why"

3. **`README.md`** (only if changes quick start)
   - Example: New `make deploy` → might update "Getting Started"
   - Example: New `make test-unit` → skip (development.md handles it)

---

## Golden Rules

### ✅ DO

- **Always use real code examples** from the repository
  - Quote actual file paths with line numbers
  - Copy-paste real code, not pseudocode
  - Example: "See `src/app/domain/conversation.py:45-60`"

- **Update principle boxes** when extending or challenging a principle
  - If you're doing something that seems to violate a principle, explain why
  - Example: Mutable cache in an immutable system → explain the boundary

- **Add to decision frameworks** when introducing choices
  - Don't just say "use X" - say "use X when Y, but use Z when W"
  - Give criteria, not mandates

- **Add anti-patterns** when you learn what NOT to do
  - "DON'T use X because Y" is often more valuable than "DO use X"
  - Anti-patterns are guardrails for both humans and AI

- **Update guides for navigation** (don't duplicate content)
  - Guides are "I want to..." → "Go here"
  - Don't copy the technical details into the guide

- **Link bidirectionally**
  - If A mentions B, B should link back to A
  - Example: `llm-integration.md` mentions Pydantic models → link to `type-system.md`
  - And `type-system.md` should mention LLM integration → link back

### ❌ DON'T

- **Don't update README** for every small change
  - README is the entry point, not a changelog
  - Only update for major architectural shifts
  - Let guides and technical docs handle the details

- **Don't duplicate content** between docs
  - Each piece of information should live in ONE place
  - Use links to connect related concepts
  - Exception: Principle boxes can appear in multiple docs (they link to `philosophy.md`)

- **Don't skip the "why"**
  - Every pattern needs principle grounding
  - "Because it works" isn't enough - "Because it enforces immutability" is

- **Don't orphan new docs**
  - Every doc must be linked from somewhere
  - Usually from a `guide.md` file
  - Check: Can someone find this doc by following links from README?

- **Don't forget `philosophy.md`**
  - If you're introducing a new core principle (rare), update it
  - Most changes won't need this (philosophy evolves slowly)

- **Don't create new top-level docs without justification**
  - We have a deliberate structure: philosophy, install, development, app/, infra/
  - If you need a new doc, ask: where does it fit in the hierarchy?

---

## The "Semantic Density" Test

Before committing documentation, ask:

> **"Could an AI read this and understand not just WHAT to do, but WHY, WHEN, and WHEN NOT?"**

If the answer is no, you're missing:
- **Principle boxes** - Connect to the "why"
- **Decision frameworks** - Provide the "when"
- **Anti-patterns** - Teach the "when not"

**Example of low semantic density:**
```markdown
## Caching

Use Redis for caching. Configure TTL appropriately.
```

**Example of high semantic density:**
```markdown
## Caching with Redis

### Why Redis?

We use Redis for caching (not Memcached) because we need:
- Persistence (disk snapshots for cache warm-up after restart)
- Rich data structures (sorted sets for time-based eviction)
- Pub/sub (for cache invalidation across instances)

See [systems.md](infra/systems.md#redis) for the full decision criteria.

### Decision Framework: What to Cache

**Cache when:**
- Data is expensive to compute (>100ms)
- Data is read frequently (>10x writes)
- Stale data is acceptable (eventual consistency OK)

**Don't cache when:**
- Data must be immediately consistent
- Data is unique per request (e.g., user sessions → use Redis as primary store)
- Storage cost > compute cost

### Anti-Patterns

**DON'T:**
- ❌ Cache without TTL (leads to stale data, memory leaks)
- ❌ Cache mutable objects (violates immutability principle)
- ❌ Use cache as primary data store (unless explicitly designed for it)
- ❌ Cache before measuring (premature optimization)

**DO:**
- ✅ Set explicit TTL on every key
- ✅ Cache serialized immutable snapshots
- ✅ Use cache for derived/computed data only
- ✅ Monitor cache hit rates before adding more
```

---

## Documentation Hierarchy

```
README.md                    ← Entry point, philosophy overview, quick start
  ↓
philosophy.md                ← The "why" (rarely changes)
  ↓
install.md                   ← First run, verification (rarely changes)
development.md               ← Daily workflow (evolves slowly)
  ↓
app/guide.md                 ← "I want to..." navigation
infra/guide.md               ← "I want to..." navigation
  ↓
Technical Docs               ← The details (change frequently)
├── app/
│   ├── type-system.md       ← Type patterns, decision frameworks, anti-patterns
│   ├── domain-models.md     ← Rich models, aggregates, real examples
│   ├── immutability.md      ← State management, frozen models
│   ├── service-patterns.md  ← Orchestration, thin services
│   ├── llm-integration.md   ← Two-phase routing, tools, structured output
│   ├── data-flow.md         ← Request/response cycles
│   ├── conversation-system.md ← Conversation aggregate details
│   └── testing.md           ← Test patterns (future)
└── infra/
    ├── systems.md           ← Why each database, decision criteria
    ├── iac.md               ← Docker, Compose, declarative infra
    ├── orchestration.md     ← Startup order, health checks, dependencies
    └── configuration.md     ← Secrets, env vars, type-safe config
```

### Update Frequency

- **Technical docs:** Every relevant commit (new pattern → document it)
- **Guides:** When adding new scenarios or major patterns
- **README/install/development:** Only for significant workflow changes
- **Philosophy:** Rarely (only when core principles evolve)

---

## The "AI-Native" Lens

This repository is designed for **AI comprehension and teaching**, not just human reference.

When adding documentation, ask:

1. **Is the decision encoded?**
   - "We chose X because Y" (not just "use X")

2. **Are alternatives shown?**
   - "We considered X, Y, Z. Chose Y because..." (shows decision process)

3. **Are guardrails provided?**
   - Anti-patterns, failure modes, common mistakes

4. **Is it linked to principles?**
   - Connect to `philosophy.md` to show how this embodies the architecture

**Why this matters:**
- **Humans** learn from principles, examples, and anti-patterns
- **AI** needs the same structure to understand semantics, not just syntax
- **Future you** will thank yourself for explaining the "why"

---

## Practical Checklist

When adding a feature, before you commit:

**For code changes:**
- [ ] Updated relevant technical doc with real code example
- [ ] Added to decision framework (when to use this pattern)
- [ ] Added anti-patterns (when NOT to use this)
- [ ] Linked to principle in `philosophy.md` (if new pattern)
- [ ] Updated guide.md with navigation link
- [ ] Checked bidirectional links (A→B, B→A)
- [ ] Ran "semantic density" test (WHY, WHEN, WHEN NOT?)

**For infrastructure changes:**
- [ ] Updated `systems.md` with why this system
- [ ] Updated `iac.md` with Docker declaration
- [ ] Updated `orchestration.md` with health checks
- [ ] Updated `infra/guide.md` with navigation
- [ ] Updated README only if paradigm-shifting (usually skip)

**For every doc change:**
- [ ] Used real code examples (not pseudocode)
- [ ] Added principle boxes where relevant
- [ ] Added decision frameworks for new choices
- [ ] Added anti-patterns for common mistakes
- [ ] No orphaned docs (linked from somewhere)
- [ ] No duplicate content (link instead)

---

## Examples

### Good: Adding Vector Search

**Technical doc (`infra/systems.md`):**
```markdown
### Qdrant (Vector Search)

**What:** Purpose-built vector database for semantic similarity search

**Why Qdrant (not Pinecone, Weaviate, or pgvector):**
- Self-hosted (no vendor lock-in, data stays local)
- Fast HNSW indexing (millisecond similarity search)
- Rich filtering (combine semantic + metadata filters)
- gRPC API (low-latency for real-time apps)

**When to use:**
- Semantic search over documents, images, audio
- Recommendation systems (find similar items)
- RAG (Retrieval-Augmented Generation) for LLMs

**Anti-patterns:**
- ❌ DON'T use for exact text search → use PostgreSQL full-text
- ❌ DON'T use for relational queries → use PostgreSQL
- ❌ DON'T store large objects → use MinIO, store embeddings only
```

**Guide (`infra/guide.md`):**
```markdown
### I want to add semantic search

→ See [Qdrant configuration](systems.md#qdrant-vector-search) for:
- When to use vector search vs. full-text search
- How to generate embeddings
- How to structure collections
```

**README:** (no update needed - guide handles it)

### Bad: Vague Documentation

```markdown
## Caching

Use Redis. Set TTL. Don't cache everything.
```

**Problems:**
- No "why" (why Redis? why TTL?)
- No "when" (when should I cache? when shouldn't I?)
- No "when not" (what are the anti-patterns?)
- No links (where can I learn more?)
- Not AI-comprehensible (no semantic structure)

---

## Philosophy Connection

This documentation strategy embodies the same principles as the code:

- **Explicitness** → Document decisions, not just outcomes
- **Semantic Richness** → Teach WHY, WHEN, WHEN NOT (not just WHAT)
- **Type Safety** → Structure docs like types (principle boxes, frameworks, anti-patterns)
- **Immutability** → Link to stable concepts, don't duplicate
- **Teaching Mission** → Every change is a teaching moment

For the philosophical foundation, see [`philosophy.md`](philosophy.md).

---

## Questions?

If you're unsure whether to update docs:

1. **Ask:** "Would someone adding a similar feature need to know this?"
   - Yes → Document it
   - No → Skip it

2. **Ask:** "Does this change how someone would use the system?"
   - Yes → Update guide.md
   - No → Only update technical doc

3. **Ask:** "Does this change the architecture's philosophy?"
   - Yes → Update philosophy.md (rare)
   - No → Link to existing principles

**When in doubt:** Over-document with examples and anti-patterns. It's easier to prune than to reconstruct lost knowledge.

