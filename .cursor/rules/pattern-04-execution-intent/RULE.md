---
description: "Pattern 04: Execution — Active Capability. Domain Models execute actions via injected tools."
globs: ["**/domain/**/*.py"]
alwaysApply: false
---

# Pattern 04: Execution (Active Capability)

## Valid Code Structure

```python
# Smart Enums
class SignupResultKind(StrEnum):
    SENT = "sent"
    FAILED = "failed"

class SignupResult(BaseModel):
    model_config = {"frozen": True}
    kind: SignupResultKind
    message_id: str | None = None

# The Capability (Tool)
# Injected into the Domain. This is the "Hand" of the model.
class EmailCapability(BaseModel):
    model_config = {"frozen": True, "arbitrary_types_allowed": True}
    
    # Holds the actual client (e.g. SMTP connection)
    client: Any 

    def send(self, to: Email, subject: str, body: str) -> EmailResult:
        # Implementation of the side effect
        # Returns Railway Result, catches Structural Failure inside if needed
        return self.client.send(to, subject, body)

# The Domain Model (Active Agent)
class User(BaseModel):
    model_config = {"frozen": True}
    
    id: UserId
    email: Email
    
    # Injected Capability
    emailer: EmailCapability

    def signup(self) -> SignupResult:
        # The Domain decides AND executes
        # "The thing is the thing" - The User signs up.
        result = self.emailer.send(
            to=self.email, 
            subject="Welcome", 
            body="..."
        )
        
        if result.is_success:
             return SignupResult(kind=SignupResultKind.SENT, message_id=result.message_id)
        
        return SignupResult(kind=SignupResultKind.FAILED)
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| **Capability injected into Model** | **Service Class executing Intent** |
| **Logic and Execution co-located** | Separation of "Decide" and "Do" |
| **Active Domain Model** | **Passive DTO** |
| **Smart Enums for Result Kinds** | **Magic Strings** |
| Real Clients (or Test Clients) | Mocks of Interfaces |
