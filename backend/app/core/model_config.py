from enum import Enum


class JsonMode(Enum):
    JSON_SCHEMA = "json_schema"  # .parse() with strict Pydantic schema — OpenAI gpt-4o+, Azure AI
    JSON_OBJECT = "json_object"  # {"type": "json_object"} — most compatible endpoints
    NONE = "none"                # unsupported; rely on prompt instructions + post-processing


# Maps lowercase model name substrings to JsonMode. First match wins.
# Add new entries here when onboarding a model with non-standard capabilities.
_JSON_MODE_REGISTRY: list[tuple[str, JsonMode]] = [
    ("microsoft_phi-4-mini-instruct", JsonMode.JSON_SCHEMA),
    ("gpt-4o",                        JsonMode.JSON_SCHEMA),  # gpt-4o, gpt-4o-mini, gpt-4o-2024-*
]


def get_json_mode(model: str) -> JsonMode:
    """Return the JSON enforcement mode for the given model name."""
    model_lower = model.lower()
    for pattern, mode in _JSON_MODE_REGISTRY:
        if pattern in model_lower:
            return mode
    return JsonMode.JSON_OBJECT
