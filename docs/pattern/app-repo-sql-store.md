# SQL Store Repository Pattern

> **SQLModel as foundation. Add rich domain models when business logic warrants it.**

## Overview

SQL persistence uses **SQLModel** - Pydantic models that are also SQLAlchemy tables. This gives us full Pydantic ecosystem (Logfire!) while managing relational data.

**The decision:** Does this aggregate need business logic?
- **No** → SQLModel alone (simple)
- **Yes** → SQLModel + rich domain model + Repository (complex)

---

## SQLModel Foundation

SQLModel combines Pydantic validation with SQLAlchemy tables:

```python
from sqlmodel import SQLModel, Field
from uuid import UUID

# Import domain types - cross-domain composition
from ..clock import Instant
from ..security.type import RevocationReason

class TokenRevocation(SQLModel, table=True):
    """Simple aggregate - SQLModel IS the domain model.

    Uses smart enums and value objects directly!
    SQLModel serializes them correctly for both SQL and Pydantic.
    """
    __tablename__ = "token_revocations"

    token_id: UUID = Field(primary_key=True)
    subject_id: UUID = Field(index=True)
    revoked_at: Instant = Field(index=True)  # Rich time type
    reason: RevocationReason  # Smart enum with methods!
    revoked_by: UUID | None = None

    model_config = {"frozen": False}  # Mutable for SQLAlchemy

    # Can even have domain methods since this IS the domain model
    def is_user_initiated(self) -> bool:
        """Business logic using smart enum's methods."""
        return self.reason.is_user_action()
```

**Benefits:**
- ✅ Pydantic validation
- ✅ Logfire serialization
- ✅ SQLAlchemy ORM features
- ✅ One model, not three

**When this works:**
- Aggregate is mostly data
- No complex business logic
- Storage shape = domain shape

---

## Decision Tree

```
Does this aggregate have business logic methods?
├─ NO → Use SQLModel alone
│       Example: TokenRevocation (just data)
│
└─ YES → Does it use rich value objects?
         ├─ NO → SQLModel + methods might work
         │       Example: Simple validation/computed properties
         │
         └─ YES → Use separate domain model + Repository
                  Example: User with EmailAddress, authenticate()
```

---

## Pattern 1: Simple (SQLModel Alone)

When aggregate is primarily data with minimal logic:

```python
# domain/database/token.py
from sqlmodel import SQLModel, Field
from uuid import UUID
import logfire

# Cross-domain composition - import domain types
from ..clock import Instant
from ..security.type import RevocationReason

class TokenRevocation(SQLModel, table=True):
    """SQLModel IS the domain model - uses smart enums directly."""
    __tablename__ = "token_revocations"

    token_id: UUID = Field(primary_key=True)
    subject_id: UUID = Field(index=True)
    revoked_at: Instant = Field(index=True)  # Rich time type
    reason: RevocationReason  # Smart enum with methods!
    revoked_by: UUID | None = None

    # Domain method using smart enum
    def is_user_initiated(self) -> bool:
        return self.reason.is_user_action()

# Repository provides observability
class TokenRevocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, token_id: UUID) -> TokenRevocation | None:
        with logfire.span("repo.token_revocation.get", token_id=str(token_id)):
            stmt = select(TokenRevocation).where(TokenRevocation.token_id == token_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

    async def save(self, revocation: TokenRevocation) -> TokenRevocation:
        with logfire.span("repo.token_revocation.save"):
            self.session.add(revocation)
            await self.session.flush()
            return revocation
```

**No translation needed** - SQLModel is both storage and domain.

---

## Pattern 2: Complex (Domain Model + Repository)

When aggregate has business logic and uses value objects:

### Storage Layer (SQLModel)

```python
# domain/database/table.py
from sqlmodel import SQLModel, Field
from uuid import UUID

# Cross-domain composition - import domain types
from ..clock import Instant
from ..security.type import HashAlgorithm
from typing import Literal

class UserTable(SQLModel, table=True):
    """Storage model - uses domain types where appropriate."""
    __tablename__ = "users"

    # Complex value objects (EmailAddress) are flattened for SQL
    user_id: UUID = Field(primary_key=True)
    username: str = Field(unique=True, index=True)
    email_local: str = Field(index=True)
    email_domain: str = Field(index=True)
    is_active: bool = Field(index=True)
    created_at: Instant

    model_config = {"frozen": False}  # Mutable for SQLAlchemy

class UserCredentialTable(SQLModel, table=True):
    """Credential storage - uses smart enums."""
    __tablename__ = "user_credentials"

    user_id: UUID = Field(foreign_key="users.user_id", primary_key=True)
    password_hash: bytes
    algorithm: HashAlgorithm  # Smart enum with methods!
    credential_type: Literal["password"]  # Discriminator for future OAuth/SAML
    created_at: Instant
```

### Domain Layer (Rich Model)

```python
# domain/identity/user.py
from pydantic import BaseModel

class User(BaseModel):
    """Rich domain model - business logic lives here."""
    model_config = {"frozen": True}  # Immutable

    user_id: UserId  # Value object
    username: Username  # Value object
    email: EmailAddress  # Value object (local_part + domain)
    credential: UserCredential  # Value object
    is_active: bool

    def authenticate(self, verification_result: PasswordVerificationResult) -> UserAuthResult:
        """Business logic: determine auth outcome."""
        match verification_result:
            case PasswordMatched():
                if not self.is_active:
                    return UserDisabled(user=self)
                return ValidCredentials(user=self)
            case PasswordMismatch():
                return InvalidPassword()
            case HashCorrupted():
                return InvalidPassword()
```

### Repository (Translation Layer)

```python
# domain/database/user.py
import logfire
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class UserRepository:
    """Translates User ↔ UserTable."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def to_domain(self, user_row: UserTable, cred_row: UserCredentialTable) -> User:
        """Storage → Domain (construct value objects)."""
        return User(
            user_id=UserId(user_row.user_id),
            username=Username(user_row.username),
            email=EmailAddress(
                local_part=user_row.email_local,
                domain=user_row.email_domain
            ),
            credential=UserCredential(
                user_id=UserId(user_row.user_id),
                password_hash=PasswordHash(
                    algorithm=HashAlgorithm(cred_row.algorithm),
                    hash=cred_row.password_hash
                ),
                credential_type=cred_row.credential_type
            ),
            is_active=user_row.is_active
        )

    def to_storage(self, user: User) -> tuple[UserTable, UserCredentialTable]:
        """Domain → Storage (flatten value objects)."""
        user_table = UserTable(
            user_id=user.user_id.value,
            username=user.username.value,
            email_local=user.email.local_part,
            email_domain=user.email.domain,
            is_active=user.is_active,
            created_at=datetime.now(UTC)
        )

        cred_table = UserCredentialTable(
            user_id=user.user_id.value,
            password_hash=user.credential.password_hash.hash,
            algorithm=user.credential.password_hash.algorithm.value,
            credential_type=user.credential.credential_type,
            created_at=datetime.now(UTC)
        )

        return user_table, cred_table

    async def get_by_email(self, email: EmailAddress) -> User | None:
        with logfire.span(
            "repo.user.get_by_email",
            email_domain=email.domain
        ) as span:
            stmt = (
                select(UserTable, UserCredentialTable)
                .join(UserCredentialTable)
                .where(
                    UserTable.email_local == email.local_part,
                    UserTable.email_domain == email.domain
                )
            )
            result = await self.session.execute(stmt)
            row = result.one_or_none()

            if not row:
                span.set_attribute("found", False)
                return None

            span.set_attribute("found", True)
            return self.to_domain(row[0], row[1])

    async def save(self, user: User) -> User:
        with logfire.span(
            "repo.user.save",
            user_id=str(user.user_id.value)
        ):
            user_table, cred_table = self.to_storage(user)

            # Merge for upsert semantics
            self.session.add(user_table)
            await self.session.merge(cred_table)
            await self.session.flush()

            return user
```

---

## When to Use Which Pattern

### Use SQLModel Alone When:
- ✅ Aggregate is data-focused (revocations, audit logs, simple lookups)
- ✅ No business logic methods
- ✅ No rich value objects needed
- ✅ Storage shape matches domain shape

**Examples:**
- TokenRevocation
- TokenRotation (audit trail)
- ModuleAttestation (cryptographic signature)

### Use Domain Model + Repository When:
- ✅ Business logic methods (`authenticate()`, `cancel()`, `approve()`)
- ✅ Rich value objects (`EmailAddress`, `UserId`, `Money`)
- ✅ Complex validation rules
- ✅ State machine behavior

**Examples:**
- User (has `authenticate()`, uses `EmailAddress`)
- Module (has lifecycle methods, uses `ModuleVersion`)
- Order (has `cancel()`, uses `Money` value object)

---

## Migrations with Alembic

SQLModel works with Alembic for migrations:

```python
# alembic/env.py
from sqlmodel import SQLModel
from app.domain.database.table import *  # Import all SQLModel tables

target_metadata = SQLModel.metadata

# Alembic auto-generates migrations
alembic revision --autogenerate -m "Add user tables"
alembic upgrade head
```

---

## Service Usage

Services create sessions and pass repositories to domain:

```python
# service/auth.py
from sqlalchemy.ext.asyncio import async_sessionmaker

class AuthService:
    def __init__(self, settings: Settings, clock: ClockService):
        # Own DB infrastructure
        self.engine = settings.postgres_engine()
        self.session_factory = async_sessionmaker(self.engine)
        self.clock = clock
        self._crypto = CryptoAdapter(...)
        self.auth_service = DomainAuthService()

    async def login_user(self, email, password) -> LoginResult:
        """Create session → repo → delegate to domain."""
        async with self.session_factory() as session:
            try:
                repo = UserRepository(session)

                result = await self.auth_service.login_user(
                    email, password, repo, self.clock, self._crypto
                )

                await session.commit()
                return result
            except:
                await session.rollback()
                raise
```

---

## Key Principles

1. **SQLModel is foundation** - Use for all SQL tables (Pydantic everywhere!)
2. **Add complexity when needed** - Start simple, add domain model when business logic warrants
3. **Repository for observability** - Even simple models get repository for Logfire
4. **Value objects signal complexity** - If using `EmailAddress` not `str`, probably need domain model
5. **Business logic in domain** - Never in SQLModel tables
6. **Mutable storage, immutable domain** - SQLModel mutable (required), domain frozen (preferred)

---

## Anti-Patterns

**❌ Business logic in SQLModel:**
```python
class User(SQLModel, table=True):
    def authenticate(self, password):  # ❌ Business logic in storage model
        ...
```

**✅ Business logic in domain model:**
```python
class UserTable(SQLModel, table=True):
    pass  # Just storage

class User(BaseModel):  # Separate domain model
    model_config = {"frozen": True}
    def authenticate(self, verification_result):  # ✅ Business logic here
        ...
```

**❌ Skip repository for observability:**
```python
async def get_user(session):
    return await session.get(UserTable, user_id)  # ❌ No Logfire instrumentation
```

**✅ Always use repository:**
```python
async def get_user(repo: UserRepository):
    return await repo.get(user_id)  # ✅ Instrumented, testable
```

---

## Related Patterns

- **app-repo.md** - Generic repository pattern
- **app-service.md** - How services use repositories
- **app.md** - Rich domain model foundations
