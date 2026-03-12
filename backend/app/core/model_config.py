from dataclasses import dataclass
from enum import Enum


class JsonMode(Enum):
    JSON_SCHEMA = "json_schema"  # .parse() with strict Pydantic schema — OpenAI gpt-4o+ only
    JSON_OBJECT = "json_object"  # {"type": "json_object"} — most compatible endpoints
    NONE = "none"                # unsupported; rely on prompt instructions + post-processing


@dataclass
class ModelCapabilities:
    json_mode: JsonMode = JsonMode.JSON_OBJECT
    supports_temperature: bool = True


# Maps lowercase model name substrings to ModelCapabilities. First match wins.
# Add new entries here when onboarding a model with non-standard capabilities.
_CAPABILITIES_REGISTRY: list[tuple[str, ModelCapabilities]] = [

    # Local
    ("microsoft_phi-4-mini-instruct", ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA)),
    ("qwen2.5-vl-32b-instruct",       ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA)),
    ("qwen3.5-9b",                    ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA)),
    ("gemma-3-12b",                   ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA)),
    ("gemma-3-4b",                    ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA)),

    # Azure Foundry
    ("phi-4-mini",                    ModelCapabilities(json_mode=JsonMode.JSON_OBJECT)),
    ("gpt-5-nano",                    ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA, supports_temperature=False)),
    ("gpt-4o",                        ModelCapabilities(json_mode=JsonMode.JSON_SCHEMA)),
]

_DEFAULT_CAPABILITIES = ModelCapabilities()


def get_capabilities(model: str) -> ModelCapabilities:
    """Return the full capability profile for the given model name."""
    model_lower = model.lower()
    for pattern, caps in _CAPABILITIES_REGISTRY:
        if pattern in model_lower:
            return caps
    return _DEFAULT_CAPABILITIES


def get_json_mode(model: str) -> JsonMode:
    """Convenience accessor — prefer get_capabilities() for new code."""
    return get_capabilities(model).json_mode
