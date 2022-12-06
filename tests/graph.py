from vrc.automata import regex
from vrc.graph import Graph
from vrc.util import Path


class TestVRCGraph:
    def test_add_node(self) -> None:
        """Check creating nodes."""
        graph = Graph()
        graph.add_node("a")
        assert graph.has_node("a")
        assert not graph.is_node_external("a")
        graph.add_external_node("b")
        assert graph.has_node("b")
        assert graph.is_node_external("b")

    def test_add_edge(self) -> None:
        """Check creating nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("a", "c", "ref")
        assert graph.edge_type("a", "b") == "call"
        assert graph.edge_type("a", "c") == "ref"

    def test_all_files(self) -> None:
        """Check creating nodes with files."""
        graph = Graph()
        graph.add_node("a", file="f.c")
        graph.add_node("b", file="g.c")
        assert sorted(graph.all_files()) == ["f.c", "g.c"]

    def test_all_nodes(self) -> None:
        """Check retrieving the list of defined nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_external_node("b")
        assert sorted(graph.all_nodes(False)) == ["a"]
        assert sorted(graph.all_nodes(True)) == ["a", "b"]

    def test_edge_to_nonexisting_node(self) -> None:
        """Check creating an edge to a function that is not defined."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "call")
        assert graph.has_node("b")
        assert graph.is_node_external("b")
        assert graph.filter_node("a", False)
        assert not graph.filter_node("b", False)
        assert graph.filter_node("b", True)

    def test_filter_edge_ref_ok(self) -> None:
        """Check ref_ok argument to filter_edge."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        graph.add_node("b")
        assert not graph.filter_edge("a", "b", False)
        assert graph.filter_edge("a", "b", True)

    def test_hide_external_ref(self) -> None:
        """References to external symbols are hidden even with ref_ok=True."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        assert graph.has_node("b")
        assert not graph.filter_edge("a", "b", True)

    def test_convert_external_node(self) -> None:
        """Check creating an edge before a function is defined."""
        graph = Graph()
        graph.add_external_node("a")
        assert graph.has_node("a")
        graph.add_node("a")
        assert graph.has_node("a")
        assert graph.filter_node("a", False)

    def test_callers_of_omitted_node(self) -> None:
        """Check edges."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_node("b")
        graph.omit_node("c")
        assert graph.filter_edge("a", "b", False)

    def test_callees_of_omitted_node(self) -> None:
        """Check creating an edge before a function is defined."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_node("a")
        graph.omit_node("b")
        assert graph.filter_edge("b", "c", False)

    def test_callers(self) -> None:
        """Check callers(), "call" edges only."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        assert sorted(graph.callers("c", False)) == ["a", "b"]

    def test_callers_ref_ok(self) -> None:
        """Check callers(), "call" and "ref"."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "ref")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        assert sorted(graph.callers("c", True)) == ["a", "b"]
        assert sorted(graph.callers("c", False)) == ["b"]

    def test_callees(self) -> None:
        """Check callees(), "call" edges to non-external nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        assert sorted(graph.callees("b", False, False)) == ["c", "d"]

    def test_callees_ref_ok(self) -> None:
        """Check callees(), "call" and "ref" edges."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "ref")
        assert sorted(graph.callees("b", False, True)) == ["c", "d"]
        assert sorted(graph.callees("b", False, False)) == ["c"]

    def test_callees_external_ok(self) -> None:
        """Check callees() for external nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        assert sorted(graph.callees("b", True, False)) == ["c", "d"]
        assert sorted(graph.callees("b", False, False)) == ["c"]

    def test_reset_filter(self) -> None:
        graph = Graph()
        graph.add_node("a")
        graph.omit_node("a")
        assert not graph.filter_node("a", False)
        graph.reset_filter()
        assert graph.filter_node("a", False)

    def test_omit_callees(self) -> None:
        graph = Graph()
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

    def test_omit_callers(self) -> None:
        graph = Graph()
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

    def test_omit_callees_check_callers(self) -> None:
        graph = Graph()
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

    def test_omit_callers_check_callees(self) -> None:
        graph = Graph()
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

    def test_labels(self) -> None:
        graph = Graph()
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

    def test_reset_labels(self) -> None:
        graph = Graph()
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


class TestPath:
    def test_path(self) -> None:
        p = Path()
        assert list(p) == []

        p.append("a")
        assert list(p) == ["a"]

        p.append("b")
        assert list(p) == ["b", "a"]

        p.pop()
        assert list(p) == ["a"]

        p.append("b")
        p.append("c")
        save_p = iter(p)
        p.pop()
        assert list(p) == ["b", "a"]
        p.append("d")
        assert list(save_p) == ["c", "b", "a"]
        assert list(p) == ["d", "b", "a"]
        p.pop()
        p.pop()
        assert list(p) == ["a"]
        p.pop()
        assert list(p) == []

        p.append("b")
        p.append("c")
        assert list(p) == ["c", "b"]
        p.pop()
        p.pop()

    @staticmethod
    def graph_for_paths() -> Graph:
        graph = Graph()
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
    def get_all_paths(graph: Graph, ast: regex.RegexAST,
                      external_ok: bool = True, ref_ok: bool = True) -> list[list[str]]:
        return [list(path) for path in graph.paths(ast.nfa().lazy_dfa(), external_ok, ref_ok)]

    def test_sample_graph(self) -> None:
        graph = self.graph_for_paths()
        assert graph.has_label("a", "L1")
        assert not graph.has_label("b", "L1")
        assert graph.has_label("c", "L1")
        assert not graph.has_label("d", "L1")

    def test_path_one_node(self) -> None:
        """Test a simple one-node path."""
        graph = self.graph_for_paths()
        ast = regex.One("a".__eq__)
        result = self.get_all_paths(graph, ast)
        assert result == [["a"]]

    def test_path_two_nodes(self) -> None:
        """Test a simple two-node path."""
        graph = self.graph_for_paths()
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.One("b".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["b", "a"]]

    def test_path_star(self) -> None:
        """Test a simple path with multiple-length solutions."""
        graph = self.graph_for_paths()
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

    def test_label(self) -> None:
        """Test a simple path with one-node path with labels."""
        graph = self.graph_for_paths()
        ast = regex.One(lambda x: graph.has_label(x, "L1"))
        result = self.get_all_paths(graph, ast)
        result = sorted(result, key=lambda x: x[0])
        assert len(result) == 2
        assert result[0] == ["a"]
        assert result[1] == ["c"]

    def test_complex(self) -> None:
        """Test a complex path with labels and stars."""
        graph = self.graph_for_paths()
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One(lambda x: graph.has_label(x, "L1")),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "c", "b", "a"]]

    def test_no_label(self) -> None:
        """Test a path with stars on labels."""
        graph = self.graph_for_paths()
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: not graph.has_label(x, "L1"))),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "a"]]

    def test_no_ref(self) -> None:
        """Test filtering out references."""
        graph = self.graph_for_paths()
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

    def test_no_external(self) -> None:
        """Test filtering out external nodes."""
        graph = self.graph_for_paths()
        ast = regex.Sequence(
            regex.One(lambda x: graph.has_label(x, "L1")),
            regex.One(lambda x: not graph.has_label(x, "L1")),
        )
        result = self.get_all_paths(graph, ast, external_ok=False)
        result = sorted(result, key=lambda x: len(x))
        # a->d, c->d are filtered out
        assert result == [["b", "a"]]

    def test_omit_callees(self) -> None:
        """Test filtering of edges."""
        graph = self.graph_for_paths()
        graph.omit_callees("b")
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "a"]]

    def test_omit_node(self) -> None:
        """Test filtering of nodes."""
        graph = self.graph_for_paths()
        graph.omit_node("b")
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: True)),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        assert result == [["d", "a"]]

    def test_only(self) -> None:
        """Test filter_default = False."""
        graph = self.graph_for_paths()
        ast = regex.One(lambda x: graph.has_label(x, "L1"))
        graph.filter_default = False
        graph.keep_node("a")
        result = self.get_all_paths(graph, ast)
        assert len(result) == 1

        graph.keep_node("c")
        result = self.get_all_paths(graph, ast)
        assert len(result) == 2
