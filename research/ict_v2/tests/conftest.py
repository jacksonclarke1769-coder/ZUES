"""Scoped pytest options for `research/ict_v2/tests` only (does not touch the repo
root `conftest.py`). `--full` gates the complete-dataset ICT V2 parity canary run
(`tests/test_model01_parity.py::test_parity_full_581_certified_signals`, ~1min, real
Databento data) -- SPEC.md's "a --full path for the complete run"; without it, only
the fast CI-time subset runs."""
import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--full",
        action="store_true",
        default=False,
        help="run the full-dataset (5.5yr, 581-signal) ICT V2 parity canary instead of skipping it",
    )
