---
description: "Pattern 05: Configuration — AppConfig as Single Source of Truth using Pydantic Settings."
globs: ["**/config.py", "**/env.py", "**/main.py", "**/system/**/*.py"]
alwaysApply: false
---

# Pattern 05: Config Injection

## Valid Code Structure

```python
from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# The Domain Config IS the Environment Schema.
# This lives in domain/system/config.py
class AppConfig(BaseSettings):
    """
    The Single Source of Truth for Configuration.
    Defines the contract between the App and the Environment.
    """
    model_config = SettingsConfigDict(env_file=".env", frozen=True)
    
    # Declarative Mapping: Domain Name <- Environment Name
    # Uses Typed Fields (PostgresDsn, ApiKey) NOT strings
    database_url: PostgresDsn = Field(alias="DATABASE_URL")
    stripe_key: ApiKey = Field(alias="STRIPE_API_KEY")
    debug_mode: bool = Field(default=False, alias="DEBUG")

# Usage in Composition Root
def main():
    # 1. Load & Validate (Crash if missing)
    config = AppConfig()
    
    # 2. Inject
    app = create_app(config)
```

## Constraints

| Required | Forbidden |
|----------|-----------|
| **`AppConfig` inherits `BaseSettings`** | `os.environ` scattered in code |
| **Lives in Domain (Schema Definition)** | Creating separate "Loader" classes |
| Explicit `Field(alias=...)` mapping | `try/except` around config loading |
| `frozen=True` (Immutable) | Mutable configuration |
| **Typed Fields (PostgresDsn)** | **Stringly Typed Config (str)** |
| **Crash on Missing Config** | Returning `ConfigResult` |
