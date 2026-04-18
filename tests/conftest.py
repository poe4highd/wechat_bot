import pytest
from pathlib import Path
from storage.db import Database

@pytest.fixture
def tmp_db(tmp_path):
    return Database(tmp_path / "test.db")
