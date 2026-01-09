---
description: "Pattern 07: Translation — Foreign Models (inbound) and API Contracts (outbound)."
globs: ["**/domain/**/*.py", "**/api/**/*.py"]
alwaysApply: false
---

# Pattern 07: ACL Translation

Translation happens at boundaries in **both directions**:
- **Inbound (Foreign Models):** External system → `.to_domain()` → Domain
- **Outbound (API Contracts):** Domain → Request/Response models → HTTP clients

---

## Inbound: Foreign Models

```python
# Foreign Model: Mirrors external API shape exactly
class CoinbaseCandle(BaseModel):
    model_config = {"frozen": True}
    
    # Field(alias=...) maps foreign names to readable internal names
    time: UnixTimestamp = Field(alias="t")
    open: Price = Field(alias="o")
    high: Price = Field(alias="h")
    
    def to_domain(self) -> Candle:
        # Pure Translation Logic
        # Structural mismatches (e.g. missing fields) cause Pydantic to CRASH before this runs.
        return Candle(
            timestamp=datetime.fromtimestamp(self.time, tz=timezone.utc),
            open=self.open,
            high=self.high,
        )

# LLM Response as Foreign Model
class GptSentimentResponse(BaseModel):
    model_config = {"frozen": True}
    
    sentiment_label: RawLabel = Field(alias="label")
    confidence_score: Probability = Field(alias="probability")
    
    def to_domain(self) -> SentimentDecision:
        # Translation Logic: Mapping string to literal
        if "pos" in self.sentiment_label.lower():
            kind = SentimentKind.POSITIVE
        elif "neg" in self.sentiment_label.lower():
            kind = SentimentKind.NEGATIVE
        else:
            # If input is unexpected, CRASH. Do not silently default.
            raise ValueError(f"Unknown sentiment: {self.sentiment_label}")
            
        return SentimentDecision(kind=kind, score=self.confidence_score)

# Raw → Foreign → Domain chain
class RawSmtpConnectError(BaseModel):
    model_config = {"frozen": True}
    kind: Literal["connect_error"]
    message: ErrorMessage
    
    def to_foreign(self) -> SmtpConnectErrorForeign:
        return SmtpConnectErrorForeign(message=self.message)

# Usage: raw.to_foreign().to_domain()
```

## Inbound Constraints

| Required | Forbidden |
|----------|-----------|
| Foreign Model mirrors external schema exactly | Raw dict passing into domain |
| `Field(alias=...)` for name mapping | Manual field copying |
| `.to_domain()` method on Foreign Model | Standalone mapper functions |
| `raw.to_foreign().to_domain()` chain | Direct external data in domain |
| Foreign Model imports Internal Truth | Internal Truth imports Foreign Model |
| **Translation Failures -> Crash (Structure)** | **Translation Failures -> Result (Logic)** |
| **Typed Fields (Price, UnixTimestamp)** | **Primitive Fields (float, int)** |

---

## Outbound: API Contracts

API request/response models live in `domain/context/api.py`. The domain defines what it exposes.

```python
# domain/event/api.py - The contract lives WITH the domain

class PublishEventRequest(BaseModel):
    """HTTP request model - what clients send us."""
    model_config = {"frozen": True}

    stream: str
    subject: str
    payload: bytes

    def to_intent(self) -> PublishEvent:
        """Translate HTTP request to domain intent."""
        return PublishEvent(
            stream_name=StreamName(self.stream),
            subject=EventSubject(self.subject),
            payload=self.payload,
        )


class PublishEventResponse(BaseModel):
    """HTTP response model - what we send clients."""
    model_config = {"frozen": True}

    published: bool
    sequence: int

    @classmethod
    def from_outcome(cls, outcome: EventPublished) -> "PublishEventResponse":
        """Translate domain outcome to HTTP response."""
        return cls(published=True, sequence=outcome.sequence)


# api/event.py - Just wiring (imports from domain)

from domain.event.api import PublishEventRequest, PublishEventResponse

@router.post("/events/publish")
async def publish(request: PublishEventRequest) -> PublishEventResponse:
    intent = request.to_intent()
    outcome = await store.publish(intent)
    return PublishEventResponse.from_outcome(outcome)
```

## Outbound Constraints

| Required | Forbidden |
|----------|-----------|
| Request/Response models in `domain/context/api.py` | API models in `api/` directory |
| `.to_intent()` on Request models | Inline intent construction in routes |
| `.from_outcome()` on Response models | Inline response construction in routes |
| `api/context.py` imports from domain | Domain imports from api |
| Routes are thin (parse → call → format) | Business logic in routes |
