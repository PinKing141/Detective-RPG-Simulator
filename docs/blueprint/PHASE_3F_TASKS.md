# Phase 3F - Multi-site Cases (Location Visits)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3f---multi-site-cases-location-visits

Phase question:
Do multi-site cases create meaningful travel trade-offs without open-world sprawl?

Phase 3F is not:
- open-world travel
- schedule simulation
- a map UI
- new evidence classes
- unlimited locations

## Scope (allowed)
- 2 to 4 locations per case (primary scene plus related sites).
- Location roles: primary scene, last-seen site, suspect anchor, collateral witness site.
- Travel action to move between known locations (time and pressure cost).
- Locations are discovered through leads and evidence, not shown by default.
- Each location uses the existing POI system (Phase 3A).
- Location-specific neighbor leads and POIs.
- World state can modify location access or cooperation tone.

## Core changes
1) Case location roster
- Assign 2 to 4 locations at case start.
- Tag each location with a role (primary/related/suspect/collateral).
- Start with the primary scene and one related site unlocked.

2) Location discovery rules
- New locations unlock when specific leads are pursued (interview, CCTV, digital).
- No "free" discovery; every new site is earned or timed.

3) Travel/visit loop
- Add a "Visit location" action that selects from known sites.
- Moving locations costs time and may increase pressure.
- Only the active location shows POIs and local leads.

4) Evidence distribution
- At least one key evidence item lives off the primary scene.
- Each location should bias toward a different evidence mix:
  - primary: forensic/temporal
  - related: testimonial/opportunity
  - suspect anchor: digital/behavioral
  - collateral: witness contradictions

5) Lead decay across locations
- Leads have deadlines regardless of location.
- Travel can cause a lead to expire; this must be visible.

## Constraints (non-negotiable)
- No more than 4 locations per case.
- No global map or free travel UI.
- No NPC schedules or commute simulation.
- No new evidence classes.
- No forced "visit everything" path.

## Deliverables
- Location roster per case with roles and unlock status.
- Travel action that changes the active location.
- Active location shown in the header or case summary.
- At least one off-site evidence path per case.

## Current implementation gaps (code audit)
Last updated: 2026-01-08
- No case location roster or role tags exist yet; generator produces a single scene.
  - Code refs: src/noir/cases/truth_generator.py
- No travel/visit action or unlock flow; location_id is fixed for the whole case.
  - Code refs: src/noir/ui/app.py, src/noir/investigation/actions.py
- POIs and local leads are not gated by active location.
  - Code refs: src/noir/locations/profiles.py, src/noir/presentation/projector.py
- Evidence still originates at the primary scene only (no off-site evidence path).
  - Code refs: src/noir/presentation/projector.py, src/noir/cases/truth_generator.py

## Exit checklist
- [ ] Cases use 2 to 4 locations with clear roles.
- [ ] Locations unlock only through leads or evidence.
- [ ] Travel costs time/pressure and can force trade-offs.
- [ ] At least one key evidence item is off the primary scene.
- [ ] No map UI or open-world traversal exists.

Stop condition:
If multi-site cases create trade-offs without sprawl, stop.
