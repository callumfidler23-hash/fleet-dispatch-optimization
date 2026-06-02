"""Core types for the time-space-state network."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union


class ArcType(Enum):
    ACQUIRE = "acquire"
    RENTAL = "rental"
    REPOSITION = "reposition"
    HOLD = "hold"
    SELL = "sell"


class VehicleSegment(Enum):
    ECONOMY = "economy"
    MIDSIZE = "midsize"
    FULLSIZE = "fullsize"
    SUV = "suv"
    LUXURY = "luxury"


# Discretization bin lower bounds for vehicle state
AGE_BINS: list[int] = [0, 6, 12, 24, 36, 60]        # months
MILEAGE_BINS: list[int] = [0, 10, 30, 50, 80, 120]  # thousands of miles


def age_bin(months: float) -> int:
    idx = 0
    for i, b in enumerate(AGE_BINS):
        if months >= b:
            idx = i
    return idx


def mileage_bin(miles_k: float) -> int:
    idx = 0
    for i, b in enumerate(MILEAGE_BINS):
        if miles_k >= b:
            idx = i
    return idx


@dataclass(frozen=True)
class VehicleState:
    segment: VehicleSegment
    age_bin: int      # index into AGE_BINS
    mileage_bin: int  # index into MILEAGE_BINS

    @property
    def age_months(self) -> int:
        return AGE_BINS[self.age_bin]

    @property
    def mileage_k(self) -> int:
        return MILEAGE_BINS[self.mileage_bin]


@dataclass(frozen=True)
class Node:
    """A node in the time-space-state network: (location, period, vehicle state)."""
    location: str
    period: int
    state: VehicleState

    def label(self) -> str:
        s = self.state
        return (
            f"{self.location}@t{self.period}"
            f"[{s.segment.value},{AGE_BINS[s.age_bin]}mo,{MILEAGE_BINS[s.mileage_bin]}kmi]"
        )


# Sentinel identifiers for source/sink super-nodes
SOURCE: str = "__SOURCE__"
SINK: str = "__SINK__"
NodeRef = Union[Node, str]


@dataclass(frozen=True)
class Arc:
    """A directed arc carrying vehicle flow through the network."""
    tail: NodeRef
    head: NodeRef
    arc_type: ArcType
    # Pre-discounted net cash flow per unit of flow on this arc
    cash_flow: float
    # Ties rental arcs back to the demand they serve (for min/max constraints)
    demand_id: str | None = None


@dataclass
class RentalDemand:
    """A (possibly partial) known rental demand between two locations."""
    demand_id: str
    origin: str
    destination: str
    period: int            # departure time period
    duration: int          # periods consumed by this rental
    distance_miles: float
    min_vehicles: float    # lower bound on total flow serving this demand
    max_vehicles: float | None = None


@dataclass
class RepositionRoute:
    """A deadhead repositioning route between two locations."""
    origin: str
    destination: str
    duration: int
    distance_miles: float
