---
description: "Pattern 09: Workflow — Process as explicit State Machine with transition methods."
globs: ["**/process.py", "**/workflow.py", "**/domain/**/*.py"]
alwaysApply: false
---

# Pattern 09: Workflow State Machine

## Valid Code Structure

```python
# Smart Enum (Behavioral Type)
class SignupKind(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    COMPLETED = "completed"

# Each workflow state is its own type
class SignupPending(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[SignupKind.PENDING]
    email: Email
    
    def verify(self, user_id: UserId) -> tuple["SignupVerified", "SendEmailIntent"]:
        new_state = SignupVerified(kind=SignupKind.VERIFIED, user_id=user_id)
        intent = SendEmailIntent(to=self.email, template=TemplateName.WELCOME)
        return new_state, intent

class SignupVerified(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[SignupKind.VERIFIED]
    user_id: UserId
    
    def complete(self) -> tuple["SignupCompleted", "NotifyAdminIntent"]:
        new_state = SignupCompleted(kind=SignupKind.COMPLETED, user_id=self.user_id)
        intent = NotifyAdminIntent(user_id=self.user_id)
        return new_state, intent

class SignupCompleted(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[SignupKind.COMPLETED]
    user_id: UserId

# Sum Type for all states
type SignupState = Annotated[
    SignupPending | SignupVerified | SignupCompleted,
    Field(discriminator="kind")
]

# Workflow Runtime: Active Domain Model
class WorkflowRuntime(BaseModel):
    """
    Active Domain Model. Drives the State Machine.
    """
    model_config = {"frozen": True, "arbitrary_types_allowed": True}
    
    # Injected Capability (Store)
    store: WorkflowStore
    
    async def run_step(self, id: WorkflowId, event: WorkflowEvent) -> RunResult:
        # 1. Load (Generic I/O via Capability)
        state = await self.store.load(id)
        
        # 2. Pure Transition (Domain Logic)
        new_state, intent = state.handle(event)
        
        # 3. Save (Generic I/O via Capability)
        await self.store.save(id, new_state)
        
        # 4. Return Intent for Execution
        return RunResult(kind="stepped", intent=intent)
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| Each state is its own frozen type | One class with `status` field |
| **Smart Enums for State Kinds** | **String Literals for State Kinds** |
| **Typed IDs (WorkflowId)** | **Primitive IDs (str)** |
| Transition methods on source state | Standalone `def verify_signup()` functions |
| Returns `(NewState, Intent)` tuple | Side effects in transition |
| **Runtime is a Domain Model** | **Runtime is a Service Class** |
| Runtime delegates to `state.handle()` | Logic inside Runtime |
