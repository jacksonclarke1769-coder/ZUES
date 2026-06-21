"""CONFIGLOCK — safe resolution of the official exit model.

Resolution order: committed default (config_defaults) -> optional local override (config.py).
Fail CLOSED for live/paper/controlled execution: a missing config is SAFE (falls back to the
committed EXIT3_FIXED_PARTIAL), but a SINGLE_TARGET or unknown override RAISES rather than
silently executing the wrong model. Emergency flatten/cancel never call this, so they are
never blocked.
"""
from config_defaults import (
    EXIT_MODEL as DEFAULT_EXIT_MODEL,
    EXIT_MODEL_ALLOWED,
    EXIT_MODEL_RESEARCH_ONLY,
    EXECUTION_MODES,
)


class ConfigLockError(RuntimeError):
    """Raised when an unsafe/unknown exit model is requested for execution."""


def resolve_exit_model(mode: str = "live") -> str:
    """Return the exit model to use. `mode` in {live,paper,controlled} fails closed on an
    unsafe override; `research`/`test` may use a research-only model for comparison."""
    exit_model = DEFAULT_EXIT_MODEL
    try:
        import config                                   # gitignored local override (optional)
        exit_model = getattr(config, "EXIT_MODEL", exit_model) or DEFAULT_EXIT_MODEL
    except Exception:                                    # noqa: BLE001 — no local config is SAFE
        exit_model = DEFAULT_EXIT_MODEL

    execution = mode in EXECUTION_MODES
    if execution:
        if exit_model in EXIT_MODEL_RESEARCH_ONLY:
            raise ConfigLockError(
                f"CONFIGLOCK: unsafe exit model blocked — '{exit_model}' is research-only and "
                f"cannot be used for {mode} execution")
        if exit_model not in EXIT_MODEL_ALLOWED:
            raise ConfigLockError(
                f"CONFIGLOCK: unsafe exit model blocked — unknown EXIT_MODEL='{exit_model}' "
                f"for {mode} execution")
    else:
        # research/test path: only allowed or explicitly research-only values are valid
        if exit_model not in (EXIT_MODEL_ALLOWED | EXIT_MODEL_RESEARCH_ONLY):
            raise ConfigLockError(f"CONFIGLOCK: unknown EXIT_MODEL='{exit_model}'")
    return exit_model
