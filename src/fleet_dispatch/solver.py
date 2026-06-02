"""Solver interface and solution container."""
from __future__ import annotations

from dataclasses import dataclass

import pulp

from .domain import Arc, ArcType, Node
from .model import FleetDispatchLP


@dataclass
class DispatchSolution:
    status: str
    npv: float
    flows: dict[Arc, float]

    @property
    def fleet_acquired(self) -> float:
        return sum(f for a, f in self.flows.items() if a.arc_type == ArcType.ACQUIRE)

    @property
    def vehicles_sold(self) -> float:
        return sum(f for a, f in self.flows.items() if a.arc_type == ArcType.SELL)

    def flow_by_type(self) -> dict[ArcType, float]:
        totals: dict[ArcType, float] = {}
        for arc, flow in self.flows.items():
            if flow > 1e-8:
                totals[arc.arc_type] = totals.get(arc.arc_type, 0.0) + flow
        return totals

    def __str__(self) -> str:
        lines = [
            f"Status       : {self.status}",
            f"NPV          : ${self.npv:>12,.2f}",
            f"Fleet acquired: {self.fleet_acquired:.2f} vehicles",
            f"Fleet sold   : {self.vehicles_sold:.2f} vehicles",
            "Active flows by arc type:",
        ]
        for arc_type, total in sorted(
            self.flow_by_type().items(), key=lambda kv: kv[0].value
        ):
            lines.append(f"  {arc_type.value:<12} {total:.2f} veh·arcs")
        return "\n".join(lines)


def solve(
    lp_model: FleetDispatchLP,
    solver: pulp.LpSolver | None = None,
    msg: bool = False,
) -> DispatchSolution:
    """Solve the LP and return a DispatchSolution."""
    if solver is None:
        solver = pulp.PULP_CBC_CMD(msg=msg)

    prob = lp_model.problem
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    npv = pulp.value(prob.objective) or 0.0
    flows = {arc: max(pulp.value(var) or 0.0, 0.0) for arc, var in lp_model.variables.items()}

    return DispatchSolution(status=status, npv=npv, flows=flows)
