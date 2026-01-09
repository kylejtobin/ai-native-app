# Outcome-Focused Roadmapping

A strategic planning approach that separates commitment decisions from execution mechanics and treats measurement as empirical work, not predictive specification.

---

## The Problem This Solves

Organizations need to decide what capabilities to build, in what order, under resource constraints. Traditional roadmapping mixes three distinct concerns that operate at different abstraction levels and time horizons:

1. **Strategic commitment** - What capabilities should we pursue?
2. **Tactical execution** - How do we build chosen capabilities?
3. **Empirical measurement** - Did building this improve viability?

When these concerns mix:
- Strategic documents fill with implementation details (wrong abstraction level)
- Roadmaps include metrics that will slip (measurement pretending to be prediction)
- Execution starts before commitment clarity (premature refinement)
- Changes at one level force rewrites across all levels (coupling creates friction)

Outcome-focused roadmapping separates these concerns explicitly, allowing each to evolve at its natural cadence without forcing the others to change.

---

## Core Distinctions

### Strategic vs Tactical

**Strategic work** answers "what capabilities should exist?"
- High abstraction, low detail
- Long time horizon (months to years)
- Irreversible or expensive to reverse
- Requires divergent thinking (explore options)
- Different decision makers (product, executives)
- Changes slowly (quarterly)

**Tactical work** answers "how do we build this capability?"
- Low abstraction, high detail
- Short time horizon (days to weeks)
- Reversible through iteration
- Requires convergent thinking (execute chosen path)
- Different decision makers (engineers, designers)
- Changes frequently (daily)

**Why they can't mix:** Human cognition cannot simultaneously hold high abstraction (strategic context) and low abstraction (implementation details). Strategic thinking requires ignoring implementation complexity. Tactical thinking requires forgetting big picture to focus on specifics. Mixing them in the same document forces constant context switching and degrades both.

**Structural consequence:** Strategic commitments and tactical execution must be separate documents that reference each other but don't embed content from different abstraction levels.

### Outcomes vs Outputs

**Outcomes** describe capability state changes:
- "Users can process payments"
- "System can send transactional emails"
- Describes WHAT capability exists, not HOW it's built

**Outputs** describe deliverables:
- "Payment API with Stripe integration"
- "Email service using SendGrid"
- Describes HOW it's built, not WHAT it enables

**Why outcomes, not outputs:** Outputs commit to implementation before understanding requirements. Outcomes preserve flexibility - the capability "users can process payments" can be satisfied by multiple technical approaches. Commitment should be to capability (outcome), not implementation (output). Implementation decisions belong in tactical phase after strategic commitment.

### Outcomes vs Metrics

**Outcomes** describe desired state:
- "Users can view transaction history"
- Normative commitment about what to build
- Describes capability, not predicted value

**Metrics** quantify actual results:
- "Retention improved by 8%"
- Empirical observation after building
- Measures what actually happened

**Why outcomes, not metrics in roadmaps:** This requires understanding the value measurement problem.

---

## The Value Measurement Problem

Organizations optimize for "value" - their capacity to survive and thrive over time. But value cannot be directly measured in the present because viability is a future state. Every present-moment measurement is therefore a **proxy**: a current indicator believed to correlate with future viability.

### All Metrics Are Proxies

If value is future organizational viability, any metric measured today is a proxy bet:
- Current revenue correlates with future viability (probably)
- User retention correlates with future viability (probably)
- Feature usage correlates with future viability (probably)

The correlation is probabilistic, not certain. This creates the proxy problem.

### Slippage: Distance from Purpose

**Slippage** is the divergence between improving a metric and improving the value it proxies for. When slippage is low, optimizing the metric improves viability. When slippage is high, you can maximize the metric while destroying what it represents.

Example: "Lines of code written" initially correlates with progress (low slippage), but optimizing for it produces bloated unmaintainable code (high slippage). The metric decouples from the value it was meant to proxy.

### Why Slippage Emerges

Four intrinsic forces create slippage in any measurement system:

**1. Context Evolution**
- Organizational conditions change faster than metric definitions adapt
- What coupled to viability last quarter may not couple this quarter
- Metrics lag context because changing metrics has transaction costs

**2. Optimization Pressure**
- Resource allocation creates pressure to optimize metrics
- Organizations discover paths that improve metrics without improving value
- Gaming becomes economically rational when slippage exists

**3. Observer Effects**
- Measurement changes behavior being measured
- Actors shift focus to visible metrics, neglecting unmeasured dimensions
- This behavioral change alters metric-value correlation

**4. Temporal Mismatch**
- Strategic investments couple to viability over years
- Operational investments couple to viability over weeks
- Single-cadence measurement creates slippage for some investment types

These forces are **structural properties of organizational systems**, not design flaws. They cannot be eliminated through better metrics.

### Why Metrics Don't Belong in Roadmaps

Putting metrics in roadmaps creates three problems:

**1. False Precision**
Writing "Increase revenue by $50k" pretends you can predict the future value of something not yet built. You cannot. The number is a guess masquerading as a commitment.

**2. Gaming Bait**
Once a metric appears in a roadmap, optimization pressure targets that metric. Organizations will find ways to hit the number that may not improve actual viability (slippage exploitation).

**3. Premature Measurement**
Metrics are empirical discoveries made during/after execution, not predictions made during planning. Putting them in roadmaps reverses the information flow - specifying measurement before understanding coupling.

**What belongs in roadmaps:** Normative commitments about which capabilities to pursue. Not predictions about metrics those capabilities will move.

**What happens to measurement:** Separate work during/after execution. Build the capability, observe actual coupling to viability, detect slippage, evolve metrics as context changes. Measurement is **continuous empirical work**, not **upfront specification**.

---

## Three-Horizon Structure

Outcomes organize by time horizon based on refinement level and commitment strength:

### Later (6-12 months)
- **Exploratory** capabilities under consideration
- **High abstraction** - brief descriptions sufficient
- **Low commitment** - can deprioritize or abandon
- **Purpose**: Direction setting, option generation

### Next (3-6 months)
- **Directional** commitments gaining specificity
- **Medium abstraction** - state changes become clear
- **Medium commitment** - likely to pursue but can defer
- **Purpose**: Progressive refinement toward execution readiness

### Now (next 3 months)
- **Committed** work ready for tactical execution
- **Low abstraction** - enough detail to start planning
- **High commitment** - resources allocated, work begins
- **Purpose**: Active execution, flows into tactical planning

### Progressive Refinement

Outcomes slide Later → Next → Now as they gain refinement. This sliding is not automatic (time-based) but intentional (commitment-based):

**Later → Next**: When exploration reveals capability is desirable and feasible
- Add "state change" description (from X to Y)
- Clarify why this capability matters

**Next → Now**: When commitment strengthens and capacity exists
- Add "why now" justification
- Create tactical planning artifacts (specs, plans, tasks)

**Refinement is additive:** Outcome descriptions gain detail as they progress. Git history tracks evolution, showing how understanding developed.

---

## Structural Implementation

### File-Per-Outcome

Each outcome gets its own file (e.g., `outcomes/payment-processing.md`):

**Why separate files:**
- Outcomes evolve independently at different rates
- Git history tracks each outcome's evolution separately
- Parallel work on different outcomes doesn't create merge conflicts
- Outcomes can reference each other without circular embedding

**What's in an outcome file:**
- Title (stable, never changes)
- Description (evolves as outcome progresses through horizons)
- Optional fields added during refinement:
  - State change (Next horizon)
  - Why now (Now horizon)
  - Planning link (when tactical work begins)
  - Status (Exploring/Committed/In Progress/Shipped)

### Roadmap as Index

Roadmap file (`roadmap.md`) is an index organizing outcomes by horizon:

```markdown
## Now
- [Payment Processing](outcomes/payment-processing.md) - In Progress

## Next
- [Email Notifications](outcomes/email-notifications.md) - Committed

## Later
- [Transaction History](outcomes/transaction-history.md) - Exploring
```

**Why separation:**
- Roadmap changes frequently (reordering, horizon shifts)
- Outcome details change independently (refinement)
- Separation prevents roadmap edits from forcing outcome file changes
- Single source of truth for each concern

### Git as Evolution Tracker

Version control provides temporal dimension:

- Commits show when outcomes entered each horizon
- Diffs show how descriptions refined over time
- History reveals how long outcomes sat before commitment
- Blame shows who made refinement decisions

**No need for metadata fields** like "created date" or "last updated" - git provides this automatically.

---

## Decision Frameworks

### When to Add an Outcome

Add to **Later horizon** when:
- Capability is directionally desirable
- No commitment to build yet
- Exploring feasibility/value

Brief description sufficient. Don't invest in refinement until commitment strengthens.

### When to Move Later → Next

Move when:
- Exploration reveals capability is valuable AND feasible
- Rough understanding of what state change looks like
- Commitment strengthens from "maybe" to "probably"

Refinement work:
- Describe state change (from current state to desired state)
- Clarify value proposition
- Identify major unknowns

### When to Move Next → Now

Move when:
- Commitment solidifies to "will build"
- Capacity exists (people, time, dependencies satisfied)
- Ready to begin tactical planning

Refinement work:
- Add "why now" justification
- Create tactical planning directory
- Begin spec/plan/tasks development
- Link outcome to planning artifacts

### When to Remove from Roadmap

Remove when:
- **Shipped**: Capability exists, outcome achieved
- **Abandoned**: No longer pursuing, context changed
- **Superseded**: Different approach chosen

For shipped outcomes: Update status, remove from active roadmap, keep file for historical reference.

---

## Tactical Planning Interface

Only **Now horizon** outcomes flow into tactical planning. This is the boundary where strategic abstraction (outcomes) meets tactical detail (specs/plans/tasks).

### The Interface

Outcome file links to planning directory:
```markdown
**Planning**: → `planning/001-payment-processing/`
```

Planning directory contains:
```
planning/001-payment-processing/
├── spec.md      # Requirements (WHAT and WHY)
├── plan.md      # Architecture (HOW)
└── tasks.md     # Implementation (DO)
```

### Information Flow

Strategic → Tactical (one-way):
- Outcome description informs requirements
- State change defines success criteria
- Why now provides context

Tactical does not flow back to strategic:
- Implementation details don't belong in outcome files
- Technical decisions don't change strategic commitment
- Execution status tracked separately from strategic priority

### When Execution Starts

Create planning directory when outcome enters Now horizon. Copy templates, begin refinement. Outcome file links to planning but remains high-level. Detailed work happens in planning directory.

### When Execution Completes

Update outcome status to "Shipped". Delete planning directory (or archive). Outcome file remains as historical record. Next Now outcome flows into planning.

---

## Anti-Patterns

### Mixing Strategic and Tactical

**What it looks like:**
Roadmap contains implementation details:
- "Build payment API using Stripe with webhook handling"
- File paths and technical architecture in outcome descriptions
- Mixing "what capability" with "how to build"

**Why it fails:**
- Forces strategic document to change when implementation details change
- Premature commitment to approach before understanding requirements
- Couples abstraction levels that evolve at different rates

**Fix:** Keep outcomes at capability level. Technical decisions belong in tactical planning phase.

### Fake Quantification

**What it looks like:**
Outcomes include predicted metrics:
- "Increase revenue by $50k"
- "Improve retention by 10%"
- "Reduce support tickets by 30%"

**Why it fails:**
- Numbers are guesses pretending to be commitments
- Creates optimization pressure toward gaming
- Measurement is empirical work, not predictive specification
- Slippage will emerge as context evolves

**Fix:** Describe capabilities, not metrics. Measurement happens during/after execution as separate empirical work.

### Single Horizon

**What it looks like:**
Everything in one list:
- No Later/Next/Now separation
- All items equally detailed
- No progression through refinement stages

**Why it fails:**
- Can't distinguish exploration from commitment
- No signal about readiness for execution
- Forces premature refinement of exploratory ideas
- No capacity planning (everything looks equally urgent)

**Fix:** Separate horizons with different refinement levels. Only Now horizon flows into execution.

### Static Descriptions

**What it looks like:**
Outcomes written once, never refined:
- Same description from Later through Now
- No evolution visible in git history
- No state change or justification added

**Why it fails:**
- Misses progressive refinement benefit
- Forces all detail upfront (premature)
- Loses context about why prioritization changed
- No learning captured in outcome evolution

**Fix:** Treat outcome descriptions as living documents. Add detail as understanding grows. Git tracks evolution.

### Waterfall Refinement

**What it looks like:**
Fully refine all outcomes before any move to Now:
- Complete state changes for Later items
- Detailed justifications for everything
- Treating horizons as stages, not commitment levels

**Why it fails:**
- Wastes refinement effort on things that may never be built
- Context will change before Later items become relevant
- Refinement work has shelf life - details get stale

**Fix:** Refine just-in-time as outcomes approach Now. Minimal detail for Later, progressive refinement as commitment strengthens.

---

## Measurement as Separate Work

Roadmaps describe what to build. Measurement detects whether building it improved viability. These are separate activities with different timing and methods.

### During Execution

While building a capability:
- Observe what's working and what isn't
- Notice unexpected coupling (or lack of coupling) to viability
- Test hypotheses about what matters
- Collect empirical evidence

### After Shipping

Once capability exists:
- Did the state change happen as expected?
- How did behavior actually change?
- What metrics moved (and didn't move)?
- What does coupling pattern reveal about context?

### Progressive Discovery

Measurement is scientific process:
1. Hypothesize what might couple to viability
2. Measure candidate proxies
3. Test whether improving proxy improves value
4. Iterate based on evidence
5. Evolve metrics as slippage emerges

This happens in parallel with roadmapping but doesn't feed back into outcome descriptions. Outcomes describe commitments (normative). Measurement reveals coupling (empirical). These are different types of knowledge.

### When Measurement Influences Roadmap

Empirical learning can change strategic priorities:
- Feature we built didn't couple to viability → deprioritize similar features
- Unexpected coupling discovered → investigate related capabilities
- Context changed → reevaluate Later/Next priorities

But this flows through decision-making, not by putting metrics in outcome files. Learning informs decisions, but outcomes remain capability descriptions, not metric predictions.

---

## Implementation Guidance

### Starting From Scratch

1. Create `outcomes/` directory
2. Create `roadmap.md` with three horizon sections
3. Add current commitments as outcomes in Now horizon
4. Add exploratory ideas to Later horizon
5. Link Now outcomes to existing planning (if it exists)

### Adding a New Outcome

1. Create `outcomes/outcome-name.md`
2. Write brief capability description
3. Add to appropriate horizon in `roadmap.md`
4. Commit with message describing why considering this outcome

### Refining an Outcome

1. Edit `outcomes/outcome-name.md`
2. Add state change description (Next horizon)
3. Add why now justification (Now horizon)
4. Commit with message describing refinement reasoning

### Moving Between Horizons

1. Update horizon section in `roadmap.md`
2. Refine outcome file as appropriate for new horizon
3. If moving to Now: create planning directory
4. Commit with message describing commitment change

### Completing an Outcome

1. Update status in outcome file to "Shipped"
2. Remove from `roadmap.md` or move to archive section
3. Delete planning directory (work is in git history)
4. Commit with message describing completion

---

## Key Principles

### 1. Separation of Concerns

Strategic commitment, tactical execution, and empirical measurement are different activities operating at different abstraction levels and time scales. Keep them separate.

### 2. Progressive Refinement

Don't refine everything upfront. Add detail just-in-time as commitment strengthens. Later needs minimal detail, Now needs execution readiness.

### 3. Normative, Not Predictive

Outcomes are commitments about what to build, not predictions about metrics that will move. Measurement is empirical work, not upfront specification.

### 4. Evolution Through Git

Track outcome evolution through version control. Commits show refinement progression, diffs show understanding development, history provides context.

### 5. Capability Descriptions

Describe state changes (what capability exists), not implementation details (how it's built) or predicted metrics (what numbers will move).

### 6. Single Source of Truth

Each concern has one location:
- Strategic priority: `roadmap.md`
- Outcome details: `outcomes/*.md`
- Tactical planning: `planning/*/`
- Measurement: Separate from roadmapping entirely

### 7. One-Way Information Flow

Strategic informs tactical (outcomes → planning). Tactical doesn't embed in strategic (planning details stay in planning/). Learning informs decisions but doesn't become roadmap content.

---

## Why This Works

**For strategic clarity:**
- Outcomes remain at appropriate abstraction level
- Horizon structure makes commitment strength explicit
- Progressive refinement prevents premature detail

**For tactical execution:**
- Clean handoff from strategy to execution
- Now outcomes provide clear starting point
- Implementation decisions separate from strategic commitments

**For organizational learning:**
- Git history tracks how understanding evolved
- Outcome files show reasoning behind priorities
- Separation enables different concerns to evolve independently

**For measurement integrity:**
- Avoids fake precision of predicted metrics
- Treats measurement as empirical work with proper method
- Acknowledges value measurement challenges explicitly

**For human cognition:**
- Respects abstraction level constraints
- Enables strategic thinking without tactical overwhelm
- Enables tactical focus without strategic drift

The structure acknowledges fundamental constraints - temporal, epistemic, organizational - and works with them rather than pretending they don't exist.

