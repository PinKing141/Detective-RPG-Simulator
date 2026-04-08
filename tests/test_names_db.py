import sqlite3
import warnings

from noir.naming.names_db import load_name_generator
from noir.util.rng import Rng


def test_load_name_generator_falls_back_for_non_sqlite_file(tmp_path) -> None:
    broken_db = tmp_path / "names.db"
    broken_db.write_text("version https://git-lfs.github.com/spec/v1\n", encoding="ascii")

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        generator = load_name_generator(broken_db)

    assert generator.db is None
    assert generator.full_name(Rng(7))
    assert captured
    assert "Falling back to built-in names" in str(captured[0].message)


def test_load_name_generator_falls_back_for_wrong_schema(tmp_path) -> None:
    broken_db = tmp_path / "names.db"
    conn = sqlite3.connect(broken_db)
    conn.execute("CREATE TABLE misc (name TEXT)")
    conn.commit()
    conn.close()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        generator = load_name_generator(broken_db)

    assert generator.db is None
    assert generator.full_name(Rng(11))
    assert captured
    assert "Falling back to built-in names" in str(captured[0].message)