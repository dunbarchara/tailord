---
description: FastAPI backend conventions for Tailord
globs: backend/**
---

- All user-scoped endpoints need both `require_api_key()` and `get_current_user()` dependencies.
- Storage: always use `StorageClient` abstraction. Never import `azure.*` or `boto3` directly outside `clients/storage_*.py`.
- New DB columns require an Alembic migration — never `Base.metadata.create_all()`.
- LLM calls go through `llm_client.py`. Never instantiate `OpenAI`/`AzureOpenAI` inline.
- All LLM calls must use `llm_parse_with_retry(..., response_model=SomePydanticModel)`. Never use raw `json.loads()` on LLM output — no validation, no retry on malformed output.
- Background work: use FastAPI `BackgroundTasks`. Never `asyncio.create_task()` inside a request handler.
