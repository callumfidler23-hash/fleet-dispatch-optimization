"""PuLP LP formulation for the fleet dispatch NPV problem."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import pulp

from .cashflow import CashFlowParams
from .domain import Arc, ArcType, Node, SOURCE
from .network import TimeSpaceNetwork


@dataclass
class FleetDispatchLP:
    """
    LP formulation of the time-space network flow problem.

    Decision variables
    ------------------
    x[arc] >= 0   (continuous)  — flow on each arc, interpreted as the expected
                                  number of vehicles traversing that arc

    Objective
    ---------
    max  Σ  β^t(arc) · cash_flow(arc) · x[arc]
         a

    where β = 1/(1+r) and t(arc) is the departure period of the arc.

    Constraints
    -----------
    Flow conservation at each interior node (in-flow = out-flow).
    Total acquisitions ≤ max_fleet_size.
    For each demand d: Σ x[rental arcs serving d] ∈ [min_vehicles, max_vehicles].
    """

    network: TimeSpaceNetwork
    cf: CashFlowParams
    max_fleet_size: float = 1_000.0

    _prob: pulp.LpProblem | None = field(default=None, repr=False, init=False)
    _x: dict[Arc, pulp.LpVariable] | None = field(default=None, repr=False, init=False)

    def build(self) -> pulp.LpProblem:
        net = self.network
        cf = self.cf

        prob = pulp.LpProblem("fleet_dispatch_npv", pulp.LpMaximize)
        x: dict[Arc, pulp.LpVariable] = {
            arc: pulp.LpVariable(f"x_{i}", lowBound=0.0)
            for i, arc in enumerate(net.arcs)
        }

        # Objective: discounted NPV across all arcs
        prob += (
            pulp.lpSum(
                cf.discount_factor(arc.tail.period if isinstance(arc.tail, Node) else 0)
                * arc.cash_flow
                * x[arc]
                for arc in net.arcs
            ),
            "NPV",
        )

        # Flow conservation at every interior node
        for i, node in enumerate(net.nodes):
            out_flow = pulp.lpSum(x[a] for a in net.outgoing(node))
            in_flow = pulp.lpSum(x[a] for a in net.incoming(node))
            prob += (out_flow == in_flow), f"fc_{i}"

        # Fleet size cap: total vehicles acquired
        acquire_arcs = [a for a in net.arcs if a.arc_type == ArcType.ACQUIRE]
        if acquire_arcs:
            prob += (
                pulp.lpSum(x[a] for a in acquire_arcs) <= self.max_fleet_size,
                "max_fleet",
            )

        # Rental demand bounds
        by_demand: dict[str, list[Arc]] = defaultdict(list)
        for arc in net.arcs:
            if arc.demand_id is not None:
                by_demand[arc.demand_id].append(arc)

        for demand in net.demands:
            arcs = by_demand.get(demand.demand_id, [])
            if not arcs:
                continue
            prob += (
                pulp.lpSum(x[a] for a in arcs) >= demand.min_vehicles,
                f"demand_min_{demand.demand_id}",
            )
            if demand.max_vehicles is not None:
                prob += (
                    pulp.lpSum(x[a] for a in arcs) <= demand.max_vehicles,
                    f"demand_max_{demand.demand_id}",
                )

        self._prob = prob
        self._x = x
        return prob

    @property
    def problem(self) -> pulp.LpProblem:
        if self._prob is None:
            raise RuntimeError("Call build() first.")
        return self._prob

    @property
    def variables(self) -> dict[Arc, pulp.LpVariable]:
        if self._x is None:
            raise RuntimeError("Call build() first.")
        return self._x
