---
description: FastAPI backend conventions for Tailord
globs: backend/**
---

- All user-scoped endpoints need both `require_api_key()` and `get_current_user()` dependencies.
- Storage: always use `StorageClient` abstraction. Never import `azure.*` or `boto3` directly outside `clients/storage_*.py`.
- New DB columns require an Alembic migration — never `Base.metadata.create_all()`.
- LLM calls go through `llm_client.py`. Never instantiate `OpenAI`/`AzureOpenAI` inline.
- Pick the model per task: `llm = resolve_llm(TaskName.X)` then `llm_parse_with_retry(llm.client, llm.model, ...)`. Never read model names/keys from settings or env at a call site. New LLM call site → add a `TaskName` in `app/core/llm_tasks.py`. Routing lives only in the registry file (`backend/llm_models.dev.json` locally, `backend/llm_models.json` in staging/production — keep shared providers/models identical in both; a test enforces it). Providers = connection + auth, models = id + pricing; secrets/endpoints are referenced by env var name, never stored. Every routed model needs pricing. Per-developer routing tweaks go in `.env` (`LLM_TASK_<TASK>=<model>`, local only), never in the tracked files.
- All LLM calls must use `llm_parse_with_retry(..., response_model=SomePydanticModel)`. Never use raw `json.loads()` on LLM output — no validation, no retry on malformed output.
- Background work: use FastAPI `BackgroundTasks`. Never `asyncio.create_task()` inside a request handler.
- Jev (System One) is called only through `app/clients/jev_client.py`, resolved via `resolve_llm` / `resolve_model` (adapter `jev`, `system_one` tasks only). Pin versioned model ids, never `jev-latest`. Model comparisons go through the eval harness (`backend/evals/README.md`), which never makes paid calls without an explicit `--max-spend`.
