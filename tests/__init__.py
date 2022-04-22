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
