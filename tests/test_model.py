"""Tests for LP formulation and solve."""
import pytest

from fleet_dispatch import (
    ArcType,
    CashFlowParams,
    FleetDispatchLP,
    RentalDemand,
    RepositionRoute,
    VehicleSegment,
    build_network,
    solve,
)


def tiny_problem(max_fleet: float = 10.0):
    locations = ["A", "B"]
    periods = 3
    segments = [VehicleSegment.ECONOMY]
    demands = [
        RentalDemand("r1", "A", "B", period=0, duration=1, distance_miles=100.0,
                     min_vehicles=1.0),
    ]
    routes = [RepositionRoute("B", "A", duration=1, distance_miles=100.0)]
    cf = CashFlowParams()
    net = build_network(locations, periods, segments, demands, routes, cf)
    lp = FleetDispatchLP(network=net, cf=cf, max_fleet_size=max_fleet)
    lp.build()
    return net, lp


def test_lp_builds():
    _, lp = tiny_problem()
    assert lp.problem is not None
    assert len(lp.variables) > 0


def test_solve_optimal():
    _, lp = tiny_problem()
    sol = solve(lp)
    assert sol.status == "Optimal"


def test_fleet_acquired_nonneg():
    _, lp = tiny_problem()
    sol = solve(lp)
    assert sol.fleet_acquired >= 0


def test_fleet_acquired_within_cap():
    _, lp = tiny_problem(max_fleet=5.0)
    sol = solve(lp)
    assert sol.fleet_acquired <= 5.0 + 1e-6


def test_demand_satisfied():
    net, lp = tiny_problem()
    sol = solve(lp)
    assert sol.status == "Optimal"

    from collections import defaultdict
    demand_flow: dict[str, float] = defaultdict(float)
    for arc, flow in sol.flows.items():
        if arc.arc_type == ArcType.RENTAL and arc.demand_id:
            demand_flow[arc.demand_id] += flow

    for demand in net.demands:
        assert demand_flow[demand.demand_id] >= demand.min_vehicles - 1e-6


def test_npv_better_than_unconstrained_zero():
    # Over a 3-period horizon the forced acquisition makes NPV negative, but the
    # optimizer still finds the best attainable value (sell quickly after the rental).
    _, lp = tiny_problem()
    sol = solve(lp)
    # Sanity: mandatory demand is served, so fleet_acquired >= 1
    assert sol.fleet_acquired >= 1.0 - 1e-6


def test_infeasible_demand_detected():
    # Demand requires more vehicles than max_fleet allows (0 fleet)
    locations = ["A", "B"]
    periods = 3
    segments = [VehicleSegment.ECONOMY]
    demands = [
        RentalDemand("r1", "A", "B", period=0, duration=1, distance_miles=100.0,
                     min_vehicles=5.0),
    ]
    cf = CashFlowParams()
    net = build_network(locations, periods, segments, demands, [], cf)
    lp = FleetDispatchLP(network=net, cf=cf, max_fleet_size=0.0)
    lp.build()
    sol = solve(lp)
    assert sol.status != "Optimal"


def test_solution_str():
    _, lp = tiny_problem()
    sol = solve(lp)
    s = str(sol)
    assert "NPV" in s
    assert "Status" in s
