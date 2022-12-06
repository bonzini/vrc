import pytest
import typing
import vrc.graph

_graph_classes = ['PythonGraph']
if 'CythonGraph' in vrc.graph.__dict__:
    _graph_classes += ['CythonGraph']


@pytest.fixture(params=_graph_classes)
def graph_class(request: typing.Any) -> typing.Type[vrc.graph.GraphMixin]:
    return vrc.graph.__dict__[request.param]    # type: ignore
