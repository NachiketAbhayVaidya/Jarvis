"""Skill registry: decorate a function with @tool(...) to expose it to the LLM."""

_REGISTRY = {}


def tool(name, description, parameters):
    """Register a function as an LLM-callable tool.

    parameters follows the OpenAI JSON Schema function-parameters format, e.g.:
        {"type": "object", "properties": {...}, "required": [...]}
    """

    def decorator(fn):
        _REGISTRY[name] = {
            "fn": fn,
            "schema": {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            },
        }
        return fn

    return decorator


def get_tool_schemas():
    return [entry["schema"] for entry in _REGISTRY.values()]


def get_tool(name):
    """Returns the registry entry ({"fn", "schema"}) for a tool, or None."""
    return _REGISTRY.get(name)


def call_tool(name, args):
    if name not in _REGISTRY:
        return f"Unknown tool: {name}"
    return _REGISTRY[name]["fn"](**args)


# Import skill modules so their @tool decorators run and populate the registry.
from . import web, music, system, apps, confirm, files  # noqa: E402,F401
