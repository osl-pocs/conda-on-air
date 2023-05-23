from pathlib import Path

import pytest


@pytest.fixture
def config_path():
    return (Path(__file__).parent.parent / '.conda-on-air.yaml').resolve()
