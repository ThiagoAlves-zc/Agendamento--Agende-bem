import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import connect  # noqa: E402
from seed import reset_demo  # noqa: E402

DEMO_DAY = date(2026, 10, 23)


@pytest.fixture
def db_file(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def conn(db_file):
    connection = connect(db_file)
    reset_demo(connection, DEMO_DAY)
    yield connection
    connection.close()
