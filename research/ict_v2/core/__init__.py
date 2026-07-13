"""Core contracts for the ICT V2 causal event engine (WP-A). See ../SPEC.md
"Core contracts" section -- this package is the binding implementation of it.
"""
from .events import CausalEvent, EventStore, compute_event_id
from .clock import SessionEngine, SessionInfo, NY
from .config import ParamSet, ICT_V2_PARAMS_V0
from .prefix import assert_prefix_invariant, assert_chunk_invariant
from .runner import BatchRunner, EngineProtocol, run_engine

__all__ = [
    "CausalEvent", "EventStore", "compute_event_id",
    "SessionEngine", "SessionInfo", "NY",
    "ParamSet", "ICT_V2_PARAMS_V0",
    "assert_prefix_invariant", "assert_chunk_invariant",
    "BatchRunner", "EngineProtocol", "run_engine",
]
