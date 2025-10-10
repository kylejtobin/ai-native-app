# API Layer Pattern (Thin Routes)

> **Routes are ultra-thin HTTP adapters that delegate to domain services**

## File Structure

```
src/
  api/
    auth/
      contracts.py    # Request models (LoginRequest, RegisterRequest)
      routes.py       # FastAPI router (login, register endpoints)
    health/
      routes.py       # Health check endpoints
    deps.py          # FastAPI dependencies (auth, services)

  domain/
    auth.py          # Domain service (AuthService)
    identity/        # Domain models (User, UserView)

  service/
    auth.py          # Infrastructure adapter (owns DB, clock, crypto)
```

**Key principle**: Routes are ultra-thin HTTP adapters in `api/` that parse requests and return domain results. All business logic lives in `domain/`.

---

## The Problem: Fat Routes

Traditional API design puts business logic in route handlers:

```python
# ❌ WRONG - Business logic in route handler
@router.post("/auth/login")
async def login(request: LoginRequest, db: Database):
    # Business logic in route handler!
    user = await db.query("SELECT * FROM users WHERE email = ?", request.email)

    if not user:
        raise HTTPException(404, "User not found")

    if not bcrypt.verify(request.password, user.password_hash):
        raise HTTPException(401, "Invalid password")

    token = jwt.encode({"sub": str(user.id)}, SECRET_KEY)

    return {"access_token": token, "user": user}
```

**Problems**:
- Business logic tied to HTTP layer
- Can't test auth without FastAPI
- Error handling mixed with business rules
- Violates separation of concerns
- No type-safe results (manual dict construction)

---

## The Solution: Thin Routes

Routes do exactly three things:

1. **Receive** - Parse HTTP request into domain value objects
2. **Delegate** - Call service method
3. **Return** - Return domain result (FastAPI auto-serializes)

```python
# ✅ CORRECT - Ultra-thin route
@router.post("/auth/login")
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResult:
    """Login endpoint - returns discriminated union."""
    # 1. Receive (FastAPI parses LoginRequest)
    # 2. Delegate (call domain service)
    result = await auth_service.login_user(
        email=request.email,
        password=request.password,
    )
    # 3. Return (FastAPI serializes LoginResult)
    return result
```

The route is **5 lines of logic**. No business rules. No error handling. Just delegation.

---

## The Pattern

### The Three-Layer Flow

Understanding API architecture requires understanding three layers:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: API Routes (api/)                                   │
│ ─────────────────────────────────────────────────────────── │
│ HTTP → Request Model → Service Call → Domain Result → JSON   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Service Adapter (service/)                          │
│ ─────────────────────────────────────────────────────────── │
│ Owns infrastructure (DB, clock, crypto)                       │
│ Provides transaction boundaries                              │
│ Delegates ALL business logic to domain service               │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Domain Service (domain/)                            │
│ ─────────────────────────────────────────────────────────── │
│ Pure Pydantic model (frozen=True)                            │
│ Contains ALL business logic                                  │
│ Orchestrates workflows using entity methods                  │
└─────────────────────────────────────────────────────────────┘
```

**Example flow (login)**:

```python
# Layer 1: API Route
POST /auth/login {"email": "user@example.com", "password": "secret"}
  ↓
LoginRequest(email=EmailAddress(...), password=PasswordPlain(...))
  ↓
await auth_service.login_user(email, password)
  ↓
LoginSuccess(user=UserView(...), access_token=JwtToken(...))
  ↓
JSON: {"status": "success", "user": {...}, "access_token": {...}}

# Layer 2: Service Adapter
async with storage.transaction() as session:
    user_repo = UserRepository(session)
    return await domain_auth.login_user(email, password, user_repo, ...)

# Layer 3: Domain Service
user = await user_repo.get_by_email(email)
auth_result = user.authenticate(password)  # Entity decides
match auth_result:
    case ValidCredentials(user=user):
        return LoginSuccess(...)
    case InvalidPassword():
        return LoginFailure(...)
```

---

## Step 1: Request Contracts

API contracts are the **public interface** to your system:

```python
# api/auth/contracts.py
from pydantic import BaseModel
from ..domain.identity import EmailAddress, PasswordPlain

class LoginRequest(BaseModel):
    """
    Login request.

    Converts HTTP JSON to domain value objects.
    """
    email: EmailAddress        # Rich VO with validation
    password: PasswordPlain    # Rich VO (not hashed yet)

class RegisterRequest(BaseModel):
    """
    Registration request.

    All validation happens in value objects.
    """
    username: Username
    email: EmailAddress
    password: PasswordPlain
```

**Key points**:
- Use domain value objects (not primitives)
- Validation happens in VOs
- No business logic here
- Request models only (responses are domain DUs)

---

## Step 2: Thin Routes

Routes are ultra-thin - just delegation:

```python
# api/auth/routes.py
from fastapi import APIRouter, Depends
from .contracts import LoginRequest, RegisterRequest
from ..service.auth import AuthService
from ..deps import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResult:
    """
    Login user.

    Returns:
        LoginSuccess | LoginFailure (discriminated union)
    """
    return await auth_service.login_user(
        email=request.email,
        password=request.password,
    )

@router.post("/register")
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RegisterResult:
    """
    Register new user.

    Returns:
        RegisterSuccess | RegisterFailure (discriminated union)
    """
    return await auth_service.register_user(
        username=request.username,
        email=request.email,
        password=request.password,
    )
```

**Key points**:
- No business logic
- No error handling (domain returns DUs)
- No manual JSON construction
- Just delegation to service

---

## Step 3: FastAPI Dependencies

Dependencies provide service injection and authentication:

```python
# api/deps.py
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from ..service.auth import AuthService
from ..service.clock import ClockService
from ..domain.security import SubjectHandle, TokenClaims

# Security scheme
bearer_scheme = HTTPBearer()

# Service injection from app.state
def get_auth_service(request: Request) -> AuthService:
    """Inject AuthService from app.state."""
    return request.app.state.auth_service

def get_clock_service(request: Request) -> ClockService:
    """Inject ClockService from app.state."""
    return request.app.state.clock_service

# Authentication dependency
async def get_current_handle(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    auth: AuthService = Depends(get_auth_service),
) -> SubjectHandle:
    """
    Extract and validate Bearer token.

    Returns SubjectHandle (subject + capabilities + token).
    Raises HTTPException(401) if invalid.
    """
    token = credentials.credentials

    # Validate JWT and extract claims
    claims = await auth_service.validate_token(token)

    if not claims:
        raise HTTPException(401, "Invalid or expired token")

    # Load capabilities from database
    capabilities = await auth_service.get_capabilities(claims.token_id)

    # Construct handle
    return SubjectHandle(
        subject=claims.subject,  # Full Subject (User/Module/System)
        capabilities=tuple(capabilities),
        token=SecretStr(token),
    )
```

**Key points**:
- Service factories use dependency injection
- `get_current_handle` enforces authentication
- Returns `SubjectHandle` (authorization context)
- Raises HTTPException on auth failure

---

## Step 4: Router Security Boundaries

Security boundaries are defined in `main.py` when including routers:

```python
# main.py
from fastapi import FastAPI, Depends
from .api.auth.routes import router as auth_router
from .api.health.routes import router as health_router
from .api.deps import get_current_handle

app = FastAPI()

# Public endpoints (no auth required)
app.include_router(auth_router)  # /auth/login, /auth/register

# Protected endpoints (auth required)
app.include_router(
    health_router,
    dependencies=[Depends(get_current_handle)]  # Enforces auth
)
```

**This is zero-trust in action**:
- By default, ALL endpoints require authentication
- Only `/auth/login` and `/auth/register` are public
- Protected routers add `dependencies=[Depends(get_current_handle)]`
- Security boundary is explicit in one place

---

## Zero-Trust Architecture

### Public Endpoints (No Authentication)

Only two endpoints are public:

```python
POST /auth/login     # Authenticate, receive tokens
POST /auth/register  # Create user, auto-login
```

### Protected Endpoints (Authentication Required)

All other endpoints require Bearer token:

```python
GET /health          # Requires: Authorization: Bearer <token>
GET /documents/{id}  # Requires: Authorization: Bearer <token>
POST /graph/query    # Requires: Authorization: Bearer <token>
```

### Token-Based Authentication

After login/register, clients receive:
- **Access Token**: Short-lived (1 hour), used for API calls
- **Refresh Token**: Long-lived (30 days), used to get new access tokens

All subsequent requests must include:
```
Authorization: Bearer <access_token>
```

### Authorization with SubjectHandle

Protected endpoints receive `SubjectHandle` via dependency injection:

```python
@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    handle: SubjectHandle = Depends(get_current_handle),
    clock: ClockService = Depends(get_clock_service),
):
    # Build resource view
    resource = ResourceView(
        module_id=ModuleId(value="documents"),
        kind=ResourceKind.NODE,
        name=ResourceName(value=doc_id),
    )

    # Check authorization
    decision = handle.check_access(resource, Action.READ, clock.now())

    if not decision.allowed:
        raise HTTPException(403, "Forbidden")

    # Access granted!
    return await get_document_from_db(doc_id)
```

**Key points**:
- Authentication at API boundary (`get_current_handle`)
- Authorization in route handler (`handle.check_access()`)
- Capability-based (not role-based)
- Fine-grained resource permissions

---

## Discriminated Union Results

Domain services return discriminated unions, FastAPI serializes automatically:

```python
# Domain defines results
LoginResult = Annotated[
    LoginSuccess | LoginFailure,
    Field(discriminator="status")
]

class LoginSuccess(BaseModel):
    status: Literal["success"] = "success"
    user: UserView
    access_token: JwtToken
    refresh_token: JwtToken

class LoginFailure(BaseModel):
    status: Literal["failure"] = "failure"
    error_code: AuthErrorCode
    message: str

# Route returns result (FastAPI handles serialization)
@router.post("/login")
async def login(...) -> LoginResult:
    return await auth_service.login_user(...)  # Returns DU

# Client receives JSON:
# Success: {"status": "success", "user": {...}, "access_token": {...}}
# Failure: {"status": "failure", "error_code": "invalid_password", "message": "..."}
```

**Benefits**:
- Type-safe error handling
- No manual dict construction
- No exception-based flow control
- Client gets structured error codes

---

## Anti-Patterns

### ❌ Business Logic in Route Handler

```python
# WRONG - Business logic in route
@router.post("/auth/login")
async def login(request: LoginRequest, db: Database):
    # ❌ Business logic in route!
    user = await db.get_user(request.email)
    if not user or not bcrypt.verify(request.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    ...
```

**Fix**: Move all business logic to domain service

### ❌ Manual Error Handling

```python
# WRONG - Manual exception catching
@router.post("/auth/login")
async def login(...):
    try:
        result = await auth_service.login_user(...)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

**Fix**: Return discriminated unions, let FastAPI handle serialization

### ❌ Route Constructs Response

```python
# WRONG - Manual response construction
@router.post("/auth/login")
async def login(...):
    user, token = await auth_service.login_user(...)
    return {
        "user": {
            "id": str(user.id),
            "username": user.username,
        },
        "token": token
    }
```

**Fix**: Return domain models directly (UserView), FastAPI serializes

### ❌ Fat Dependencies

```python
# WRONG - Business logic in dependency
def get_current_user(token: str = Depends(bearer_scheme)) -> User:
    # ❌ Business logic in dependency!
    claims = jwt.decode(token, SECRET_KEY)
    user = db.get_user(claims["sub"])
    if not user.is_active:
        raise HTTPException(403, "User inactive")
    return user
```

**Fix**: Dependencies should only inject services or validate auth

---

## When to Use This Pattern

**Always.** This is the foundational pattern for all HTTP APIs.

Use thin routes for:
- ✅ All REST endpoints
- ✅ Public authentication endpoints
- ✅ Protected resource endpoints
- ✅ Health checks and status endpoints

Avoid for:
- ❌ WebSocket handlers (different pattern)
- ❌ GraphQL resolvers (different pattern)
- ❌ gRPC services (different pattern)

---

## Minimal Example

```python
# api/orders/contracts.py
class CreateOrderRequest(BaseModel):
    user_id: UserId
    items: list[OrderItem]

# api/orders/routes.py
router = APIRouter(prefix="/orders")

@router.post("")
async def create_order(
    request: CreateOrderRequest,
    handle: SubjectHandle = Depends(get_current_handle),
    order_service: OrderService = Depends(get_order_service),
) -> CreateOrderResult:
    """Create order - returns discriminated union."""
    return await order_service.create_order(
        user_id=request.user_id,
        items=request.items,
        handle=handle,  # For authorization
    )

# domain/order.py
class OrderService(BaseModel):
    model_config = {"frozen": True}

    async def create_order(
        self,
        user_id: UserId,
        items: list[OrderItem],
        handle: SubjectHandle,
        order_repo: OrderRepositoryProtocol,
    ) -> CreateOrderResult:
        # Authorization check
        decision = handle.check_access(
            resource=ResourceView(...),
            action=Action.CREATE,
            now=...,
        )

        if not decision.allowed:
            return CreateOrderDenied(reason="No permission")

        # Business logic
        order = Order.create(user_id=user_id, items=items)
        await order_repo.save(order)

        return CreateOrderSuccess(order=order)
```

---

## Key Takeaways

1. **Routes are ultra-thin** - Three responsibilities: Receive, Delegate, Return
2. **No business logic in routes** - All logic in domain services
3. **Return domain results** - FastAPI serializes automatically
4. **Use discriminated unions** - Type-safe error handling
5. **Dependencies inject services** - Clean separation of concerns
6. **Zero-trust by default** - All endpoints require auth except login/register
7. **Authorization in domain** - `SubjectHandle.check_access()` in business logic
8. **Security boundaries in main.py** - Explicit router dependencies

## Next

- **app.md** - Review rich domain entity foundations
- **app-service.md** - Review domain service orchestration pattern
- **app-service-db.md** - Review SQL database and repository pattern

