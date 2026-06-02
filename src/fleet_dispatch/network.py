"""Time-space-state network construction."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .cashflow import CashFlowParams
from .domain import (
    AGE_BINS,
    MILEAGE_BINS,
    Arc,
    ArcType,
    Node,
    NodeRef,
    RentalDemand,
    RepositionRoute,
    SINK,
    SOURCE,
    VehicleSegment,
    VehicleState,
    age_bin,
    mileage_bin,
)


@dataclass
class TimeSpaceNetwork:
    nodes: set[Node] = field(default_factory=set)
    arcs: list[Arc] = field(default_factory=list)
    demands: list[RentalDemand] = field(default_factory=list)
    _out: dict[NodeRef, list[Arc]] = field(
        default_factory=lambda: defaultdict(list), repr=False
    )
    _in: dict[NodeRef, list[Arc]] = field(
        default_factory=lambda: defaultdict(list), repr=False
    )

    def add_arc(self, arc: Arc) -> None:
        self.arcs.append(arc)
        self._out[arc.tail].append(arc)
        self._in[arc.head].append(arc)

    def outgoing(self, node: NodeRef) -> list[Arc]:
        return self._out[node]

    def incoming(self, node: NodeRef) -> list[Arc]:
        return self._in[node]

    def summary(self) -> str:
        counts: dict[ArcType, int] = defaultdict(int)
        for a in self.arcs:
            counts[a.arc_type] += 1
        parts = [f"nodes={len(self.nodes)}", f"arcs={len(self.arcs)}"]
        for t in ArcType:
            if t in counts:
                parts.append(f"{t.value}={counts[t]}")
        return "TimeSpaceNetwork(" + ", ".join(parts) + ")"


def _advance_state(
    state: VehicleState,
    age_periods: float,
    period_months: float,
    distance_miles: float,
) -> VehicleState:
    """Return the new VehicleState after traversing an arc."""
    new_age_months = state.age_months + age_periods * period_months
    new_mileage_k = state.mileage_k + distance_miles / 1000.0
    return VehicleState(
        segment=state.segment,
        age_bin=age_bin(new_age_months),
        mileage_bin=mileage_bin(new_mileage_k),
    )


def build_network(
    locations: list[str],
    periods: int,
    segments: list[VehicleSegment],
    demands: list[RentalDemand],
    reposition_routes: list[RepositionRoute],
    cf: CashFlowParams,
    period_months: float = 1.0,
) -> TimeSpaceNetwork:
    """
    Build the full time-space-state network.

    Node space: location × period × (segment, age_bin, mileage_bin).

    Arc types
    ---------
    ACQUIRE   SOURCE → (loc, t=0, new state)       purchase cost
    RENTAL    (origin, t, s) → (dest, t+D, s')     rental revenue minus variable cost
    REPOSITION (l, t, s) → (l', t+D, s')           deadhead cost
    HOLD      (l, t, s) → (l, t+1, s')             idle holding cost
    SELL      (l, t, s) → SINK                     salvage value (absorbing arc)

    All arc cash flows are expressed at the departure period; the LP discounts them.
    """
    net = TimeSpaceNetwork(demands=list(demands))

    all_states = [
        VehicleState(seg, ab, mb)
        for seg in segments
        for ab in range(len(AGE_BINS))
        for mb in range(len(MILEAGE_BINS))
    ]

    # Register every (location, period, state) node
    for loc in locations:
        for t in range(periods):
            for state in all_states:
                net.nodes.add(Node(loc, t, state))

    # ACQUIRE arcs: only brand-new vehicles (age_bin=0, mileage_bin=0) at t=0
    for loc in locations:
        for seg in segments:
            new_state = VehicleState(seg, age_bin=0, mileage_bin=0)
            net.add_arc(
                Arc(
                    tail=SOURCE,
                    head=Node(loc, 0, new_state),
                    arc_type=ArcType.ACQUIRE,
                    cash_flow=cf.acquire_net(seg),
                )
            )

    # RENTAL arcs: one arc per (demand, vehicle state) pair
    for demand in demands:
        arrival = demand.period + demand.duration
        if arrival >= periods:
            continue
        for state in all_states:
            arrived_state = _advance_state(
                state,
                age_periods=demand.duration,
                period_months=period_months,
                distance_miles=demand.distance_miles,
            )
            tail = Node(demand.origin, demand.period, state)
            head = Node(demand.destination, arrival, arrived_state)
            if tail not in net.nodes or head not in net.nodes:
                continue
            net.add_arc(
                Arc(
                    tail=tail,
                    head=head,
                    arc_type=ArcType.RENTAL,
                    cash_flow=cf.rental_net(
                        state.segment,
                        demand.duration,
                        state.age_bin,
                        state.mileage_bin,
                        demand.distance_miles,
                    ),
                    demand_id=demand.demand_id,
                )
            )

    # REPOSITION arcs
    for route in reposition_routes:
        for t in range(periods):
            arrival = t + route.duration
            if arrival >= periods:
                continue
            for state in all_states:
                arrived_state = _advance_state(
                    state,
                    age_periods=route.duration,
                    period_months=period_months,
                    distance_miles=route.distance_miles,
                )
                tail = Node(route.origin, t, state)
                head = Node(route.destination, arrival, arrived_state)
                if tail not in net.nodes or head not in net.nodes:
                    continue
                net.add_arc(
                    Arc(
                        tail=tail,
                        head=head,
                        arc_type=ArcType.REPOSITION,
                        cash_flow=cf.reposition_net(route.distance_miles),
                    )
                )

    # HOLD arcs: vehicle sits for one period, accumulating age only
    for loc in locations:
        for t in range(periods - 1):
            for state in all_states:
                aged_state = _advance_state(
                    state,
                    age_periods=1.0,
                    period_months=period_months,
                    distance_miles=0.0,
                )
                net.add_arc(
                    Arc(
                        tail=Node(loc, t, state),
                        head=Node(loc, t + 1, aged_state),
                        arc_type=ArcType.HOLD,
                        cash_flow=cf.holding_net(state.segment),
                    )
                )

    # SELL arcs: absorbing arcs to SINK, available at every node
    for node in net.nodes:
        net.add_arc(
            Arc(
                tail=node,
                head=SINK,
                arc_type=ArcType.SELL,
                cash_flow=cf.salvage_value(
                    node.state.segment, node.state.age_bin, node.state.mileage_bin
                ),
            )
        )

    return net
