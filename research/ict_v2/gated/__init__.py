"""Data-gated interface stubs (Court docket D1): order-flow/depth (`orderflow.py`),
formal inter-market SMT (`smt.py`), point-in-time macro calendar (`macro.py`).

None of these have a live feed wired up in Phase 2. Every method on every
interface in this package raises `DataGated` -- callers must record the absence
of the data structurally (e.g. Displacement's OFI/depth/spread fields stay
`None` with an explicit `data_gated=True` attribute, per SPEC.md "Displacement")
rather than catching this exception and silently substituting a default value.
"""
from __future__ import annotations


class DataGated(Exception):
    """Raised by any gated/* interface method. The absence of the data IS the
    fact being recorded -- never catch-and-fabricate a value in its place."""
