"""gated/*: DataGated stubs (orderflow, smt, macro) -- Court docket D1."""
from __future__ import annotations

import pytest

from research.ict_v2.gated import DataGated
from research.ict_v2.gated.macro import MACRO_CSV_SCHEMA, MacroCalendarInterface
from research.ict_v2.gated.macro import DataGated as MacroDataGated
from research.ict_v2.gated.orderflow import DataGated as OFDataGated
from research.ict_v2.gated.orderflow import OrderFlowInterface
from research.ict_v2.gated.smt import DataGated as SMTDataGated
from research.ict_v2.gated.smt import SMTInterface


def test_all_stub_modules_reexport_the_same_datagated_class():
    assert OFDataGated is DataGated
    assert SMTDataGated is DataGated
    assert MacroDataGated is DataGated


def test_datagated_is_an_exception():
    assert issubclass(DataGated, Exception)


def test_orderflow_interface_all_methods_gated():
    iface = OrderFlowInterface()
    with pytest.raises(DataGated):
        iface.ofi(bar=None)
    with pytest.raises(DataGated):
        iface.depth_imbalance(bar=None)
    with pytest.raises(DataGated):
        iface.spread(bar=None)


def test_smt_interface_gated():
    iface = SMTInterface()
    with pytest.raises(DataGated):
        iface.divergence(primary_bar=None, secondary_bar=None)


def test_macro_interface_gated():
    iface = MacroCalendarInterface()
    with pytest.raises(DataGated):
        import datetime

        iface.events_known_by(datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc))


def test_macro_csv_schema_has_point_in_time_columns():
    cols = [c.strip() for c in MACRO_CSV_SCHEMA.split(",")]
    assert cols == [
        "release_time_utc",
        "known_at_utc",
        "event_name",
        "country",
        "importance",
        "actual",
        "forecast",
        "previous",
        "revised_from",
    ]
    # the point-in-time discipline hinges on these two distinct timestamp columns
    assert "release_time_utc" in cols and "known_at_utc" in cols
