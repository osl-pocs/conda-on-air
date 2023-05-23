"""Tests for `conda-on-air` package."""
from pathlib import Path

import pytest

from conda_on_air import CondaOnAir


def test_config_reading(config_path):
    """Test the config reading"""
    conair = CondaOnAir(config_path)
    assert conair.config_data


def test_run(config_path):
    """Test the config reading"""
    CondaOnAir(config_path).run()
