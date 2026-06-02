"""Tests for time-space-state network construction."""
import pytest

from fleet_dispatch import (
    AGE_BINS,
    MILEAGE_BINS,
    ArcType,
    CashFlowParams,
    RentalDemand,
    RepositionRoute,
    VehicleSegment,
    build_network,
)


def small_network():
    locations = ["LAX", "SFO"]
    periods = 4
    segments = [VehicleSegment.ECONOMY, VehicleSegment.MIDSIZE]
    demands = [
        RentalDemand("r1", "LAX", "SFO", period=0, duration=2, distance_miles=380.0,
                     min_vehicles=2.0, max_vehicles=10.0),
        RentalDemand("r2", "SFO", "LAX", period=1, duration=2, distance_miles=380.0,
                     min_vehicles=1.0),
    ]
    routes = [
        RepositionRoute("LAX", "SFO", duration=1, distance_miles=380.0),
        RepositionRoute("SFO", "LAX", duration=1, distance_miles=380.0),
    ]
    return build_network(locations, periods, segments, demands, routes, CashFlowParams())


def test_node_count():
    net = small_network()
    # 2 locations × 4 periods × 2 segments × 6 age_bins × 6 mileage_bins
    assert len(net.nodes) == 2 * 4 * 2 * len(AGE_BINS) * len(MILEAGE_BINS)


def test_acquire_arcs():
    net = small_network()
    acquire = [a for a in net.arcs if a.arc_type == ArcType.ACQUIRE]
    # 2 locations × 2 segments × 1 (new only: age_bin=0, mileage_bin=0)
    assert len(acquire) == 2 * 2


def test_acquire_cash_flow_is_negative():
    net = small_network()
    for a in net.arcs:
        if a.arc_type == ArcType.ACQUIRE:
            assert a.cash_flow < 0


def test_sell_arc_count():
    net = small_network()
    sell = [a for a in net.arcs if a.arc_type == ArcType.SELL]
    # Every interior node gets exactly one SELL arc
    assert len(sell) == len(net.nodes)


def test_sell_cash_flow_is_positive():
    net = small_network()
    for a in net.arcs:
        if a.arc_type == ArcType.SELL:
            assert a.cash_flow > 0


def test_hold_arcs_exist():
    net = small_network()
    hold = [a for a in net.arcs if a.arc_type == ArcType.HOLD]
    assert len(hold) > 0


def test_hold_arcs_advance_time():
    net = small_network()
    from fleet_dispatch.domain import Node
    for a in net.arcs:
        if a.arc_type == ArcType.HOLD:
            assert isinstance(a.tail, Node) and isinstance(a.head, Node)
            assert a.head.period == a.tail.period + 1
            assert a.head.location == a.tail.location


def test_rental_arcs_have_demand_id():
    net = small_network()
    for a in net.arcs:
        if a.arc_type == ArcType.RENTAL:
            assert a.demand_id is not None


def test_demands_skipped_beyond_horizon():
    from fleet_dispatch import build_network, RentalDemand, CashFlowParams, VehicleSegment
    # demand that would land at period == periods (out of bounds)
    demands = [
        RentalDemand("oob", "A", "B", period=3, duration=1, distance_miles=100.0,
                     min_vehicles=1.0)
    ]
    net = build_network(["A", "B"], 4, [VehicleSegment.ECONOMY], demands, [], CashFlowParams())
    rental = [a for a in net.arcs if a.arc_type == ArcType.RENTAL]
    assert len(rental) == 0


def test_summary_string():
    net = small_network()
    s = net.summary()
    assert "nodes=" in s
    assert "arcs=" in s
    assert "rental" in s
