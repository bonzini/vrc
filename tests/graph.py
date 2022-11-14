import unittest
from vrc.automata import regex
from vrc.graph import Graph
from vrc.util import Path


class VRCGraphTest(unittest.TestCase):
    def test_add_node(self) -> None:
        """Check creating nodes."""
        graph = Graph()
        graph.add_node("a")
        self.assertTrue(graph.has_node("a"))
        self.assertFalse(graph.is_node_external("a"))
        graph.add_external_node("b")
        self.assertTrue(graph.has_node("b"))
        self.assertTrue(graph.is_node_external("b"))

    def test_add_edge(self) -> None:
        """Check creating nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("a", "c", "ref")
        self.assertTrue(graph.edge_type("a", "b") == "call")
        self.assertTrue(graph.edge_type("a", "c") == "ref")

    def test_all_files(self) -> None:
        """Check creating nodes with files."""
        graph = Graph()
        graph.add_node("a", file="f.c")
        graph.add_node("b", file="g.c")
        self.assertEqual(sorted(graph.all_files()), ["f.c", "g.c"])

    def test_all_nodes(self) -> None:
        """Check retrieving the list of defined nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_external_node("b")
        self.assertEqual(sorted(graph.all_nodes(False)), ["a"])
        self.assertEqual(sorted(graph.all_nodes(True)), ["a", "b"])

    def test_edge_to_nonexisting_node(self) -> None:
        """Check creating an edge to a function that is not defined."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "call")
        self.assertTrue(graph.has_node("b"))
        self.assertTrue(graph.is_node_external("b"))
        self.assertTrue(graph.filter_node("a", False))
        self.assertFalse(graph.filter_node("b", False))
        self.assertTrue(graph.filter_node("b", True))

    def test_filter_edge_ref_ok(self) -> None:
        """Check ref_ok argument to filter_edge."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        graph.add_node("b")
        self.assertFalse(graph.filter_edge("a", "b", False))
        self.assertTrue(graph.filter_edge("a", "b", True))

    def test_hide_external_ref(self) -> None:
        """References to external symbols are hidden even with ref_ok=True."""
        graph = Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        self.assertTrue(graph.has_node("b"))
        self.assertFalse(graph.filter_edge("a", "b", True))

    def test_convert_external_node(self) -> None:
        """Check creating an edge before a function is defined."""
        graph = Graph()
        graph.add_external_node("a")
        self.assertTrue(graph.has_node("a"))
        graph.add_node("a")
        self.assertTrue(graph.has_node("a"))
        self.assertTrue(graph.filter_node("a", False))

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
        self.assertTrue(graph.filter_edge("a", "b", False))

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
        self.assertTrue(graph.filter_edge("b", "c", False))

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
        self.assertEqual(sorted(graph.callers("c", False)), ["a", "b"])

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
        self.assertEqual(sorted(graph.callers("c", True)), ["a", "b"])
        self.assertEqual(sorted(graph.callers("c", False)), ["b"])

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
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c", "d"])

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
        self.assertEqual(sorted(graph.callees("b", False, True)), ["c", "d"])
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c"])

    def test_callees_external_ok(self) -> None:
        """Check callees() for external nodes."""
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        self.assertEqual(sorted(graph.callees("b", True, False)), ["c", "d"])
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c"])

    def test_reset_filter(self) -> None:
        graph = Graph()
        graph.add_node("a")
        graph.omit_node("a")
        self.assertFalse(graph.filter_node("a", False))
        graph.reset_filter()
        self.assertTrue(graph.filter_node("a", False))

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
        self.assertFalse(graph.filter_edge("a", "c", False))
        self.assertTrue(graph.filter_edge("b", "c", False))
        self.assertFalse(graph.filter_node("a", False))
        self.assertTrue(graph.filter_node("c", False))
        self.assertFalse(graph.filter_node("d", False))

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
        self.assertFalse(graph.filter_edge("a", "c", False))
        self.assertTrue(graph.filter_edge("a", "d", False))
        self.assertTrue(graph.filter_node("a", False))
        self.assertFalse(graph.filter_node("b", False))
        self.assertFalse(graph.filter_node("c", False))

        # With an extra edge out of c the node does not disappear
        graph.reset_filter()
        graph.add_edge("c", "d", "call")
        graph.omit_callers("c")
        self.assertTrue(graph.filter_node("c", False))

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
        self.assertEqual(sorted(graph.callers("a", False)), ["e"])
        self.assertEqual(sorted(graph.callees("e", False, False)), ["a"])
        self.assertEqual(sorted(graph.callers("b", False)), ["c"])
        self.assertEqual(sorted(graph.callees("c", False, False)), ["b"])
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
        self.assertEqual(sorted(graph.callers("c", False)), ["b"])
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c"])
        # TODO: test that b -> c is the only edge left in the DOT output

    def test_labels(self) -> None:
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        self.assertEqual(sorted(graph.labels()), [])
        graph.add_label("a", "L1")
        self.assertEqual(sorted(graph.labels()), ["L1"])
        self.assertTrue(graph.has_label("a", "L1"))
        self.assertEqual(sorted(graph.labeled_nodes("L1")), ["a"])
        self.assertFalse(graph.has_label("a", "L2"))
        self.assertFalse(graph.has_label("b", "L1"))
        self.assertFalse(graph.has_label("c", "L2"))
        graph.add_label("b", "L1")
        self.assertEqual(sorted(graph.labeled_nodes("L1")), ["a", "b"])
        graph.add_label("b", "L2")
        self.assertEqual(sorted(graph.labels()), ["L1", "L2"])
        self.assertEqual(sorted(graph.labeled_nodes("L1")), ["a", "b"])
        self.assertEqual(sorted(graph.labeled_nodes("L2")), ["b"])
        graph.add_label("c", "L2")
        self.assertEqual(sorted(graph.labeled_nodes("L2")), ["b", "c"])

    def test_reset_labels(self) -> None:
        graph = Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_label("a", "L1")
        graph.add_label("b", "L2")
        self.assertEqual(sorted(graph.labels()), ["L1", "L2"])
        self.assertTrue(graph.has_label("a", "L1"))
        self.assertTrue(graph.has_label("b", "L2"))
        graph.reset_labels()
        self.assertFalse(graph.has_label("a", "L1"))
        self.assertFalse(graph.has_label("b", "L2"))
        self.assertEqual(sorted(graph.labels()), [])


class PathTest(unittest.TestCase):
    def test_path(self) -> None:
        p = Path()
        self.assertEqual(list(p), [])

        p.append("a")
        self.assertEqual(list(p), ["a"])

        p.append("b")
        self.assertEqual(list(p), ["b", "a"])

        p.pop()
        self.assertEqual(list(p), ["a"])

        p.append("b")
        p.append("c")
        save_p = iter(p)
        p.pop()
        self.assertEqual(list(p), ["b", "a"])
        p.append("d")
        self.assertEqual(list(save_p), ["c", "b", "a"])
        self.assertEqual(list(p), ["d", "b", "a"])
        p.pop()
        p.pop()
        self.assertEqual(list(p), ["a"])
        p.pop()
        self.assertEqual(list(p), [])

        p.append("b")
        p.append("c")
        self.assertEqual(list(p), ["c", "b"])
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
        self.assertTrue(graph.has_label("a", "L1"))
        self.assertTrue(not graph.has_label("b", "L1"))
        self.assertTrue(graph.has_label("c", "L1"))
        self.assertTrue(not graph.has_label("d", "L1"))

    def test_path_one_node(self) -> None:
        """Test a simple one-node path."""
        graph = self.graph_for_paths()
        ast = regex.One("a".__eq__)
        result = self.get_all_paths(graph, ast)
        self.assertEqual(result, [["a"]])

    def test_path_two_nodes(self) -> None:
        """Test a simple two-node path."""
        graph = self.graph_for_paths()
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.One("b".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        self.assertEqual(result, [["b", "a"]])

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
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ["d", "a"])
        self.assertEqual(result[1], ["d", "c", "b", "a"])

    def test_label(self) -> None:
        """Test a simple path with one-node path with labels."""
        graph = self.graph_for_paths()
        ast = regex.One(lambda x: graph.has_label(x, "L1"))
        result = self.get_all_paths(graph, ast)
        result = sorted(result, key=lambda x: x[0])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ["a"])
        self.assertEqual(result[1], ["c"])

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
        self.assertEqual(result, [["d", "c", "b", "a"]])

    def test_no_label(self) -> None:
        """Test a path with stars on labels."""
        graph = self.graph_for_paths()
        ast = regex.Sequence(
            regex.One("a".__eq__),
            regex.Star(regex.One(lambda x: not graph.has_label(x, "L1"))),
            regex.One("d".__eq__)
        )
        result = self.get_all_paths(graph, ast)
        self.assertEqual(result, [["d", "a"]])

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
        self.assertEqual(len(result), 2)
        # a->b is filtered out
        self.assertEqual(result[0], ["d", "a"])
        self.assertEqual(result[1], ["d", "c"])

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
        self.assertEqual(result, [["b", "a"]])

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
        self.assertEqual(result, [["d", "a"]])

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
        self.assertEqual(result, [["d", "a"]])

    def test_only(self) -> None:
        """Test filter_default = False."""
        graph = self.graph_for_paths()
        ast = regex.One(lambda x: graph.has_label(x, "L1"))
        graph.filter_default = False
        graph.keep_node("a")
        result = self.get_all_paths(graph, ast)
        self.assertEqual(len(result), 1)

        graph.keep_node("c")
        result = self.get_all_paths(graph, ast)
        self.assertEqual(len(result), 2)
