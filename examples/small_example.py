"""
Three-location, six-period dispatch example.

LAX / SFO / SEA over 6 monthly periods.
Three segments: Economy, Midsize, SUV.
Four known rental demands + full reposition graph.
"""
from fleet_dispatch import (
    CashFlowParams,
    FleetDispatchLP,
    RentalDemand,
    RepositionRoute,
    VehicleSegment,
    build_network,
    solve,
)

locations = ["LAX", "SFO", "SEA"]
periods = 6
segments = [VehicleSegment.ECONOMY, VehicleSegment.MIDSIZE, VehicleSegment.SUV]

demands = [
    RentalDemand("lax_sfo_0", "LAX", "SFO", period=0, duration=2,
                 distance_miles=380, min_vehicles=3, max_vehicles=20),
    RentalDemand("sfo_sea_1", "SFO", "SEA", period=1, duration=3,
                 distance_miles=800, min_vehicles=2, max_vehicles=15),
    RentalDemand("sea_lax_2", "SEA", "LAX", period=2, duration=3,
                 distance_miles=1_140, min_vehicles=2, max_vehicles=15),
    RentalDemand("lax_sea_0", "LAX", "SEA", period=0, duration=3,
                 distance_miles=1_140, min_vehicles=1, max_vehicles=10),
]

routes = [
    RepositionRoute("LAX", "SFO", duration=1, distance_miles=380),
    RepositionRoute("SFO", "LAX", duration=1, distance_miles=380),
    RepositionRoute("SFO", "SEA", duration=1, distance_miles=800),
    RepositionRoute("SEA", "SFO", duration=1, distance_miles=800),
    RepositionRoute("LAX", "SEA", duration=2, distance_miles=1_140),
    RepositionRoute("SEA", "LAX", duration=2, distance_miles=1_140),
]

cf = CashFlowParams(discount_rate_per_period=0.005)
net = build_network(locations, periods, segments, demands, routes, cf)
print(net.summary())
print()

lp = FleetDispatchLP(network=net, cf=cf, max_fleet_size=50.0)
lp.build()

solution = solve(lp, msg=False)
print(solution)
