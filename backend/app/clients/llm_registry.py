"""
LLM model registry and per-task routing.

A registry file is REQUIRED. It is the single source of truth for which model serves
which task; there is no env-var fallback (the old LLM_MODEL setting is gone). A missing or
invalid file stops startup.

Which file is used follows ENVIRONMENT:
  local                  backend/llm_models.dev.json   (standard dev setup, local models too)
  staging / production   backend/llm_models.json       (the only file baked into the image)
LLM_REGISTRY_PATH overrides the choice explicitly (tests, eval runs).

The file separates *where a model lives* from *which model it is*:

  providers  a connection: adapter, endpoint, auth. Env-specific values are referenced by
             env var NAME (base_url_env, api_key_env) so one committed file works in every
             environment and never contains a secret.
  models     a model id plus pricing, served by one provider.
  defaults   the model for each task kind (generative / system_one).
  tasks      optional per-task overrides.

Resolution order for a task:  tasks[<task>] → defaults[<task kind>].
Every task must resolve to a model; startup validation fails otherwise.

Auth modes (provider.auth):
  auto              (default) API key when api_key_env resolves; otherwise Azure Managed
                    Identity in staging/production; otherwise a keyless local endpoint
  api_key           a key is required (api_key_env must resolve)
  managed_identity  Azure Managed Identity (Foundry in the same Azure tenant)
New clouds (AWS IAM, Google ADC, ...) are new `auth` values plus an adapter; no model
entries change.

Local-only overrides (process env or your gitignored .env; ignored with a warning when
ENVIRONMENT is staging/production):
  LLM_DEFAULT_GENERATIVE=<model>     default model for a task kind (LLM_DEFAULT_SYSTEM_ONE)
  LLM_TASK_JOB_BOUNDS=<model>        model for one task (LLM_TASK_<TASK_NAME>)
Precedence: LLM_TASK_*  >  file tasks  >  LLM_DEFAULT_*  >  file defaults. <model> must be a
name from the file's `models`; unknown names are an error so typos cannot silently no-op.

Example:
    {
      "providers": {
        "foundry": {
          "adapter": "openai_compat",
          "base_url_env": "LLM_BASE_URL",
          "api_key_env": "LLM_API_KEY"
        }
      },
      "models": {
        "gpt-5.4-mini": {"provider": "foundry", "model": "gpt-5.4-mini"}
      },
      "defaults": {"generative": "gpt-5.4-mini"},
      "tasks": {"letter_generation": "gpt-5.4-mini"}
    }
"""

import json
import os
import threading
from pathlib import Path
from typing import Literal

import structlog
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.config import settings
from app.core.llm_pricing import get_pricing, set_pricing_overrides
from app.core.llm_tasks import TaskKind, TaskName, task_kind

logger = structlog.get_logger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
PROD_REGISTRY_PATH = _BACKEND_DIR / "llm_models.json"
DEV_REGISTRY_PATH = _BACKEND_DIR / "llm_models.dev.json"

_DEFAULT_PREFIX = "LLM_DEFAULT_"
_TASK_PREFIX = "LLM_TASK_"

# Which task kinds each adapter can serve. openai_compat serves classification via
# structured output. `jev` (TypeSafe's System One API) answers typed choice/score questions
# and generates no text, so it can only serve SYSTEM_ONE tasks. The eval harness has a jev
# client (backend/evals); the app does not yet, see ResolvedLLM in llm_client.py.
ADAPTER_KINDS: dict[str, frozenset[TaskKind]] = {
    "openai_compat": frozenset({TaskKind.GENERATIVE, TaskKind.SYSTEM_ONE}),
    "jev": frozenset({TaskKind.SYSTEM_ONE}),
}


# ── File schema ───────────────────────────────────────────────────────────────


class ModelPricing(BaseModel):
    """
    USD rates as the provider quotes them, per `per_tokens` tokens (default 1M).
    Use per_tokens to copy a price sheet verbatim (e.g. 1000 for per-1K pricing); rates are
    normalized to per-1M tokens at load, which is the unit the rest of the app uses.
    """

    model_config = ConfigDict(extra="forbid")

    per_tokens: int = Field(default=1_000_000, gt=0)
    input: float
    cached: float = 0.0
    output: float = 0.0

    def per_million(self) -> dict[str, float]:
        scale = 1_000_000 / self.per_tokens
        return {
            "input": self.input * scale,
            "cached": self.cached * scale,
            "output": self.output * scale,
        }


class ProviderConfig(BaseModel):
    """A connection to somewhere models are served from."""

    model_config = ConfigDict(extra="forbid")

    adapter: str = "openai_compat"
    base_url: str | None = None  # literal endpoint (use for fixed URLs)
    base_url_env: str | None = None  # env var holding the endpoint (per-environment URLs)
    api_version: str | None = None
    auth: Literal["auto", "api_key", "managed_identity"] = "auto"
    api_key_env: str | None = None  # env var holding the key; never the key itself

    @model_validator(mode="after")
    def _one_base_url_source(self) -> "ProviderConfig":
        if self.base_url and self.base_url_env:
            raise ValueError("set base_url or base_url_env, not both")
        return self


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model: str  # deployment / model id sent to the API
    pricing: ModelPricing | None = None


class _RegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: dict[str, ProviderConfig]
    models: dict[str, ModelConfig]
    defaults: dict[TaskKind, str] = {}
    tasks: dict[TaskName, str] = {}


# ── Resolved registry ─────────────────────────────────────────────────────────


class ModelSpec(BaseModel):
    """A model joined with its provider, with env-dependent values resolved."""

    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str
    adapter: str
    model: str
    base_url: str | None = None
    base_url_env: str | None = None  # kept so validation can name the missing variable
    api_version: str | None = None
    auth: Literal["api_key", "managed_identity"] = "api_key"
    key_required: bool = False
    api_key_env: str | None = None
    pricing: ModelPricing | None = None
    # Resolved from api_key_env at load time. Never serialized or logged.
    api_key: str | None = Field(default=None, exclude=True, repr=False)

    def connection_key(self) -> tuple:
        """Identity of the connection a client is built from (shared across models)."""
        return (self.adapter, self.base_url, self.api_version, self.auth, self.api_key)


class Registry:
    def __init__(
        self,
        models: dict[str, ModelSpec],
        defaults: dict[TaskKind, str],
        tasks: dict[TaskName, str],
    ) -> None:
        self.models = models
        self.defaults = defaults
        self.tasks = tasks

    def name_for(self, task: TaskName) -> str | None:
        return self.tasks.get(task) or self.defaults.get(task_kind(task))

    def spec_for(self, task: TaskName) -> ModelSpec:
        name = self.name_for(task)
        if name is None:
            raise LookupError(
                f"no model configured for task '{task}': set tasks.{task} "
                f"or defaults.{task_kind(task)} in llm_models.json"
            )
        return self.models[name]

    def routed_specs(self) -> list[ModelSpec]:
        """Distinct models some task can actually resolve to."""
        names = {self.name_for(task) for task in TaskName} - {None}
        return [self.models[name] for name in sorted(names)]  # type: ignore[arg-type]


def _env_value(name: str) -> str | None:
    """
    Read a value by env var name: the process environment first (production, CI), then
    the local .env file. Settings reads .env into its own fields but never exports it to
    os.environ, so names defined only in .env would otherwise not resolve.
    """
    value = os.environ.get(name)
    if value:
        return value
    env_file = settings.model_config.get("env_file")
    if isinstance(env_file, str):
        return dotenv_values(env_file).get(name) or None
    return None


def _registry_path() -> Path:
    if settings.llm_registry_path:
        return Path(settings.llm_registry_path)
    return DEV_REGISTRY_PATH if settings.environment == "local" else PROD_REGISTRY_PATH


def _override_vars() -> dict[str, str]:
    """LLM_DEFAULT_* / LLM_TASK_* from the process env, then the local .env file."""
    prefixes = (_DEFAULT_PREFIX, _TASK_PREFIX)
    found = {k: v for k, v in os.environ.items() if k.startswith(prefixes) and v}
    env_file = settings.model_config.get("env_file")
    if isinstance(env_file, str):
        for key, value in dotenv_values(env_file).items():
            if key.startswith(prefixes) and value and key not in found:
                found[key] = value
    return found


def _apply_env_overrides(
    models: set[str],
    defaults: dict[TaskKind, str],
    tasks: dict[TaskName, str],
    problems: list[str],
) -> dict[str, str]:
    """Apply local-only routing overrides in place. Returns {variable: model} applied."""
    found = _override_vars()
    if not found:
        return {}
    if settings.environment != "local":
        logger.warning(
            "llm_env_overrides_ignored",
            names=sorted(found),
            detail="LLM_DEFAULT_* / LLM_TASK_* are honored only when ENVIRONMENT=local; "
            "the registry file is the source of truth here",
        )
        return {}

    applied: dict[str, str] = {}
    for var, model in sorted(found.items()):
        try:
            if var.startswith(_DEFAULT_PREFIX):
                key: TaskKind | TaskName = TaskKind(var[len(_DEFAULT_PREFIX) :].lower())
                target: dict = defaults
            else:
                key = TaskName(var[len(_TASK_PREFIX) :].lower())
                target = tasks
        except ValueError:
            valid = [f"{_DEFAULT_PREFIX}{k.upper()}" for k in TaskKind] + [
                f"{_TASK_PREFIX}{t.upper()}" for t in TaskName
            ]
            problems.append(f"{var} is not a recognised override (valid: {', '.join(valid)})")
            continue
        if model not in models:
            problems.append(f"{var}={model}: no such model in the registry file")
            continue
        target[key] = model
        applied[var] = model
    return applied


def _build_spec(name: str, model: ModelConfig, provider_name: str, p: ProviderConfig) -> ModelSpec:
    api_key = _env_value(p.api_key_env) if p.api_key_env else None
    base_url = p.base_url or (_env_value(p.base_url_env) if p.base_url_env else None)

    if p.auth == "managed_identity":
        auth, key_required = "managed_identity", False
    elif p.auth == "api_key":
        auth, key_required = "api_key", True
    elif api_key:  # auto
        auth, key_required = "api_key", False
    elif settings.environment in ("staging", "production"):
        auth, key_required = "managed_identity", False
    else:
        # Keyless local endpoint (Ollama, LM Studio). A *named* key that is missing is an
        # error, though: it means the developer forgot to set it.
        auth, key_required = "api_key", p.api_key_env is not None

    return ModelSpec(
        name=name,
        provider=provider_name,
        adapter=p.adapter,
        model=model.model,
        base_url=base_url,
        base_url_env=p.base_url_env,
        api_version=p.api_version,
        auth=auth,
        key_required=key_required,
        api_key_env=p.api_key_env,
        pricing=model.pricing,
        api_key=api_key,
    )


def load_registry(path: Path | None = None) -> Registry:
    """Load and structurally validate the registry file. Raises RuntimeError if unusable."""
    path = path or _registry_path()
    if not path.exists():
        raise RuntimeError(
            f"LLM model registry not found at {path}. Tailord requires a registry file "
            "(llm_models.dev.json locally, llm_models.json in staging/production); "
            "there is no environment-variable fallback."
        )
    try:
        parsed = _RegistryFile.model_validate(json.loads(path.read_text()))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise RuntimeError(f"Invalid LLM model registry {path}: {exc}") from exc

    problems: list[str] = []
    for provider_name, provider in parsed.providers.items():
        if provider.adapter not in ADAPTER_KINDS:
            problems.append(f"provider '{provider_name}': unknown adapter '{provider.adapter}'")
    for name, model in parsed.models.items():
        if model.provider not in parsed.providers:
            problems.append(f"model '{name}' refers to unknown provider '{model.provider}'")
    for ref, target in list(parsed.defaults.items()) + list(parsed.tasks.items()):
        if target not in parsed.models:
            problems.append(f"'{ref}' refers to unknown model '{target}'")
    defaults, tasks = dict(parsed.defaults), dict(parsed.tasks)
    overrides = _apply_env_overrides(set(parsed.models), defaults, tasks, problems)
    if problems:
        raise RuntimeError(f"Invalid LLM model registry {path}:\n  - " + "\n  - ".join(problems))

    logger.info(
        "llm_registry_loaded",
        path=str(path),
        environment=settings.environment,
        env_overrides=overrides or None,
    )
    specs = {
        name: _build_spec(name, model, model.provider, parsed.providers[model.provider])
        for name, model in parsed.models.items()
    }
    return Registry(specs, defaults, tasks)


def validate_registry(registry: Registry) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a loaded registry. Pure — raises nothing."""
    errors: list[str] = []
    warnings: list[str] = []

    for task in TaskName:
        name = registry.name_for(task)
        if name is None:
            errors.append(
                f"no model configured for task '{task}': set tasks.{task} "
                f"or defaults.{task_kind(task)}"
            )
            continue
        spec = registry.models[name]
        if task_kind(task) not in ADAPTER_KINDS[spec.adapter]:
            errors.append(
                f"task '{task}' ({task_kind(task)}) is routed to model '{name}', whose adapter "
                f"'{spec.adapter}' cannot serve {task_kind(task)} tasks"
            )

    for spec in registry.routed_specs():
        if spec.base_url_env and not spec.base_url:
            errors.append(
                f"model '{spec.name}': endpoint env var {spec.base_url_env} "
                f"(provider '{spec.provider}') is not set"
            )
        if spec.auth == "api_key" and spec.key_required and not spec.api_key:
            errors.append(
                f"model '{spec.name}': API key env var {spec.api_key_env} "
                f"(provider '{spec.provider}') is not set"
            )
        if spec.pricing is None and get_pricing(spec.model) is None:
            message = (
                f"model '{spec.name}' ({spec.model}) has no pricing — add `pricing` to "
                "llm_models.json or the catalog in app/core/llm_pricing.py so usage cost "
                "can be reported"
            )
            if settings.environment in ("staging", "production"):
                errors.append(message)
            else:
                warnings.append(message)

    return errors, warnings


def _publish_pricing(registry: Registry) -> None:
    set_pricing_overrides(
        {
            spec.model: spec.pricing.per_million()
            for spec in registry.models.values()
            if spec.pricing is not None
        }
    )


_registry: Registry | None = None
_registry_lock = threading.Lock()


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                registry = load_registry()
                _publish_pricing(registry)
                _registry = registry
    return _registry


def reset_registry() -> None:
    """Drop the cached registry (tests, or after changing settings)."""
    global _registry
    with _registry_lock:
        _registry = None
    set_pricing_overrides({})


def resolve_spec(task: TaskName, registry: Registry | None = None) -> ModelSpec:
    """Model spec for a task. `registry` lets a caller supply a different source (e.g. a
    per-user registry); it defaults to the global one."""
    return (registry or get_registry()).spec_for(task)


# Tasks that run during tailoring generation, keyed as stored in Tailoring.models.
# "letter" predates per-task routing and is kept so existing rows and readers still work.
_GENERATION_MODEL_KEYS: dict[str, TaskName] = {
    "letter": TaskName.LETTER_GENERATION,
    "job_extraction": TaskName.JOB_EXTRACTION,
    "job_bounds": TaskName.JOB_BOUNDS,
    "chunk_matching": TaskName.CHUNK_MATCHING,
}


def generation_models() -> dict[str, str]:
    """Model id per task for a tailoring generation run (stored on Tailoring.models)."""
    return {key: resolve_spec(task).model for key, task in _GENERATION_MODEL_KEYS.items()}
