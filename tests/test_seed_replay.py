from noir.cases import truth_generator
from noir.cases.truth_generator import generate_case
from noir.presentation.evidence import CCTVReport, ForensicObservation, ForensicsResult, WitnessStatement
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def _reset_generators() -> None:
    truth_generator._NAME_GENERATOR = None


def _evidence_fingerprint(item) -> tuple:
    if isinstance(item, WitnessStatement):
        return (
            "witness",
            item.summary,
            item.source,
            item.confidence.value,
            item.statement,
            item.reported_time_window,
            tuple(item.uncertainty_hooks),
        )
    if isinstance(item, CCTVReport):
        return (
            "cctv",
            item.summary,
            item.source,
            item.confidence.value,
            item.time_window,
            len(item.observed_person_ids),
        )
    if isinstance(item, ForensicsResult):
        return (
            "forensics_result",
            item.summary,
            item.source,
            item.confidence.value,
            item.finding,
            item.method_category,
        )
    if isinstance(item, ForensicObservation):
        return (
            "forensic_observation",
            item.summary,
            item.source,
            item.confidence.value,
            item.observation,
            item.tod_window,
            item.wound_class,
        )
    raise AssertionError(f"Unhandled evidence type: {type(item)!r}")


def _event_metadata_fingerprint(metadata: dict) -> tuple:
    stable_items = []
    for key, value in sorted(metadata.items()):
        if key in {"weapon_id", "found_victim_id"}:
            continue
        stable_items.append((key, value))
    return tuple(stable_items)


def _case_fingerprint(seed: int) -> tuple:
    _reset_generators()
    truth, case_facts = generate_case(Rng(seed), case_id=f"case_{seed}")
    presentation = project_case(truth, Rng(seed))
    people = sorted(
        (person.name, tuple(sorted(tag.value for tag in person.role_tags)))
        for person in truth.people.values()
    )
    locations = sorted((location.name, location.district) for location in truth.locations.values())
    events = sorted(
        (event.kind.value, event.timestamp, _event_metadata_fingerprint(event.metadata))
        for event in truth.events.values()
    )
    meta = (
        truth.case_meta.get("method_category"),
        truth.case_meta.get("motive_category"),
        truth.case_meta.get("access_path"),
        truth.case_meta.get("location_name"),
    )
    evidence = tuple(_evidence_fingerprint(item) for item in presentation.evidence)
    return people, locations, events, meta, case_facts["case_archetype"], evidence


def test_same_seed_replays_the_same_case_and_projection() -> None:
    assert _case_fingerprint(42) == _case_fingerprint(42)


def test_different_seeds_diverge() -> None:
    assert _case_fingerprint(7) != _case_fingerprint(8)