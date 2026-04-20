"""LangGraph agent service."""

from importlib import import_module

_LAZY_SUBMODULES = {
    "checkpointer",
    "graph",
    "memory",
    "observability",
    "tools",
}


def __getattr__(name: str):
    if name in _LAZY_SUBMODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = sorted(_LAZY_SUBMODULES)
