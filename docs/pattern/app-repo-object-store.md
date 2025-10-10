# Object Store Repository Pattern

> **Binary object storage with observability**

## Overview

Object stores handle binary blob storage (files, images, documents). Repository provides semantic operations over S3-compatible APIs.

**Current implementation:** MinIO (S3-compatible)
**Future options:** Azure Blob Storage, Google Cloud Storage

---

## Repository Interface

```python
from typing import Protocol

class ObjectRepository(Protocol):
    async def store(
        self,
        key: ObjectKey,
        data: bytes,
        metadata: ObjectMetadata
    ) -> StoredObject:
        """Store object."""
        ...
    
    async def retrieve(self, key: ObjectKey) -> StoredObject | None:
        """Retrieve object."""
        ...
    
    async def delete(self, key: ObjectKey) -> bool:
        """Delete object."""
        ...
```

---

## MinIO Implementation

```python
import logfire
from minio import Minio

class MinioObjectRepository:
    def __init__(self, client: Minio, bucket: BucketName):
        self.client = client
        self.bucket = bucket
    
    async def store(
        self,
        key: ObjectKey,
        data: bytes,
        metadata: ObjectMetadata
    ) -> StoredObject:
        with logfire.span(
            "repo.object.store",
            key=key.value,
            size=len(data),
            content_type=metadata.content_type
        ):
            self.client.put_object(
                bucket_name=self.bucket.value,
                object_name=key.value,
                data=BytesIO(data),
                length=len(data),
                metadata=metadata.to_dict()
            )
            return StoredObject(key=key, size=len(data), metadata=metadata)
```

---

## Related Patterns

- **app-repo.md** - Generic repository pattern
- **app-persistence.md** - Storage strategy overview

---

*This file will be expanded when implementing object storage domain.*
