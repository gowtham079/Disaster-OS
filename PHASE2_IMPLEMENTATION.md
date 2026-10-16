# Disaster OS — Phase 2 implementation

## Compatibility

The orchestrator lifecycle and existing API paths are unchanged. A simulation
still advances through `INIT`, `INCIDENT_REPORTED`, `RESOURCE_ALLOCATED`,
`RESCUE_IN_PROGRESS`, and `COMPLETED`. External routing is optional and cannot
terminate a simulation.

## Routing provenance

`RoutingService` first attempts an OSRM-compatible road router and falls back
to the existing local A* city graph on timeout, invalid data, network failure,
or a no-route response. The result includes `route_source` and
`route_provider`; the map labels the two route types separately.

Configuration:

- `OSRM_ENABLED=true|false` (default `true`)
- `OSRM_BASE_URL=https://router.project-osrm.org`
- `OSRM_TIMEOUT_SECONDS=2.5`

For production, point `OSRM_BASE_URL` at an organization-controlled OSRM
deployment. The public demonstration server should not be treated as an SLA.

## Explainable allocation score

Available resources are ranked on a 100-point score calculated only from data
already stored for each team:

- proximity: 45 points, linearly decreasing to zero at 1,200 km;
- availability: 25 points;
- capacity: up to 20 points, capped at a capacity of 25;
- supported specialization: 10 points (otherwise 5).

The chosen score, factor breakdown, actual/simulated route estimate, and a
plain-language selection explanation are persisted with the incident.

## Interface changes

- Consolidated color, typography, spacing, radius, focus, and motion tokens.
- Reduced card/border repetition and strengthened operational hierarchy.
- Workflow animation follows persisted lifecycle state—no fake timers.
- GIS-first map workspace with floating layers, professional SVG markers,
  resource markers, impact zones, responsive controls, and route provenance.
- Critical pulse is limited to active high-priority incidents.
- Added reduced-motion behavior and visible keyboard focus states.

## Verification

- Python source compilation completed successfully.
- A 150-incident integration run completed all five states.
- React optimized production build compiled successfully.

