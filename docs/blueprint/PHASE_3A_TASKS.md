# Phase 3A - Investigative Depth (Forensic Observation)
Roadmap section: docs/blueprint/ROADMAP.md#phase-3a---investigative-depth-forensic-observation

Phase question:
Do crime scenes create meaningful, uncertain evidence without new mechanics?

Phase 3A is not:
- a forensic simulator
- a formula puzzle
- a new evidence class rollout
- a full ZOI traversal UI

## Scope (allowed)
- ZOI-lite: each scene exposes 3 to 5 points of interest.
- Forensic observations as evidence items (wound class, TOD band).
- Bounded uncertainty (bands and stages, not equations).
- Existing evidence classes only (physical/temporal/testimonial).
- Anchor objects for POIs (no guess-the-verb).
- Forensic clocks as stages (algor/rigor/livor bands).
- POI templates drive short, consistent scene descriptions.
- Location scope sets (zones + neighbor slots) and zone templates live in data/schemas/locations.yml.

## Core changes
1) Scene points of interest
- Each case surface 3 to 5 POIs.
- Searching a POI costs time and pressure.
- Each POI yields 0 to 2 evidence items.

2) Scene generation modes (top-down vs bottom-up)
Top-down (default for most cases):
- Pick a LocationProfile archetype and its scope_set.
- Instantiate zones from the scope_set (3 to 5 zones).
- Populate POIs per zone using zone_templates.
- Attach neighbor leads using neighbor_slots (if present).
- Result: coherent layout and consistent witness logic.

Bottom-up (use for character/pattern cases):
- Seed 3 to 5 POIs based on the crime's signature or character focus.
- Infer zones required to host those POIs (e.g., bed -> bedroom).
- Pull matching zone_templates for those zones.
- Attach neighbor leads that make sense for those zones.
- Result: scene is shaped by the crime, not the building.

Decision rule:
- Use top-down for most cases (baseline layout + consistent witnesses).
- Use bottom-up when the case signature or character focus should dominate the scene.

3) Forensic observations
- Wound class vocabulary: incision, laceration, puncture, gunshot.
- TOD as a time band, not a precise time.
- Rigor/livor as stage hints that widen or narrow the band.
- Environmental tags (temp/humidity) only widen or narrow bands.

4) Evidence phrasing (presentation only)
- Observations imply, never conclude.
- "Supports sharp force" is allowed, not "confirms sharp force."
- Uncertainty always named (lighting, contamination, delay).

## Constraints (non-negotiable)
- No new evidence classes.
- No equations or exact TOD calculation.
- No method certainty; method remains a hypothesis dimension.
- No new UI screens or micro-traversal systems.

## Deliverables
- POI list per scene with deterministic ordering.
- Forensic observation evidence items with confidence bands.
- TOD bands expressed as windows (e.g., 4 to 7 hours).
- At least two distinct POI paths per case.
- LocationProfile scope sets are used to surface optional neighbor leads.

## Exit checklist
- [ ] Each scene has 3 to 5 POIs with time/pressure costs.
- [ ] POIs produce evidence with confidence and uncertainty.
- [ ] TOD is expressed as a window, never a point.
- [ ] Wound class appears as observation, not conclusion.
- [ ] At least two POI paths yield different evidence mixes.
- [ ] No new evidence classes were introduced.

Stop condition:
If scenes feel investigatory and still uncertain, stop.
