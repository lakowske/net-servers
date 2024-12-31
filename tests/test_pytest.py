"""A simple test to check if pytest is working."""

from actions.build import build


def test_pytest():
    """A simple assertion to check if pytest is working."""
    a = 1
    assert a == 1
    build()
