import pytest
import typing

from vrc.graph import GraphMixin
from vrc.loaders import ResolutionError
import vrc.graph


@pytest.fixture
def cython_loader() -> typing.Any:
    try:
        import vrc.loaders.cython_loader as cython_loader   # type: ignore
        return cython_loader
    except ModuleNotFoundError:
        pytest.skip('cython_loader not found')


@pytest.fixture
def cython_graph() -> typing.Type[GraphMixin]:
    if 'CythonGraph' in vrc.graph.__dict__:
        return vrc.graph.__dict__['CythonGraph']   # type: ignore
    else:
        pytest.skip('cython_graph not found')


def test_empty_args(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(ResolutionError):
        cython_loader.build_graph("test.c", [], cython_graph(), True)


def test_invalid_type_args(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(TypeError):
        cython_loader.build_graph("test.c", ["abc", 123, "def"], cython_graph(), True)


def test_none_filename(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(ResolutionError):
        cython_loader.build_graph(None, [], cython_graph(), True)


def test_invalid_type_filename(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(TypeError):
        cython_loader.build_graph(123, [], cython_graph(), True)


def test_none_out_path(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(TypeError):
        cython_loader.build_graph("test.c", [], None, True)


def test_invalid_type_out_path(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(TypeError):
        cython_loader.build_graph([], 123, True)


def test_dummy(cython_loader: typing.Any, cython_graph: typing.Type[GraphMixin]) -> None:
    with pytest.raises(ResolutionError):
        cython_loader.build_graph("nonexistent.c", ["nonexistent.c"], cython_graph(), True)
