import pytest
import typing

from vrc.automata import regex
from vrc.graph import GraphMixin
from vrc.util import Path


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
        graph.add_node(i)
    return graph


@pytest.fixture
def graph_with_edges(many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> GraphMixin:
    graph = graph_class()
    for i in many_strings:
        graph.add_node(i)
    for n, i in enumerate(graph.all_nodes(False)):
        for j in range([1, 13, 2, 3, 2, 7, 0][n % 7]):
            graph.add_edge(i, many_strings[(n + j + 1) * 17 * j % 10000], "call")
    return graph


@pytest.mark.usefixtures("graph_class")
class TestVRCGraph:
    def test_add_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating nodes."""
        graph = graph_class()
        graph.add_node("a")
        assert graph.has_node("a")
        assert not graph.is_node_external("a")
        graph.add_external_node("b")
        assert graph.has_node("b")
        assert graph.is_node_external("b")

    def test_add_edge(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating nodes."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("a", "c", "ref")
        assert graph.edge_type("a", "b") == "call"
        assert graph.edge_type("a", "c") == "ref"

    def test_all_files(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating nodes with files."""
        graph = graph_class()
        graph.add_node("a", file="f.c")
        graph.add_node("b", file="g.c")
        assert sorted(graph.all_files()) == ["f.c", "g.c"]

    def test_all_nodes(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check retrieving the list of defined nodes."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_external_node("b")
        assert sorted(graph.all_nodes(False)) == ["a"]
        assert sorted(graph.all_nodes(True)) == ["a", "b"]

    def test_edge_to_nonexisting_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating an edge to a function that is not defined."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_edge("a", "b", "call")
        assert graph.has_node("b")
        assert graph.is_node_external("b")
        assert graph.filter_node("a", False)
        assert not graph.filter_node("b", False)
        assert graph.filter_node("b", True)

    def test_filter_edge_ref_ok(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check ref_ok argument to filter_edge."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        graph.add_node("b")
        assert not graph.filter_edge("a", "b", False)
        assert graph.filter_edge("a", "b", True)

    def test_hide_external_ref(self, graph_class: typing.Type[GraphMixin]) -> None:
        """References to external symbols are hidden even with ref_ok=True."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        assert graph.has_node("b")
        assert not graph.filter_edge("a", "b", True)

    def test_convert_external_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating an edge before a function is defined."""
        graph = graph_class()
        graph.add_external_node("a")
        assert graph.has_node("a")
        graph.add_node("a")
        assert graph.has_node("a")
        assert graph.filter_node("a", False)

    def test_callers_of_omitted_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check edges."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_node("b")
        graph.omit_node("c")
        assert graph.filter_edge("a", "b", False)

    def test_callees_of_omitted_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check creating an edge before a function is defined."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_node("a")
        graph.omit_node("b")
        assert graph.filter_edge("b", "c", False)

    def test_callers(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callers(), "call" edges only."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        assert sorted(graph.callers("c", False)) == ["a", "b"]

    def test_callers_ref_ok(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callers(), "call" and "ref"."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "ref")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        assert sorted(graph.callers("c", True)) == ["a", "b"]
        assert sorted(graph.callers("c", False)) == ["b"]

    def test_callees(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callees(), "call" edges to non-external nodes."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        assert sorted(graph.callees("b", False, False)) == ["c", "d"]

    def test_callees_ref_ok(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callees(), "call" and "ref" edges."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "ref")
        assert sorted(graph.callees("b", False, True)) == ["c", "d"]
        assert sorted(graph.callees("b", False, False)) == ["c"]

    def test_callees_external_ok(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Check callees() for external nodes."""
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        assert sorted(graph.callees("b", True, False)) == ["c", "d"]
        assert sorted(graph.callees("b", False, False)) == ["c"]

    def test_reset_filter(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.omit_node("a")
        assert not graph.filter_node("a", False)
        graph.reset_filter()
        assert graph.filter_node("a", False)

    def test_omit_callees(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("a", "d", "call")
        graph.omit_callees("a")
        assert not graph.filter_edge("a", "c", False)
        assert graph.filter_edge("b", "c", False)
        assert not graph.filter_node("a", False)
        assert graph.filter_node("c", False)
        assert not graph.filter_node("d", False)

    def test_omit_callers(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("a", "d", "call")
        graph.omit_callers("c")
        assert not graph.filter_edge("a", "c", False)
        assert graph.filter_edge("a", "d", False)
        assert graph.filter_node("a", False)
        assert not graph.filter_node("b", False)
        assert not graph.filter_node("c", False)

        # With an extra edge out of c the node does not disappear
        graph.reset_filter()
        graph.add_edge("c", "d", "call")
        graph.omit_callers("c")
        assert graph.filter_node("c", False)

    def test_omit_callees_check_callers(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("e")
        graph.add_edge("a", "b", "call")
        graph.add_edge("c", "b", "call")
        graph.add_edge("e", "a", "call")
        graph.omit_callees("a")
        assert sorted(graph.callers("a", False)) == ["e"]
        assert sorted(graph.callees("e", False, False)) == ["a"]
        assert sorted(graph.callers("b", False)) == ["c"]
        assert sorted(graph.callees("c", False, False)) == ["b"]
        # TODO: test that c -> b and e -> a are in the DOT output

    def test_omit_callers_check_callees(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("e")
        graph.add_edge("e", "a", "call")
        graph.add_edge("b", "a", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_callers("a")
        assert sorted(graph.callers("c", False)) == ["b"]
        assert sorted(graph.callees("b", False, False)) == ["c"]
        # TODO: test that b -> c is the only edge left in the DOT output

    def test_labels(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        assert sorted(graph.labels()) == []
        graph.add_label("a", "L1")
        assert sorted(graph.labels()) == ["L1"]
        assert graph.has_label("a", "L1")
        assert sorted(graph.labeled_nodes("L1")) == ["a"]
        assert not graph.has_label("a", "L2")
        assert not graph.has_label("b", "L1")
        assert not graph.has_label("c", "L2")
        graph.add_label("b", "L1")
        assert sorted(graph.labeled_nodes("L1")) == ["a", "b"]
        graph.add_label("b", "L2")
        assert sorted(graph.labels()) == ["L1", "L2"]
        assert sorted(graph.labeled_nodes("L1")) == ["a", "b"]
        assert sorted(graph.labeled_nodes("L2")) == ["b"]
        graph.add_label("c", "L2")
        assert sorted(graph.labeled_nodes("L2")) == ["b", "c"]

    def test_reset_labels(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_label("a", "L1")
        graph.add_label("b", "L2")
        assert sorted(graph.labels()) == ["L1", "L2"]
        assert graph.has_label("a", "L1")
        assert graph.has_label("b", "L2")
        graph.reset_labels()
        assert not graph.has_label("a", "L1")
        assert not graph.has_label("b", "L2")
        assert sorted(graph.labels()) == []

    def test_benchmark_add_external_node(self, benchmark: typing.Any, many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> None:
        def func() -> None:
            graph = graph_class()
            for i in many_strings:
                graph.add_external_node(i)
        benchmark(func)

    def test_benchmark_add_node(self, benchmark: typing.Any, many_strings: list[str], graph_class: typing.Type[GraphMixin]) -> None:
        def func() -> None:
            graph = graph_class()
            for i in many_strings:
                graph.add_node(i)
        benchmark(func)

    def test_benchmark_define_node(self, benchmark: typing.Any, many_strings: list[str], graph_with_external_nodes: GraphMixin) -> None:
        def func() -> None:
            for n, i in enumerate(many_strings):
                graph_with_external_nodes.add_node(i, file=["a.c", "b.c", "c.c"][n % 3])
        benchmark(func)

    def test_benchmark_add_edge(self, benchmark: typing.Any, many_strings: list[str], graph_with_nodes: GraphMixin) -> None:
        def func() -> None:
            for n, i in enumerate(graph_with_nodes.all_nodes(False)):
                for j in range([1, 13, 2, 3, 2, 7, 0][n % 7]):
                    graph_with_nodes.add_edge(i, many_strings[(n + j + 1) * 17 % 10000], "call")
        benchmark(func)

    def test_benchmark_add_label(self, benchmark: typing.Any, many_strings: list[str], graph_with_nodes: GraphMixin) -> None:
        def func() -> None:
            for n, i in enumerate(graph_with_nodes.all_nodes(True)):
                graph_with_nodes.add_label(many_strings[(n + 1) * 17 % 10000], "L1")
                graph_with_nodes.add_label(many_strings[(n + 1) * 2 % 10000], "L2")
                graph_with_nodes.add_label(many_strings[(n + 1) * 23 % 5000 * 2], "L3")
        benchmark(func)

    def test_benchmark_edges(self, benchmark: typing.Any, many_strings: list[str], graph_with_edges: GraphMixin) -> None:
        def func() -> None:
            for i in graph_with_edges.all_nodes(True):
                graph_with_edges.callers(i, False)
        benchmark(func)


@pytest.mark.usefixtures("graph_class")
class TestPath:
    def test_path(self) -> None:
        p = Path()
        assert list(p) == []

        p.append("a", 0, iter([]), 123)
        assert list(p) == ["a"]

        p.append("b", 0, iter([]), 123)
        assert list(p) == ["b", "a"]

        p.first = p.first.next                   # type: ignore
        assert list(p) == ["a"]

        p.append("b", 0, iter([]), 123)
        p.append("c", 0, iter([]), 123)
        save_p = iter(p)
        p.first = p.first.next                   # type: ignore
        assert list(p) == ["b", "a"]
        p.append("d", 0, iter([]), 123)
        assert list(save_p) == ["c", "b", "a"]
        assert list(p) == ["d", "b", "a"]
        p.first = p.first.next                   # type: ignore
        p.first = p.first.next                   # type: ignore
        assert list(p) == ["a"]
        p.first = p.first.next                   # type: ignore
        assert list(p) == []

        p.append("b", 0, iter([]), 123)
        p.append("c", 0, iter([]), 123)
        assert list(p) == ["c", "b"]

    @staticmethod
    def graph_for_paths(graph_class: typing.Type[GraphMixin]) -> GraphMixin:
        graph = graph_class()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_external_node("d")
        graph.add_edge("a", "b", "ref")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        graph.add_edge("a", "d", "call")
        graph.add_label("a", "L1")
        graph.add_label("c", "L1")
        return graph

    @staticmethod
    def get_all_paths(graph: GraphMixin, ast: regex.RegexAST,
                      external_ok: bool = True, ref_ok: bool = True,
                      limit: typing.Optional[int] = None) -> list[list[str]]:
        return [list(path) for path in graph.paths(ast.nfa().lazy_dfa(), external_ok, ref_ok, limit)]

    def test_sample_graph(self, graph_class: typing.Type[GraphMixin]) -> None:
        graph = self.graph_for_paths(graph_class)
        assert graph.has_label("a", "L1")
        assert not graph.has_label("b", "L1")
        assert graph.has_label("c", "L1")
        assert not graph.has_label("d", "L1")

    def test_path_one_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test a simple one-node path."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.One("a".__eq__)
        result = self.get_all_paths(graph, ast)
        assert result == [["a"]]

    def test_path_two_nodes(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test a simple two-node path."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.One("b".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["b", "a"]]

    def test_path_star(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test a simple path with multiple-length solutions."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        result = sorted(result, key=lambda x: len(x))
        assert len(result) == 2
        assert result[0] == ["d", "a"]
        assert result[1] == ["d", "c", "b", "a"]

    def test_path_limit(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test interrupting a path search."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast, limit=1)
        result = sorted(result, key=lambda x: len(x))
        if len(result[0]) == 2:
            assert result[0] == ["d", "a"]
        else:
            assert result[0] == ["d", "c", "b", "a"]

    def test_label(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test a simple path with one-node path with labels."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.One(lambda x: graph.has_label(x, "L1"))
        result = self.get_all_paths(graph, ast)
        result = sorted(result, key=lambda x: x[0])
        assert len(result) == 2
        assert result[0] == ["a"]
        assert result[1] == ["c"]

    def test_complex(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test a complex path with labels and stars."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One(lambda x: graph.has_label(x, "L1")),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "c", "b", "a"]]

    def test_no_label(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test a path with stars on labels."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: not graph.has_label(x, "L1"))),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "a"]]

    def test_no_ref(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test filtering out references."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One(lambda x: graph.has_label(x, "L1")),
            regex.One(lambda x: not graph.has_label(x, "L1")),
        )
        result = self.get_all_paths(graph, ast, ref_ok=False)
        result = sorted(result, key=lambda x: len(x))
        result = sorted(result, key=lambda x: x[-1])
        assert len(result) == 2
        # a->b is filtered out
        assert result[0] == ["d", "a"]
        assert result[1] == ["d", "c"]

    def test_no_external(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test filtering out external nodes."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.Sequence(
            regex.One(lambda x: graph.has_label(x, "L1")),
            regex.One(lambda x: not graph.has_label(x, "L1")),
        )
        result = self.get_all_paths(graph, ast, external_ok=False)
        result = sorted(result, key=lambda x: len(x))
        # a->d, c->d are filtered out
        assert result == [["b", "a"]]

    def test_omit_callees(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test filtering of edges."""
        graph = self.graph_for_paths(graph_class)
        graph.omit_callees("b")
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "a"]]

    def test_omit_node(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test filtering of nodes."""
        graph = self.graph_for_paths(graph_class)
        graph.omit_node("b")
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "a"]]

    def test_only(self, graph_class: typing.Type[GraphMixin]) -> None:
        """Test filter_default = False."""
        graph = self.graph_for_paths(graph_class)
        ast = regex.One(lambda x: graph.has_label(x, "L1"))
        graph.filter_default = False
        graph.keep_node("a")
        result = self.get_all_paths(graph, ast)
        assert len(result) == 1

        graph.keep_node("c")
        result = self.get_all_paths(graph, ast)
        assert len(result) == 2
