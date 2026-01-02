# Phase 3 SQL and Names (Decision Note)

## SQL database timing

You only need SQL the moment you want durable continuity across multiple cases
and sessions (world state, case history, recurring people/locations, nemesis
history, analytics). That is Phase 3 territory.

Rule:
- Phase 0-2: in-memory state + a JSON save/load is enough.
- Phase 3: bring in SQLite (SQLModel/SQLAlchemy) because the world remembers.
- Phase 4+: expand schema only if the game proves it needs it.

If Phase 3 is starting soon, add SQLite at the start of Phase 3 to avoid
retrofits.

## Phase 3 minimal SQL schema

Do not store the entire truth graph yet. SQL is a memory spine, not the brain.

Tables:

1) world_state
- id (always 1)
- trust_level
- pressure_level
- date/time tick (optional)
- nemesis_activity (optional)

2) case_history
- case_id
- seed
- started_at_tick, ended_at_tick
- outcome (clean/shaky/failed)
- trust_delta
- pressure_delta
- notes (short text)

3) people_index (optional)
- person_id
- first_name
- last_name
- archetype (optional)
- created_in_case_id

## Pressure rename

If the meter tracks institutional or social forces, use Pressure. This keeps the
loop readable and avoids a wanted-level feel.

Example:
Time: 2/8 | Pressure: 1/6

## CSV names (for naming generator)

If you meant CSV: yes, add it now. Names are low-risk and reduce robotic output.

Suggested files:

data/names/first_names.csv
Columns: name, gender (optional), origin (optional), weight (optional)

data/names/last_names.csv
Columns: name, origin (optional), weight (optional)

Example rows:
- Morgan,neutral,uk,1
- Aisha,female,ng,1
- Daniel,male,uk,1

Last names:
- Iverson,uk,1
- Adeyemi,ng,1
- Okafor,ng,1

Name generator rules:
- Default display: First Last
- Alternate format: Last, First for official files
- Internal person_id stays stable

Suggested structure:

data/
  names/
    first_names.csv
    last_names.csv
src/
  game/
    naming/
      name_loader.py
      name_generator.py
