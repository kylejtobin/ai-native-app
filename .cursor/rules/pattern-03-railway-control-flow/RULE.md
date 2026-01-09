---
description: "Pattern 03: Control Flow — Railway oriented programming. No exceptions for domain logic."
globs: ["**/domain/**/*.py"]
alwaysApply: false
---

# Pattern 03: Railway Control Flow

## Valid Code Structure

```python
# Smart Enums for Result Kinds
class WithdrawalResultKind(StrEnum):
    SUCCESS = "success"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    SKIPPED = "skipped"

# Value Object (Owns the Logic)
class Money(BaseModel):
    model_config = {"frozen": True}
    cents: PositiveInt

    def subtract(self, other: "Money") -> "Money | InsufficientFunds":
        # The Type owns the rule. The Entity just calls it.
        if other.cents > self.cents:
            return InsufficientFunds(
                kind=WithdrawalResultKind.INSUFFICIENT_FUNDS,
                current_balance=self,
                requested=other
            )
        return Money(cents=self.cents - other.cents)

# Result Types
class WithdrawalSuccess(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[WithdrawalResultKind.SUCCESS]
    new_balance: Money

class InsufficientFunds(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[WithdrawalResultKind.INSUFFICIENT_FUNDS]
    current_balance: Money
    requested: Money

type WithdrawalResult = WithdrawalSuccess | InsufficientFunds

# Entity (Delegates to Value Object)
class Account(BaseModel):
    model_config = {"frozen": True}
    balance: Money
    
    def withdraw(self, amount: Money) -> WithdrawalResult:
        # No defensive 'if' here.
        # Delegate logic to the Value Object.
        match self.balance.subtract(amount):
            case InsufficientFunds() as failure:
                return failure
            case Money() as new_balance:
                return WithdrawalSuccess(kind=WithdrawalResultKind.SUCCESS, new_balance=new_balance)

# Explicit NoOp
class PaymentSkipped(BaseModel):
    model_config = {"frozen": True}
    kind: Literal[WithdrawalResultKind.SKIPPED]
    reason: SkippedReason
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| Return `Success \| Failure` Sum Type | `raise Exception()` for business logic |
| **Smart Enums for Result Kinds** | **String Literals for Result Kinds** |
| **Logic on Value Object** | **Logic leaked into Entity (defensive if)** |
| Structural Rules (Types) -> Crash | Business Rules -> Result Type |
| Explicit `Skipped`/`NoOp` type | `return None` |
| `match/case` to handle tracks | `try/except` for logic |
| **Typed Reasons (SkippedReason)** | **String Literals for Reason** |
