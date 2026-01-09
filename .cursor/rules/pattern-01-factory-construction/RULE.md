---
description: "Pattern 01: Construction — Parse, don't validate. Factory methods on frozen models."
globs: ["**/domain/**/*.py", "**/entity.py"]
alwaysApply: false
---

# Pattern 01: Factory Construction

## Valid Code Structure

```python
# Smart Enum
class CreationResultKind(StrEnum):
    CREATED = "created"
    REJECTED = "rejected"

# Value Objects: Use Pydantic built-ins
class User(BaseModel):
    model_config = {"frozen": True}
    email: EmailStr
    age: PositiveInt = Field(ge=18)  # Structural Constraint!
    
    # Injected Capability
    emailer: EmailCapability

# Result Types: Explicit success/failure
class UserCreated(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[CreationResultKind.CREATED]
    user: User

class UserRejected(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[CreationResultKind.REJECTED]
    reason: RejectionReason

type CreateUserResult = UserCreated | UserRejected

# Factory: Pure Construction (Crash on Failure) + Assembly
class UserFactory:
    @staticmethod
    def create(raw: dict, emailer: EmailCapability) -> CreateUserResult:
        # 1. Parse Data (Pydantic handles validation. If it fails, it crashes.)
        # This is correct. The system does not accept invalid input.
        user_data = UserData.model_validate(raw)
        
        # 2. Inject Capability
        user = User(
            email=user_data.email, 
            age=user_data.age, 
            emailer=emailer
        )
        
        return UserCreated(kind=CreationResultKind.CREATED, user=user)
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| `model_config = {"frozen": True}` | Default values on fields |
| `EmailStr`, `PositiveInt` (Pydantic built-ins) | `str`, `int` for domain concepts |
| **Factory simply calls model_validate** | **Factory manual if/else checks** |
| **Constraint encoded in Type** | **Constraint encoded in Factory Logic** |
| **Factory injects Capabilities** | **Factory is Pydantic Model** |
| Crash on invalid input | `try/except` inside Domain |
| **Smart Enums for Kinds** | **String Literals** |
