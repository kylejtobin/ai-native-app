---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Planning documents from `specs/[###-feature-name]/`
**Prerequisites**: spec.md (requirements), plan.md (architecture)

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

**This project uses domain-centric architecture:**

- **Domain models**: `src/app/domain/[context]/`
  - `value.py` - Value objects (IDs, typed primitives)
  - `type.py` - Smart enums with behavior
  - `[aggregate].py` - Rich domain models (frozen=True)
  - `event.py` - Domain events
  - `repository.py` - Repository protocol + implementation
- **Infrastructure adapters**: `src/app/service/[context].py`
- **HTTP layer**: `src/app/api/[context]/routes.py`
- **Tests**: `tests/unit/[context]/`, `tests/integration/[context]/`

**Pattern Reminders:**
- ✅ All domain models MUST be `frozen=True`
- ✅ Use discriminated unions for outcomes (not booleans/exceptions)
- ✅ Wrap all primitives in value objects
- ✅ Add Logfire spans to all repository operations
- ✅ Reference pattern docs: `docs/architecture/pattern/`

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  When creating tasks.md for a real feature, replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Domain design from plan.md (value objects, enums, aggregates, events)
  - File structure from plan.md

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create domain directory structure per plan.md
- [ ] T002 Add any new dependencies to pyproject.toml (if needed)
- [ ] T003 [P] Verify linting and formatting passes (ruff check, ruff format)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

**Typical foundational tasks** (adjust based on plan.md):

- [ ] T004 Create domain directory structure at `src/app/domain/[context]/`
- [ ] T005 [P] Setup repository infrastructure (if new storage type needed)
- [ ] T006 [P] Add domain context to Settings for client factories
- [ ] T007 [P] Create base value objects that all stories depend on
- [ ] T008 [P] Create smart enums used across multiple aggregates
- [ ] T009 Configure Logfire instrumentation for this domain

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T010 [P] [US1] Unit tests for domain models in `tests/unit/[context]/test_[aggregate].py`
- [ ] T011 [P] [US1] Repository tests in `tests/unit/[context]/test_repository.py`
- [ ] T012 [P] [US1] Integration test for full workflow in `tests/integration/[context]/test_[context]_service.py`

### Implementation for User Story 1 (Three-Layer Pattern)

**Domain Layer** (business logic):
- [ ] T013 [P] [US1] Create value objects in `src/app/domain/[context]/value.py`
  - Pattern: `RootModel[UUID]` for IDs, Field validators for typed primitives
  - Reminder: `frozen=True` required
- [ ] T014 [P] [US1] Create smart enums in `src/app/domain/[context]/type.py`
  - Pattern: StrEnum with behavior methods (e.g., `can_transition_to()`)
- [ ] T015 [US1] Create [Aggregate] model in `src/app/domain/[context]/[aggregate].py`
  - Pattern: Pydantic BaseModel, `frozen=True`, business logic methods
  - Reminder: Methods return new instances via `model_copy(update={...})`
  - Reminder: Outcomes use discriminated unions (not bool/exceptions)
- [ ] T016 [US1] Create domain events in `src/app/domain/[context]/event.py`
  - Pattern: Inherit from EventBase, specify category/retention
- [ ] T017 [US1] Create repository protocol in `src/app/domain/[context]/repository.py`
  - Pattern: Protocol class defining operations
  - Reminder: All methods must have Logfire spans

**Service Layer** (orchestration):
- [ ] T018 [US1] Implement repository in `src/app/domain/[context]/repository.py`
  - Pattern: Takes client from Settings, wraps operations in Logfire spans
  - Reminder: Follow pattern from `docs/architecture/pattern/app-repo-*.md`
- [ ] T019 [US1] Create infrastructure adapter in `src/app/service/[context].py`
  - Pattern: Gets clients from Settings, creates repositories per request
  - Pattern: Load → Domain.method() → Save (orchestration only)
  - Reminder: NO business logic in service layer

**API Layer** (HTTP adapter):
- [ ] T020 [US1] Add HTTP routes in `src/app/api/[context]/routes.py`
  - Pattern: Parse request → delegate to service → return response
  - Reminder: Ultra-thin, no business logic

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (OPTIONAL - only if tests requested) ⚠️

- [ ] T021 [P] [US2] Unit tests for new domain models in `tests/unit/[context]/test_[aggregate].py`
- [ ] T022 [P] [US2] Integration test in `tests/integration/[context]/test_[context]_service.py`

### Implementation for User Story 2

**Domain Layer**:
- [ ] T023 [P] [US2] Add new value objects to `src/app/domain/[context]/value.py` (if needed)
- [ ] T024 [P] [US2] Add new enums to `src/app/domain/[context]/type.py` (if needed)
- [ ] T025 [US2] Extend [Aggregate] model in `src/app/domain/[context]/[aggregate].py`
  - Pattern: Add new methods, ensure `frozen=True`, return new instances
- [ ] T026 [US2] Add new domain events to `src/app/domain/[context]/event.py` (if needed)

**Service Layer**:
- [ ] T027 [US2] Extend repository operations in `src/app/domain/[context]/repository.py`
- [ ] T028 [US2] Extend infrastructure adapter in `src/app/service/[context].py`

**API Layer**:
- [ ] T029 [US2] Add new routes to `src/app/api/[context]/routes.py`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 3 (OPTIONAL - only if tests requested) ⚠️

- [ ] T030 [P] [US3] Unit tests in `tests/unit/[context]/test_[aggregate].py`
- [ ] T031 [P] [US3] Integration test in `tests/integration/[context]/test_[context]_service.py`

### Implementation for User Story 3

**Follow same three-layer pattern as US1/US2**:
- [ ] T032 [P] [US3] Domain layer changes in `src/app/domain/[context]/`
- [ ] T033 [US3] Service layer changes in `src/app/service/[context].py`
- [ ] T034 [US3] API layer changes in `src/app/api/[context]/routes.py`

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit tests (if requested) in tests/unit/
- [ ] TXXX Security hardening

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (if tests requested):
Task: "Unit tests in tests/unit/[context]/test_[aggregate].py"
Task: "Repository tests in tests/unit/[context]/test_repository.py"
Task: "Integration test in tests/integration/[context]/test_[context]_service.py"

# Launch independent domain layer files together:
Task: "Create value objects in src/app/domain/[context]/value.py"
Task: "Create smart enums in src/app/domain/[context]/type.py"
Task: "Create domain events in src/app/domain/[context]/event.py"

# These must come AFTER domain layer is done (dependencies):
Task: "Create [Aggregate] model in src/app/domain/[context]/[aggregate].py"
Task: "Create repository in src/app/domain/[context]/repository.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
