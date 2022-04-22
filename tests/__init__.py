import unittest
import vrc


class VRCGraphTest(unittest.TestCase):
    def test_edge_to_nonexisting_node(self):
        """Check creating an edge to a function that is not defined."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "call")
        self.assertTrue(graph.has_node("b"))
        self.assertTrue(graph.filter_node("a", False))
        self.assertFalse(graph.filter_node("b", False))
        self.assertTrue(graph.filter_node("b", True))

    def test_filter_edge_ref_ok(self):
        """Check ref_ok argument to filter_edge."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        graph.add_node("b")
        self.assertFalse(graph.filter_edge("a", "b", False))
        self.assertTrue(graph.filter_edge("a", "b", True))

    def test_hide_external_ref(self):
        """References to external symbols are hidden even with ref_ok=True."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_edge("a", "b", "ref")
        self.assertTrue(graph.has_node("b"))
        self.assertFalse(graph.filter_edge("a", "b", True))

    def test_convert_external_node(self):
        """Check creating an edge before a function is defined."""
        graph = vrc.Graph()
        graph.add_external_node("a")
        self.assertTrue(graph.has_node("a"))
        graph.add_node("a")
        self.assertTrue(graph.has_node("a"))
        self.assertTrue(graph.filter_node("a", False))

    def test_callers_of_omitted_node(self):
        """Check edges."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_node("b")
        graph.omit_node("c")
        self.assertTrue(graph.filter_edge("a", "b", False))

    def test_callees_of_omitted_node(self):
        """Check creating an edge before a function is defined."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.omit_node("a")
        graph.omit_node("b")
        self.assertTrue(graph.filter_edge("b", "c", False))

    def test_callers(self):
        """Check callers(), "call" edges only."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        self.assertEqual(sorted(graph.callers("c", False)), ["a", "b"])

    def test_callers_ref_ok(self):
        """Check callers(), "call" and "ref"."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "c", "ref")
        graph.add_edge("b", "c", "call")
        graph.add_edge("c", "d", "call")
        self.assertEqual(sorted(graph.callers("c", True)), ["a", "b"])
        self.assertEqual(sorted(graph.callers("c", False)), ["b"])

    def test_callees(self):
        """Check callees(), "call" edges to non-external nodes."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c", "d"])

    def test_callees_ref_ok(self):
        """Check callees(), "call" and "ref" edges."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_node("d")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "ref")
        self.assertEqual(sorted(graph.callees("b", False, True)), ["c", "d"])
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c"])

    def test_callees_external_ok(self):
        """Check callees() for external nodes."""
        graph = vrc.Graph()
        graph.add_node("a")
        graph.add_node("b")
        graph.add_node("c")
        graph.add_edge("a", "b", "call")
        graph.add_edge("b", "c", "call")
        graph.add_edge("b", "d", "call")
        self.assertEqual(sorted(graph.callees("b", True, False)), ["c", "d"])
        self.assertEqual(sorted(graph.callees("b", False, False)), ["c"])

    def test_reset_filter(self):
        graph = vrc.Graph()
        graph.add_node("a")
        graph.omit_node("a")
        self.assertFalse(graph.filter_node("a", False))
        graph.reset_filter()
        self.assertTrue(graph.filter_node("a", False))

    def test_omit_callees(self):
        graph = vrc.Graph()
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

    def test_omit_callers(self):
        graph = vrc.Graph()
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

    def test_omit_callees_check_callers(self):
        graph = vrc.Graph()
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

    def test_omit_callers_check_callees(self):
        graph = vrc.Graph()
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
