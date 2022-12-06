import pytest
import typing

from vrc.graph import GraphMixin


@pytest.fixture
def many_strings() -> list[str]:
    return [str(i) for i in range(1, 10001)]


@pytest.fixture
def graph_with_external_nodes(many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> GraphMixin:
    graph = graph_class()
    for i in many_strings:
        graph.add_external_node(i)
    return graph


@pytest.fixture
def graph_with_nodes(many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> GraphMixin:
    graph = graph_class()
    for i in many_strings:
        graph._add_node(graph.add_external_node(i))
    return graph


@pytest.fixture
def graph_with_edges(many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> GraphMixin:
    graph = graph_class()
    for i in many_strings:
        graph._add_node(graph.add_external_node(i))
    for n in range(0, 10000):
        for j in range([1, 13, 2, 3, 2, 7, 0][n % 7]):
            graph._add_edge(n, (n + j + 1) * 17 * j % 10000, True)
    return graph


@pytest.mark.usefixtures("graph_class")
class TestVRCGraph:
    def test_add_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating nodes."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        assert graph._get_node("a") == (0, "a")
        assert not graph._is_node_external(0)
        assert graph.add_external_node("b") == 1
        assert graph._get_node("b") == (1, "b")
        assert graph._name_by_index(1) == "b"
        assert graph._is_node_external(1)
        assert graph._get_node("c") == (None, None)

    def test_add_edge(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating nodes."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_node(graph.add_external_node("c"))
        graph._add_edge(0, 1, True)
        graph._add_edge(0, 2, False)
        assert graph._has_call_edge(0, 1)
        assert not graph._has_call_edge(0, 2)
        assert not graph._has_call_edge(1, 2)
        assert graph._has_edge(0, 1, False)
        assert not graph._has_edge(0, 2, False)
        assert not graph._has_edge(1, 2, False)
        assert graph._has_edge(0, 1, True)
        assert graph._has_edge(0, 2, True)
        assert not graph._has_edge(1, 2, True)

    def test_all_files(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating nodes with files."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"), file="f.c")
        graph._add_node(graph.add_external_node("b"), file="g.c")
        graph._add_node(graph.add_external_node("c"), file="g.c")
        assert sorted(graph._all_nodes_for_file("g.c")) == [1, 2]
        assert sorted(graph.all_files()) == ["f.c", "g.c"]

    def test_convert_external_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating an edge before a function is defined."""
        graph = graph_class()
        assert graph.add_external_node("a") == 0
        assert graph._is_node_external(0)
        assert graph._get_node("a") == (0, "a")
        graph._add_node(0)
        assert graph._get_node("a") == (0, "a")
        assert not graph._is_node_external(0)

    def test_callers(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callers(), "call" edges only."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_node(graph.add_external_node("c"))
        graph._add_node(graph.add_external_node("d"))
        graph._add_edge(0, 2, True)
        graph._add_edge(1, 2, True)
        graph._add_edge(2, 3, True)
        assert sorted(graph._get_callers(2)) == [0, 1]
        assert sorted(graph._get_callers(2)) == [0, 1]

    def test_callers_ref_ok(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callers(), "call" and "ref"."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_node(graph.add_external_node("c"))
        graph._add_node(graph.add_external_node("d"))
        graph._add_edge(0, 2, False)
        graph._add_edge(1, 2, True)
        graph._add_edge(2, 3, True)
        assert sorted(graph._get_callers(2)) == [0, 1]

    def test_callees(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callees(), "call" edges to non-external nodes."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_node(graph.add_external_node("c"))
        graph._add_node(graph.add_external_node("d"))
        graph._add_edge(0, 1, True)
        graph._add_edge(1, 2, True)
        graph._add_edge(1, 3, True)
        assert sorted(graph._get_callees(1)) == [2, 3]

    def test_callees_ref_ok(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callees(), "call" and "ref" edges."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph._add_edge(0, 1, True)
        graph._add_edge(1, 2, True)
        graph._add_edge(1, 3, False)
        assert sorted(graph._get_callees(1)) == [2, 3]

    def test_callees_external(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callees() for external nodes."""
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_node(graph.add_external_node("c"))
        graph.add_external_node("d")
        graph._add_edge(0, 1, True)
        graph._add_edge(1, 2, True)
        graph._add_edge(1, 3, True)
        assert sorted(graph._get_callees(1)) == [2, 3]

    def test_labels(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_node(graph.add_external_node("c"))
        assert sorted(graph.labels()) == []
        assert sorted(graph._all_nodes_for_label("L1")) == []
        graph._add_label(0, "L1")
        assert sorted(graph.labels()) == ["L1"]
        assert graph._has_label(0, "L1")
        assert sorted(graph._all_nodes_for_label("L1")) == [0]
        assert not graph._has_label(0, "L2")
        assert not graph._has_label(1, "L1")
        assert not graph._has_label(2, "L2")
        graph._add_label(1, "L1")
        assert sorted(graph._all_nodes_for_label("L1")) == [0, 1]
        graph._add_label(1, "L2")
        assert sorted(graph.labels()) == ["L1", "L2"]
        assert sorted(graph._all_nodes_for_label("L1")) == [0, 1]
        assert sorted(graph._all_nodes_for_label("L2")) == [1]
        graph._add_label(2, "L2")
        assert sorted(graph._all_nodes_for_label("L2")) == [1, 2]

    def test_reset_labels(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph._add_node(graph.add_external_node("a"))
        graph._add_node(graph.add_external_node("b"))
        graph._add_label(0, "L1")
        graph._add_label(1, "L2")
        assert sorted(graph.labels()) == ["L1", "L2"]
        assert graph._has_label(0, "L1")
        assert graph._has_label(1, "L2")
        graph.reset_labels()
        assert sorted(graph.labels()) == []
        assert not graph._has_label(0, "L1")
        assert not graph._has_label(1, "L2")

    def test_username(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_external_node("a")
        assert graph._get_node("a") == (0, "a")
        assert graph.name("a") == "a"
        graph._add_node(0, username="a()", file="f.c", line=456)

        assert graph._get_node("a") == (0, "a()")
        assert graph._get_node("a()") == (0, "a()")
        assert graph.name("a") == "a()"

        assert graph.add_external_node("a()") == 0

    def test_node_object(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_external_node("a")
        n = graph._node_by_index(0)
        assert n.name == "a"
        assert n.external
        assert n.username is None
        assert n.file is None
        assert n.line is None
        graph._add_node(0, username="a()", file="f.c", line=456)
        assert not n.external
        assert n.username == "a()"
        assert n.file == "f.c"
        assert n.line == 456
        graph._add_node(0, username="a()", file="f.c", line=456)

    def test_benchmark_ll_add_external_node(self, benchmark: typing.Any, many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> None:
        def func() -> None:
            graph = graph_class()
            for i in many_strings:
                graph.add_external_node(i)
        benchmark(func)

    def test_benchmark_ll_define_node(self, benchmark: typing.Any, graph_with_external_nodes: GraphMixin) -> None:
        def func() -> None:
            for n in range(0, 10000):
                graph_with_external_nodes._add_node(n, file=["a.c", "b.c", "c.c"][n % 3])
        benchmark(func)

    def test_benchmark_ll_add_edge(self, benchmark: typing.Any, graph_with_nodes: GraphMixin) -> None:
        def func() -> None:
            for n in range(0, 10000):
                for j in range([1, 13, 2, 3, 2, 7, 0][n % 7]):
                    graph_with_nodes._add_edge(n, (n + j + 1) * 17 % 10000, True)
        benchmark(func)

    def test_benchmark_ll_add_label(self, benchmark: typing.Any, graph_with_nodes: GraphMixin) -> None:
        def func() -> None:
            for n in range(0, 10000):
                graph_with_nodes._add_label((n + 1) * 17 % 10000, "L1")
                graph_with_nodes._add_label((n + 1) * 2 % 10000, "L2")
                graph_with_nodes._add_label((n + 1) * 23 % 5000 * 2, "L3")
        benchmark(func)

    def test_benchmark_ll_edges(self, benchmark: typing.Any, graph_with_edges: GraphMixin) -> None:
        def func() -> None:
            for n in range(0, 10000):
                i = iter(graph_with_edges._get_callers(n))
                try:
                    while True:
                        next(i)
                except StopIteration:
                    pass
        benchmark(func)
