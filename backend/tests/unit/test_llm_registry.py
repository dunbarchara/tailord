import json
import os
from pathlib import Path

import pytest

from app.clients import llm_client, llm_registry
from app.clients.llm_client import resolve_llm, validate_llm_config
from app.clients.llm_registry import ModelSpec, get_registry, load_registry
from app.config import settings
from app.core import llm_pricing
from app.core.llm_tasks import TASK_KINDS, TaskKind, TaskName

PRICED = {"input": 1.0, "cached": 0.1, "output": 2.0}


@pytest.fixture(autouse=True)
def _local_env(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "environment", "local")
    # An isolated cwd so a developer's real .env is never read.
    monkeypatch.chdir(tmp_path)
    for var in ("TEST_KEY", "TEST_URL"):
        monkeypatch.delenv(var, raising=False)
    for var in list(os.environ):  # a developer's own overrides must not leak into tests
        if var.startswith(("LLM_DEFAULT_", "LLM_TASK_")):
            monkeypatch.delenv(var)


def _config(**overrides) -> dict:
    config = {
        "providers": {"p": {"base_url": "http://p.invalid/v1"}},
        "models": {
            "mini": {"provider": "p", "model": "mini-deploy", "pricing": PRICED},
            "big": {"provider": "p", "model": "big-deploy", "pricing": PRICED},
            "other": {"provider": "p", "model": "other-deploy", "pricing": PRICED},
        },
        "defaults": {"generative": "mini"},
        "tasks": {},
    }
    config.update(overrides)
    return config


def _use(tmp_path, monkeypatch, config: dict) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(settings, "llm_registry_path", str(path))
    return path


@pytest.fixture
def use_config(tmp_path, monkeypatch):
    return lambda **overrides: _use(tmp_path, monkeypatch, _config(**overrides))


class TestTaskCatalog:
    def test_every_task_has_a_kind(self):
        assert set(TASK_KINDS) == set(TaskName)

    def test_all_current_tasks_are_generative(self):
        assert set(TASK_KINDS.values()) == {TaskKind.GENERATIVE}


class TestRegistryIsRequired:
    def test_missing_file_fails_startup(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_registry_path", "/nonexistent/llm_models.json")
        with pytest.raises(RuntimeError, match="not found"):
            validate_llm_config()

    def test_no_env_fallback_when_file_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "llm_model_deprecated", "gpt-5.4")
        monkeypatch.setattr(settings, "llm_registry_path", None)
        monkeypatch.setattr(llm_registry, "DEV_REGISTRY_PATH", Path("/nonexistent/x.json"))
        with pytest.raises(RuntimeError, match="no environment-variable fallback"):
            get_registry()

    def test_committed_registries_are_valid_and_route_every_task(self):
        for path in (llm_registry.DEV_REGISTRY_PATH, llm_registry.PROD_REGISTRY_PATH):
            registry = load_registry(path)
            for task in TaskName:
                registry.spec_for(task)

    def test_dev_registry_mirrors_prod_providers(self):
        """Dev may add providers (local models) but must not redefine prod's."""
        prod = json.loads(llm_registry.PROD_REGISTRY_PATH.read_text())
        dev = json.loads(llm_registry.DEV_REGISTRY_PATH.read_text())
        for name, provider in prod["providers"].items():
            assert dev["providers"].get(name) == provider, f"provider '{name}' differs in dev"
        for name, model in prod["models"].items():
            assert dev["models"].get(name) == model, f"model '{name}' differs in dev"

    @pytest.mark.parametrize(
        "path", [llm_registry.DEV_REGISTRY_PATH, llm_registry.PROD_REGISTRY_PATH]
    )
    def test_jev_models_are_priced_and_read_their_key_from_env(self, path, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "ts-secret")
        registry = load_registry(path)
        spec = registry.models["jev-1.14.0"]
        assert spec.adapter == "jev" and spec.auth == "api_key"
        assert spec.api_key == "ts-secret" and "ts-secret" not in repr(spec)
        assert spec.pricing is not None and spec.pricing.output == 0.0
        # Pinned versions only: the alias moves under us.
        assert not any("latest" in name for name in registry.models)

    def test_legacy_llm_model_env_is_warned_about(self, use_config, monkeypatch):
        use_config()
        monkeypatch.setattr(settings, "llm_model_deprecated", "gpt-5.4")
        calls = []
        monkeypatch.setattr(llm_client.logger, "warning", lambda *a, **k: calls.append(a))
        validate_llm_config()
        assert ("llm_legacy_env_ignored",) in calls


class TestResolution:
    def test_kind_default_routes_every_task(self, use_config):
        use_config()
        for task in TaskName:
            assert resolve_llm(task).model == "mini-deploy"

    def test_task_override_wins_over_kind_default(self, use_config):
        use_config(tasks={"letter_generation": "big"})
        assert resolve_llm(TaskName.LETTER_GENERATION).model == "big-deploy"
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "mini-deploy"
        assert resolve_llm(TaskName.LETTER_GENERATION).task == TaskName.LETTER_GENERATION

    def test_missing_default_fails_validation(self, use_config):
        use_config(defaults={}, tasks={"job_bounds": "mini"})
        with pytest.raises(RuntimeError, match="no model configured for task 'chunk_matching'"):
            validate_llm_config()

    def test_every_task_overridden_needs_no_default(self, use_config):
        use_config(defaults={}, tasks={t.value: "mini" for t in TaskName})
        validate_llm_config()

    def test_custom_registry_can_be_supplied(self, tmp_path, use_config):
        use_config()
        other = tmp_path / "other.json"
        other.write_text(
            json.dumps(
                _config(
                    providers={"q": {"base_url": "http://q.invalid/v1"}},
                    models={"m": {"provider": "q", "model": "user-model", "pricing": PRICED}},
                    defaults={"generative": "m"},
                )
            )
        )
        llm = resolve_llm(TaskName.JOB_BOUNDS, load_registry(other))
        assert llm.model == "user-model"
        assert llm.spec.base_url == "http://q.invalid/v1"


class TestLoadErrors:
    def test_unknown_key_rejected(self, use_config):
        use_config(modles={})
        with pytest.raises(RuntimeError, match="Invalid LLM model registry"):
            get_registry()

    def test_unknown_task_name_rejected(self, use_config):
        use_config(tasks={"nonsense": "mini"})
        with pytest.raises(RuntimeError, match="Invalid LLM model registry"):
            get_registry()

    def test_malformed_json_rejected(self, tmp_path, monkeypatch):
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        monkeypatch.setattr(settings, "llm_registry_path", str(path))
        with pytest.raises(RuntimeError, match="Invalid LLM model registry"):
            get_registry()

    def test_unknown_provider_rejected(self, use_config):
        use_config(models={"x": {"provider": "nope", "model": "x", "pricing": PRICED}})
        with pytest.raises(RuntimeError, match="unknown provider 'nope'"):
            get_registry()

    def test_unknown_model_reference_rejected(self, use_config):
        use_config(tasks={"job_bounds": "nope"})
        with pytest.raises(RuntimeError, match="unknown model 'nope'"):
            get_registry()

    def test_unknown_adapter_rejected(self, use_config):
        use_config(providers={"p": {"adapter": "mystery", "base_url": "http://x"}})
        with pytest.raises(RuntimeError, match="unknown adapter 'mystery'"):
            get_registry()

    def test_base_url_and_base_url_env_are_exclusive(self, use_config):
        use_config(providers={"p": {"base_url": "http://x", "base_url_env": "TEST_URL"}})
        with pytest.raises(RuntimeError, match="not both"):
            get_registry()


class TestEnvResolution:
    def test_base_url_resolved_from_process_env(self, use_config, monkeypatch):
        use_config(providers={"p": {"base_url_env": "TEST_URL"}})
        monkeypatch.setenv("TEST_URL", "http://from-env/v1")
        assert resolve_llm(TaskName.JOB_BOUNDS).spec.base_url == "http://from-env/v1"

    def test_missing_base_url_env_fails_validation(self, use_config):
        use_config(providers={"p": {"base_url_env": "TEST_URL"}})
        with pytest.raises(RuntimeError, match="endpoint env var TEST_URL"):
            validate_llm_config()

    def test_values_resolved_from_local_dotenv(self, use_config, tmp_path):
        (tmp_path / ".env").write_text("TEST_URL=http://dotenv/v1\nTEST_KEY=from-dotenv\n")
        use_config(providers={"p": {"base_url_env": "TEST_URL", "api_key_env": "TEST_KEY"}})
        spec = get_registry().models["mini"]
        assert spec.base_url == "http://dotenv/v1"
        assert spec.api_key == "from-dotenv"
        validate_llm_config()

    def test_process_env_wins_over_dotenv(self, use_config, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("TEST_KEY=from-dotenv\n")
        monkeypatch.setenv("TEST_KEY", "from-process")
        use_config(providers={"p": {"base_url": "http://x", "api_key_env": "TEST_KEY"}})
        assert get_registry().models["mini"].api_key == "from-process"

    def test_api_key_never_serialized(self, use_config, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "secret-value")
        use_config(providers={"p": {"base_url": "http://x", "api_key_env": "TEST_KEY"}})
        spec = get_registry().models["mini"]
        assert "secret-value" not in repr(spec)
        assert "secret-value" not in spec.model_dump_json()


class TestAuthModes:
    def test_auto_with_key_uses_api_key(self, use_config, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "k")
        monkeypatch.setattr(settings, "environment", "production")
        use_config(providers={"p": {"base_url": "http://x", "api_key_env": "TEST_KEY"}})
        assert get_registry().models["mini"].auth == "api_key"

    def test_auto_without_key_uses_managed_identity_in_production(self, use_config, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        use_config(providers={"p": {"base_url": "http://x", "api_key_env": "TEST_KEY"}})
        spec = get_registry().models["mini"]
        assert spec.auth == "managed_identity"
        validate_llm_config()  # a missing key is expected under managed identity

    def test_auto_without_key_is_keyless_locally(self, use_config):
        use_config()  # no api_key_env at all: a local model server
        assert get_registry().models["mini"].auth == "api_key"
        validate_llm_config()

    def test_auto_with_named_but_missing_key_fails_locally(self, use_config):
        use_config(providers={"p": {"base_url": "http://x", "api_key_env": "TEST_KEY"}})
        with pytest.raises(RuntimeError, match="API key env var TEST_KEY"):
            validate_llm_config()

    def test_explicit_api_key_requires_key_even_in_production(self, use_config, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        use_config(
            providers={"p": {"base_url": "http://x", "auth": "api_key", "api_key_env": "TEST_KEY"}}
        )
        with pytest.raises(RuntimeError, match="API key env var TEST_KEY"):
            validate_llm_config()

    def test_explicit_managed_identity_needs_no_key(self, use_config):
        use_config(providers={"p": {"base_url": "http://x", "auth": "managed_identity"}})
        assert get_registry().models["mini"].auth == "managed_identity"
        validate_llm_config()


class TestClientCache:
    def test_models_on_one_provider_share_a_client(self, use_config):
        use_config(tasks={"job_bounds": "big"})
        assert resolve_llm(TaskName.JOB_BOUNDS).client is resolve_llm(TaskName.GAP_ANALYSIS).client

    def test_different_connections_get_different_clients(self, use_config):
        use_config(
            providers={"p": {"base_url": "http://p/v1"}, "q": {"base_url": "http://q/v1"}},
            models={
                "mini": {"provider": "p", "model": "m1", "pricing": PRICED},
                "big": {"provider": "q", "model": "m2", "pricing": PRICED},
            },
            tasks={"job_bounds": "big"},
        )
        job_bounds = resolve_llm(TaskName.JOB_BOUNDS)
        assert job_bounds.client is not resolve_llm(TaskName.GAP_ANALYSIS).client

    def test_connection_key_covers_endpoint_and_credentials(self):
        a = ModelSpec(name="a", provider="p", adapter="x", model="m", base_url="u", api_key="k1")
        b = a.model_copy(update={"name": "b", "model": "other", "pricing": None})
        c = a.model_copy(update={"api_key": "k2"})
        assert a.connection_key() == b.connection_key()
        assert a.connection_key() != c.connection_key()


class TestValidation:
    def test_clean_config_passes(self, use_config):
        use_config(tasks={"job_bounds": "big"})
        validate_llm_config()

    def test_adapter_kind_mismatch_fails(self, use_config, monkeypatch):
        monkeypatch.setitem(
            llm_registry.ADAPTER_KINDS, "classifier_only", frozenset({TaskKind.SYSTEM_ONE})
        )
        use_config(providers={"p": {"adapter": "classifier_only", "base_url": "http://x"}})
        with pytest.raises(RuntimeError, match="cannot serve generative"):
            validate_llm_config()

    def test_system_one_adapter_ok_as_system_one_default(self, use_config, monkeypatch):
        monkeypatch.setitem(
            llm_registry.ADAPTER_KINDS, "classifier_only", frozenset({TaskKind.SYSTEM_ONE})
        )
        use_config(
            providers={
                "p": {"base_url": "http://x"},
                "c": {"adapter": "classifier_only", "base_url": "http://c"},
            },
            models={
                "mini": {"provider": "p", "model": "m", "pricing": PRICED},
                "cls": {"provider": "c", "model": "cls", "pricing": PRICED},
            },
            defaults={"generative": "mini", "system_one": "cls"},
        )
        validate_llm_config()

    def test_jev_adapter_serves_only_system_one(self):
        assert llm_registry.ADAPTER_KINDS["jev"] == frozenset({TaskKind.SYSTEM_ONE})

    def test_generative_task_routed_to_jev_model_fails_validation(self, use_config):
        use_config(
            providers={
                "p": {"base_url": "http://x"},
                "t": {"adapter": "jev", "base_url": "http://t", "api_key_env": "TEST_KEY"},
            },
            models={
                "mini": {"provider": "p", "model": "m", "pricing": PRICED},
                "jev": {"provider": "t", "model": "jev-1", "pricing": PRICED},
            },
            tasks={"job_bounds": "jev"},
        )
        with pytest.raises(RuntimeError, match="cannot serve generative"):
            validate_llm_config()

    def test_app_cannot_resolve_a_client_for_a_jev_model_yet(self, use_config):
        use_config(
            providers={"t": {"adapter": "jev", "base_url": "http://t"}},
            models={"jev": {"provider": "t", "model": "jev-1", "pricing": PRICED}},
            defaults={"generative": "jev"},
        )
        with pytest.raises(NotImplementedError, match="adapter 'jev'"):
            resolve_llm(TaskName.JOB_BOUNDS)

    def test_unrouted_model_problems_are_ignored(self, use_config):
        use_config(
            providers={
                "p": {"base_url": "http://x"},
                "q": {"base_url": "http://q", "api_key_env": "TEST_KEY", "auth": "api_key"},
            },
            models={
                "mini": {"provider": "p", "model": "m", "pricing": PRICED},
                "unused": {"provider": "q", "model": "unpriced-unused"},
            },
        )
        validate_llm_config()


class TestPricing:
    def test_unpriced_routed_model_warns_locally(self, use_config, monkeypatch):
        use_config(models={"mini": {"provider": "p", "model": "no-such-priced-model"}})
        calls = []
        monkeypatch.setattr(llm_client.logger, "warning", lambda *a, **k: calls.append((a, k)))
        validate_llm_config()  # must not raise locally
        assert any("no pricing" in k.get("detail", "") for _, k in calls)

    def test_unpriced_routed_model_fails_in_production(self, use_config, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        use_config(models={"mini": {"provider": "p", "model": "no-such-priced-model"}})
        with pytest.raises(RuntimeError, match="no pricing"):
            validate_llm_config()

    def test_catalog_pricing_satisfies_production_check(self, use_config, monkeypatch):
        monkeypatch.setattr(settings, "environment", "production")
        use_config(models={"mini": {"provider": "p", "model": "gpt-5.4"}})
        validate_llm_config()

    def test_registry_pricing_overrides_catalog(self, use_config):
        use_config(
            models={
                "mini": {
                    "provider": "p",
                    "model": "gpt-5.4-mini",
                    "pricing": {"input": 100.0, "output": 200.0},
                }
            }
        )
        get_registry()
        cost = llm_pricing.compute_cost_usd(
            model="gpt-5.4-mini", input_tokens=1_000_000, output_tokens=1_000_000
        )
        assert cost == pytest.approx(300.0)

    def test_registry_pricing_prices_models_missing_from_catalog(self, use_config):
        use_config(
            models={
                "mini": {
                    "provider": "p",
                    "model": "brand-new-model",
                    "pricing": {"input": 1.0, "output": 2.0},
                }
            }
        )
        get_registry()
        assert llm_pricing.compute_cost_usd(
            model="brand-new-model", input_tokens=1_000_000
        ) == pytest.approx(1.0)

    def test_per_tokens_scale_is_normalized_to_per_million(self, use_config):
        use_config(
            models={
                "mini": {
                    "provider": "p",
                    "model": "per-1k-model",
                    "pricing": {
                        "per_tokens": 1000,
                        "input": 0.003,
                        "cached": 0.0003,
                        "output": 0.015,
                    },
                }
            }
        )
        get_registry()
        assert llm_pricing.get_pricing("per-1k-model") == pytest.approx(
            {"input": 3.0, "cached": 0.3, "output": 15.0}
        )
        assert llm_pricing.compute_cost_usd(
            model="per-1k-model", input_tokens=1_000, output_tokens=1_000
        ) == pytest.approx(0.018)

    def test_per_tokens_defaults_to_one_million(self):
        assert llm_registry.ModelPricing(input=2.0, output=8.0).per_million() == {
            "input": 2.0,
            "cached": 0.0,
            "output": 8.0,
        }

    @pytest.mark.parametrize("per_tokens", [0, -1000])
    def test_non_positive_per_tokens_rejected(self, use_config, per_tokens):
        use_config(
            models={
                "mini": {
                    "provider": "p",
                    "model": "m",
                    "pricing": {"per_tokens": per_tokens, "input": 1.0},
                }
            }
        )
        with pytest.raises(RuntimeError, match="Invalid LLM model registry"):
            get_registry()

    def test_unpriced_model_returns_none_and_warns_once(self, monkeypatch):
        llm_pricing.set_pricing_overrides({})
        calls = []
        monkeypatch.setattr(llm_pricing.logger, "warning", lambda *a, **k: calls.append((a, k)))
        assert llm_pricing.compute_cost_usd(model="mystery-xyz", input_tokens=10) is None
        assert llm_pricing.compute_cost_usd(model="mystery-xyz", input_tokens=10) is None
        assert len(calls) == 1
        assert calls[0][1]["model"] == "mystery-xyz"


class TestGenerationModels:
    def test_every_key_follows_default(self, use_config):
        use_config()
        assert llm_registry.generation_models() == {
            "letter": "mini-deploy",
            "job_extraction": "mini-deploy",
            "job_bounds": "mini-deploy",
            "chunk_matching": "mini-deploy",
        }

    def test_reflects_per_task_routing(self, use_config):
        use_config(tasks={"letter_generation": "big", "chunk_matching": "other"})
        models = llm_registry.generation_models()
        assert models["letter"] == "big-deploy"
        assert models["chunk_matching"] == "other-deploy"
        assert models["job_bounds"] == "mini-deploy"


def _two_files(tmp_path, monkeypatch):
    dev = tmp_path / "dev.json"
    prod = tmp_path / "prod.json"
    dev.write_text(json.dumps(_config()))
    prod_config = _config()
    prod_config["models"]["mini"]["model"] = "prod-mini"
    prod.write_text(json.dumps(prod_config))
    monkeypatch.setattr(settings, "llm_registry_path", None)
    monkeypatch.setattr(llm_registry, "DEV_REGISTRY_PATH", dev)
    monkeypatch.setattr(llm_registry, "PROD_REGISTRY_PATH", prod)
    return dev, prod


class TestRegistryFileSelection:
    def test_local_uses_dev_file(self, tmp_path, monkeypatch):
        _two_files(tmp_path, monkeypatch)
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "mini-deploy"

    @pytest.mark.parametrize("environment", ["staging", "production"])
    def test_deployed_environments_use_prod_file(self, tmp_path, monkeypatch, environment):
        _two_files(tmp_path, monkeypatch)
        monkeypatch.setattr(settings, "environment", environment)
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "prod-mini"

    def test_explicit_path_overrides_environment(self, tmp_path, monkeypatch):
        _, prod = _two_files(tmp_path, monkeypatch)
        monkeypatch.setattr(settings, "llm_registry_path", str(prod))
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "prod-mini"

    def test_missing_dev_file_fails_locally(self, tmp_path, monkeypatch):
        _two_files(tmp_path, monkeypatch)
        monkeypatch.setattr(llm_registry, "DEV_REGISTRY_PATH", tmp_path / "absent.json")
        with pytest.raises(RuntimeError, match="not found"):
            get_registry()


class TestEnvOverrides:
    def test_task_override_beats_file_task_and_default(self, use_config, monkeypatch):
        use_config(tasks={"job_bounds": "big"})
        monkeypatch.setenv("LLM_TASK_JOB_BOUNDS", "other")
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "other-deploy"
        assert resolve_llm(TaskName.GAP_ANALYSIS).model == "mini-deploy"

    def test_default_override_beats_file_default_but_not_file_task(self, use_config, monkeypatch):
        use_config(tasks={"job_bounds": "big"})
        monkeypatch.setenv("LLM_DEFAULT_GENERATIVE", "other")
        assert resolve_llm(TaskName.GAP_ANALYSIS).model == "other-deploy"
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "big-deploy"

    def test_overrides_read_from_dotenv(self, use_config, tmp_path):
        (tmp_path / ".env").write_text("LLM_TASK_LETTER_GENERATION=big\n")
        use_config()
        assert resolve_llm(TaskName.LETTER_GENERATION).model == "big-deploy"

    def test_process_env_wins_over_dotenv(self, use_config, tmp_path, monkeypatch):
        (tmp_path / ".env").write_text("LLM_TASK_LETTER_GENERATION=big\n")
        monkeypatch.setenv("LLM_TASK_LETTER_GENERATION", "other")
        use_config()
        assert resolve_llm(TaskName.LETTER_GENERATION).model == "other-deploy"

    def test_unknown_task_name_is_an_error(self, use_config, monkeypatch):
        use_config()
        monkeypatch.setenv("LLM_TASK_JOB_BOUND", "big")  # typo
        with pytest.raises(RuntimeError, match="LLM_TASK_JOB_BOUND is not a recognised override"):
            get_registry()

    def test_unknown_kind_is_an_error(self, use_config, monkeypatch):
        use_config()
        monkeypatch.setenv("LLM_DEFAULT_CLASSIFIER", "big")
        with pytest.raises(RuntimeError, match="LLM_DEFAULT_CLASSIFIER is not a recognised"):
            get_registry()

    def test_unknown_model_is_an_error(self, use_config, monkeypatch):
        use_config()
        monkeypatch.setenv("LLM_TASK_JOB_BOUNDS", "nope")
        with pytest.raises(RuntimeError, match="LLM_TASK_JOB_BOUNDS=nope: no such model"):
            get_registry()

    @pytest.mark.parametrize("environment", ["staging", "production"])
    def test_ignored_with_warning_outside_local(self, use_config, monkeypatch, environment):
        monkeypatch.setattr(settings, "environment", environment)
        use_config()
        monkeypatch.setenv("LLM_TASK_JOB_BOUNDS", "big")
        calls = []
        monkeypatch.setattr(llm_registry.logger, "warning", lambda *a, **k: calls.append((a, k)))
        assert resolve_llm(TaskName.JOB_BOUNDS).model == "mini-deploy"
        assert calls[0][0] == ("llm_env_overrides_ignored",)
        assert calls[0][1]["names"] == ["LLM_TASK_JOB_BOUNDS"]

    def test_applied_overrides_are_logged(self, use_config, monkeypatch):
        use_config()
        monkeypatch.setenv("LLM_TASK_JOB_BOUNDS", "big")
        calls = []
        monkeypatch.setattr(llm_registry.logger, "info", lambda *a, **k: calls.append((a, k)))
        get_registry()
        loaded = [k for a, k in calls if a == ("llm_registry_loaded",)][0]
        assert loaded["env_overrides"] == {"LLM_TASK_JOB_BOUNDS": "big"}
