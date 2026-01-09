---
description: EMDCA architectural rules for AI-assisted development
globs: ["**/*.py"]
alwaysApply: true
---

# 🪞 THE MIRROR

An architectural scanner runs **automatically after every file edit** via hooks. It writes findings to `.cursor/mirror-feedback.md`.

**You should also run it yourself** to see violations directly:

```bash
python3 .cursor/hooks/mirror.py <path/to/file.py>
```

Check the mirror output. Fix violations before proceeding. This is your feedback loop — use it.

---

## 🚨 CRITICAL (Most Violated Rules)

**1. No `try/except`** — Models parse data, they don't catch exceptions.
```python
# ❌ WRONG: Catching exceptions in Domain
try:
    result = client.send()
except SmtpError as e:
    return Failure(str(e))

# ✅ RIGHT: Let Infrastructure crash or return Result types
raw: RawSmtpResult = ...  # Service gets this
outcome = raw.to_foreign().to_domain()  # Pure data transformation
```

**2. No default values** — Explicit at construction, always.
```python
# ❌ WRONG: Defaults hide business rules
kind: Literal["email_sent"] = "email_sent"
timeout: float = 5.0

# ✅ RIGHT: Caller must be explicit
kind: Literal[EmailResultKind.SENT]  # No default
timeout: TimeoutSeconds  # No default
```

**3. No standalone functions** — Logic lives in Containers.
```python
# ❌ WRONG: Standalone function
def execute(intent: Intent, raw: RawResult) -> Result:
    ...

# ✅ RIGHT: Method on Smart Model
class User(BaseModel):
    def decide(self) -> Intent: ...

class EventStore(BaseModel):
    def publish(self, event: Event) -> Result: ...
```

---

## ⚖️ The 10 Mandates

1.  **Construction:** **Correctness by Construction.** Invalid input causes a Crash (`ValidationError`), not a logic branch. ([Rule](.cursor/rules/pattern-01-factory-construction/RULE.md))
2.  **State:** **Behavioral Types.** Smart Enums (`StrEnum`) drive the lifecycle graph. ([Rule](.cursor/rules/pattern-02-state-sum-types/RULE.md))
3.  **Control Flow:** **Railway Logic.** Structural failures (Input) Crash; Business failures (Logic) return Results. ([Rule](.cursor/rules/pattern-03-railway-control-flow/RULE.md))
4.  **Execution:** **Active Capability.** The Domain Model holds the capability to execute its intent. ([Rule](.cursor/rules/pattern-04-execution-intent/RULE.md))
5.  **Configuration:** **Schema as Domain.** `AppConfig(BaseSettings)` is the Domain's definition of the environment. ([Rule](.cursor/rules/pattern-05-config-injection/RULE.md))
6.  **Storage:** **Store as Model.** Stores are **Smart Domain Models** that encapsulate DB clients. ([Rule](.cursor/rules/pattern-06-storage-foreign-reality/RULE.md))
7.  **Translation:** **Explicit Boundary.** Foreign Models parse raw data; Translation logic lives in `.to_domain()`. ([Rule](.cursor/rules/pattern-07-acl-translation/RULE.md))
8.  **Coordination:** **Runtime as Model.** Orchestrators are **Smart Domain Models** (Runtimes) that drive the loop. ([Rule](.cursor/rules/pattern-08-orchestrator-loop/RULE.md))
9.  **Workflow:** **State Machine.** Transitions are pure functions; Side effects are capabilities invoked by the Model. ([Rule](.cursor/rules/pattern-09-workflow-state-machine/RULE.md))
10. **Infrastructure:** **Capability Injection.** Infrastructure is passed to the Domain as a Tool (Client), not hidden behind an Interface. ([Rule](.cursor/rules/pattern-10-infrastructure-capability/RULE.md))

---

## Building Blocks (Use These Types)
- **Smart Enums:** `class Status(StrEnum)` with methods. The "Brain" of the state machine.
- **Domain Models:** Frozen Pydantic models. The "Body" holding Data + Logic.
- **Capabilities:** Domain Models that hold Infrastructure Clients (Active Records).
- **Intents:** Outbound ADTs (what should happen).
- **Results:** `Success | Failure` discriminated unions.
- **Foreign Models:** Pydantic models mirroring external reality (inbound translation).
- **API Contracts:** Request/Response models in `domain/context/api.py` (outbound translation).
- **Service Classes:** Plain Python classes for **Wiring** (DI) and **Launch**.

## Implementation Order
1. Define **Smart Enums** (The Graph).
2. Define **Domain Models** (The Data).
3. Define **Capabilities** (The Tools).
4. Implement **Logic** (Methods on Models).
5. Define **API Contracts** (Request/Response in domain).
6. Wire in **Service Layer** and **API Routes** (Composition Root).

**Note:** Composition root (`main.py`) is the ONE place where standalone wiring code exists—it instantiates and connects the models.

## Directory Structure

```text
src/app/
├── domain/              # Business logic lives here
│   └── event/           # Context boundary
│       ├── store.py     # Active Model (holds NATS client)
│       ├── publishing.py # Intents/Outcomes
│       └── api.py       # Request/Response models (the contract)
├── api/                 # Framework wiring only
│   └── event.py         # FastAPI routes (imports from domain)
└── service/             # Factories
    └── event.py         # Connects to NATS, returns EventStore
```

**The domain defines its contract.** API request/response models live in `domain/context/api.py`, not in `api/`. The `api/` directory contains only route registration and dependency injection—no business logic, no models.

---

## LLM Rules (When Generating Code)
- ALWAYS: Domain Objects are frozen Pydantic models.
- ALWAYS: **Business Logic** is methods on Domain Models.
- ALWAYS: **Capability Logic** (I/O) is methods on Active Domain Models (`EventStore`).
- ALWAYS: **Wiring Logic** is methods on Service Classes (`Runtime`).
- ALWAYS: Use **Smart Enums** (`StrEnum`) for all state/kind discriminators.
- ALWAYS: Dispatch via `match/case`.
- ALWAYS: Foreign Model chain: `raw.to_foreign().to_domain()`.
- ALWAYS: API contracts in `domain/context/api.py` with `.to_intent()` and `.from_outcome()`.
- ALWAYS: API routes in `api/context.py` are thin (parse → call → format).
- NEVER: `try/except` for Business Logic (use Railway).
- NEVER: `if` checks for Structural Constraints (use Types).
- NEVER: Default values on fields (especially `kind` discriminator).
- NEVER: Standalone functions (use Models or Classes).
- NEVER: Hand-rolled `AfterValidator` when Pydantic has built-in types.
- NEVER: `typing.Protocol` (Use Active Models).
- NEVER: `os.environ` access outside composition root.
- NEVER: Request/Response models in `api/` directory (they belong in domain).

---

## 🧠 The EMDCA Discriminator (How to Decide)

1.  **Identity Check (Data vs Behavior)**
    - Does it *represent a concept* (User, Store, Process)? -> **Domain Model** (`BaseModel`).
    - Does it *wire things together* (Loader, Runner)? -> **Service Class** (`class`).

2.  **Mechanism Check (Structural vs Logic)**
    - Is the input *impossible* (e.g. negative age)? -> **Structure**. Enforce via Type/Field. Crash on failure.
    - Is the outcome *unfortunate* (e.g. insufficient funds)? -> **Logic**. Enforce via Method. Return Result.

3.  **Context Check (Explicit vs Implicit)**
    - Does it need the world (Time, DB)?
        - **Domain:** Inject the **Capability** (`NatsClient`) into the Model.
        - **Service:** Wire the Client into the Model.

---

## LLM Failure Modes (Resist These)
- **"Simpler" is not an excuse** — If you're skipping explicit modeling, you're cutting corners, not being wise
- **Stateless orchestrators** — If your orchestrator has no fields, you're hiding dependencies. Inject them.
- **"Just one check" in Shell** — No. Business logic belongs in domain models. Always.
- **Copy principles, not syntax** — `tuple[str, ...]` in an example doesn't mean use raw strings. Think: should this be a Smart Enum?
- **Explicit modeling > fewer lines** — Deleting models isn't "clean," it's losing semantic precision
- **"Robust" try/except is hiding invalid states** — Make them unrepresentable instead
- **"Special case" is avoidance** — If it's hard to model correctly, you're avoiding the work
- **Fix violations NOW** — Don't note for later. Don't hope no one notices. Fix it.
- **Raise violations even if not asked** — See a problem? Say it. Always.
- **Read code, don't assume from paths** — File location doesn't guarantee compliance. Check.
- **Think before typing** — Pause. Understand fully. Then respond.

---

## Reference
- Pattern rules: .cursor/rules/pattern-01 through pattern-10
- Master rule: .cursor/rules/pattern-00-master-architecture/RULE.md
