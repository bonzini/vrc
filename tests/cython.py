from vrc.cython.storer import Storer  # type: ignore
import pytest


@pytest.fixture
def storer() -> Storer:
    return Storer()


def test_initial(storer: Storer) -> None:
    assert storer.get_value() == 0


def test_set(storer: Storer) -> None:
    storer.set_value(42)
    assert storer.get_value() == 42
