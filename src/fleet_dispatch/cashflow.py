"""Cash flow and NPV calculation parameters."""
from __future__ import annotations

from dataclasses import dataclass, field

from .domain import AGE_BINS, MILEAGE_BINS, VehicleSegment


@dataclass
class CashFlowParams:
    """
    All pricing parameters for the fleet dispatch model.

    Revenue/cost factors indexed by segment enum; age/mileage multipliers
    indexed by bin index matching AGE_BINS / MILEAGE_BINS.
    """

    discount_rate_per_period: float = 0.005  # ~6% annual with monthly periods

    # Base daily rental revenue per period by segment
    rental_revenue_per_period: dict[VehicleSegment, float] = field(
        default_factory=lambda: {
            VehicleSegment.ECONOMY: 35.0,
            VehicleSegment.MIDSIZE: 50.0,
            VehicleSegment.FULLSIZE: 65.0,
            VehicleSegment.SUV: 80.0,
            VehicleSegment.LUXURY: 120.0,
        }
    )
    # Revenue multiplier as vehicle ages (parallel to AGE_BINS)
    age_revenue_factor: list[float] = field(
        default_factory=lambda: [1.00, 0.98, 0.95, 0.90, 0.82, 0.70]
    )
    # Revenue multiplier as mileage accumulates (parallel to MILEAGE_BINS)
    mileage_revenue_factor: list[float] = field(
        default_factory=lambda: [1.00, 0.97, 0.93, 0.87, 0.78, 0.65]
    )

    # Variable operating cost per mile (fuel, tires, maintenance)
    variable_cost_per_mile: dict[VehicleSegment, float] = field(
        default_factory=lambda: {
            VehicleSegment.ECONOMY: 0.08,
            VehicleSegment.MIDSIZE: 0.10,
            VehicleSegment.FULLSIZE: 0.12,
            VehicleSegment.SUV: 0.15,
            VehicleSegment.LUXURY: 0.20,
        }
    )

    # Repositioning: fixed logistics cost + per-mile driver/fuel cost
    reposition_fixed: float = 200.0
    reposition_per_mile: float = 0.25

    # Holding cost per period while idle (insurance, lot fees)
    holding_per_period: dict[VehicleSegment, float] = field(
        default_factory=lambda: {
            VehicleSegment.ECONOMY: 5.0,
            VehicleSegment.MIDSIZE: 7.0,
            VehicleSegment.FULLSIZE: 9.0,
            VehicleSegment.SUV: 12.0,
            VehicleSegment.LUXURY: 20.0,
        }
    )

    # New-vehicle acquisition cost by segment
    acquisition_cost: dict[VehicleSegment, float] = field(
        default_factory=lambda: {
            VehicleSegment.ECONOMY: 20_000.0,
            VehicleSegment.MIDSIZE: 28_000.0,
            VehicleSegment.FULLSIZE: 35_000.0,
            VehicleSegment.SUV: 45_000.0,
            VehicleSegment.LUXURY: 70_000.0,
        }
    )
    # Salvage value as fraction of acquisition cost, by age bin
    salvage_age_factor: list[float] = field(
        default_factory=lambda: [0.85, 0.75, 0.65, 0.50, 0.35, 0.20]
    )
    # Additional salvage multiplier by mileage bin
    salvage_mileage_factor: list[float] = field(
        default_factory=lambda: [1.00, 0.92, 0.82, 0.70, 0.55, 0.40]
    )

    def discount_factor(self, period: int) -> float:
        return (1.0 / (1.0 + self.discount_rate_per_period)) ** period

    def rental_net(
        self,
        seg: VehicleSegment,
        duration: int,
        age_b: int,
        mileage_b: int,
        distance_miles: float,
    ) -> float:
        revenue = (
            self.rental_revenue_per_period[seg]
            * duration
            * self.age_revenue_factor[age_b]
            * self.mileage_revenue_factor[mileage_b]
        )
        cost = self.variable_cost_per_mile[seg] * distance_miles
        return revenue - cost

    def reposition_net(self, distance_miles: float) -> float:
        return -(self.reposition_fixed + self.reposition_per_mile * distance_miles)

    def holding_net(self, seg: VehicleSegment, duration: int = 1) -> float:
        return -self.holding_per_period[seg] * duration

    def salvage_value(self, seg: VehicleSegment, age_b: int, mileage_b: int) -> float:
        return (
            self.acquisition_cost[seg]
            * self.salvage_age_factor[age_b]
            * self.salvage_mileage_factor[mileage_b]
        )

    def acquire_net(self, seg: VehicleSegment) -> float:
        return -self.acquisition_cost[seg]
