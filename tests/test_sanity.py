"""Sanity checks that the pinned toolchain is actually in use."""

import sys

import pytest


@pytest.mark.unit
def test_environment_sane() -> None:
    """The interpreter must be the uv-pinned Python 3.11."""
    assert sys.version_info[:2] == (3, 11)
