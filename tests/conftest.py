from pathlib import Path

import pytest

SAMPLE_DATA_DIR = Path(__file__).resolve().parents[1] / "sample-data" / "inspection-certs"


@pytest.fixture
def sample_data_dir() -> Path:
    return SAMPLE_DATA_DIR
