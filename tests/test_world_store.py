from noir.persistence.db import WorldStore
from noir.world.state import CaseRecord


def test_load_world_state_initializes_row_without_losing_existing_records(tmp_path) -> None:
    path = tmp_path / "world.db"
    store = WorldStore(path)
    store.record_case(
        CaseRecord(
            case_id="case_001",
            seed=101,
            district="harbor",
            started_tick=0,
            ended_tick=3,
            outcome="failed",
            trust_delta=-1,
            pressure_delta=1,
            notes=["Pattern file notes a compromised method."],
        )
    )
    store.conn.execute(
        """
        INSERT INTO people_index (
            person_id,
            name,
            role_tag,
            country_of_origin,
            religion_affiliation,
            religion_observance,
            community_connectedness,
            created_in_case_id,
            last_seen_case_id,
            last_seen_tick
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "person-1",
            "Mina Vale",
            "witness",
            None,
            None,
            None,
            None,
            "case_001",
            "case_001",
            3,
        ),
    )
    store.conn.commit()

    state = store.load_world_state()

    assert [record.case_id for record in state.case_history] == ["case_001"]
    assert state.people_index["person-1"].name == "Mina Vale"
    store.close()