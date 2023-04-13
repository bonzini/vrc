import pytest
import typing

from vrc.automata import Automaton
from vrc.graph import GraphMixin, PythonGraph
from vrc.matchers import (
    Matcher, MatchByName, MatchByRegex, MatchLabel, MatchAnd, MatchOr, MatchNot,
    MatchAllCallers, MatchAllCallees, MatchCallers, MatchCallees,
    parse_nodespec, parse_pathspec
)


@pytest.fixture
def sample_graph(graph_class: typing.Type[GraphMixin]) -> GraphMixin:
    g = graph_class()
    g.add_node("a")
    g.add_node("b")
    g.add_node("func_a")
    g.add_node("l1")
    g.add_node("l2")
    g.add_node("l12")
    g.add_node("f(int, float)")

    g.add_edge("a", "b", "call")
    g.add_edge("func_a", "b", "ref")

    g.add_label("l1", "L1")
    g.add_label("l2", "L2")
    g.add_label("l12", "L1")
    g.add_label("l12", "L2")
    return g


@pytest.fixture
def complex_graph(graph_class: typing.Type[GraphMixin]) -> GraphMixin:
    g = graph_class()
    g.add_node("a")
    g.add_node("b")
    g.add_node("c")
    g.add_node("d")
    g.add_node("e")
    g.add_label("a", "CO")
    g.add_edge("a", "b", "call")
    g.add_edge("a", "c", "call")
    g.add_label("c", "CO")
    g.add_edge("c", "d", "call")
    g.add_edge("d", "c", "call")
    g.add_edge("d", "e", "call")
    return g


class TestMatcher:
    def do_test(self, g: GraphMixin, m: Matcher, results: list[str]) -> None:
        assert sorted(list(m.match_nodes_in_graph(g))) == sorted(results)

        c = m.as_callable(g)
        for node in g.all_nodes(True):
            assert c(node) == (node in results)

        c = m.optimize().as_callable(g)
        for node in g.all_nodes(True):
            assert c(node) == (node in results)

    def do_parse_test(self, g: GraphMixin, s: str, results: list[str]) -> None:
        parse_result = parse_nodespec(s)
        self.do_test(g, parse_result, results)

    def test_by_name(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchByName("a"), ["a"])
        self.do_test(sample_graph, MatchByName("blah"), [])
        self.do_test(sample_graph, MatchByName("f(int, float)"), ["f(int, float)"])

    def test_by_regex(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchByRegex("a$"), ["a", "func_a"])
        self.do_test(sample_graph, MatchByRegex("^func_"), ["func_a"])

    def test_label(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchLabel("L1"), ["l1", "l12"])
        self.do_test(sample_graph, MatchLabel("L2"), ["l2", "l12"])
        self.do_test(sample_graph, MatchLabel("L3"), [])

    def test_and(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchAnd(), ["a", "b", "f(int, float)", "func_a", "l1", "l2", "l12"])
        self.do_test(sample_graph, MatchAnd(MatchLabel("L1"), MatchLabel("L2")), ["l12"])

    def test_not(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchNot(MatchAnd()), [])
        self.do_test(sample_graph, MatchNot(MatchLabel("L1")), ["a", "b", "f(int, float)", "func_a", "l2"])
        self.do_test(sample_graph, MatchAnd(MatchNot(MatchLabel("L1")), MatchNot(MatchLabel("L2"))), ["a", "b", "f(int, float)", "func_a"])
        self.do_test(sample_graph, MatchNot(MatchOr(MatchLabel("L1"), MatchLabel("L2"))), ["a", "b", "f(int, float)", "func_a"])

    def test_or(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchOr(), [])
        self.do_test(sample_graph, MatchOr(MatchLabel("L1"), MatchByName("l2")), ["l1", "l2", "l12"])

    def test_callers(self, sample_graph: GraphMixin) -> None:
        self.do_test(sample_graph, MatchCallers(MatchByName("b")), ["a"])

    def test_all_callers(self, complex_graph: GraphMixin) -> None:
        self.do_test(complex_graph, MatchAllCallers(MatchByName("d")), ["a", "c", "d"])

    def test_all_callees(self, complex_graph: GraphMixin) -> None:
        self.do_test(complex_graph, MatchAllCallees(MatchByName("d")), ["c", "d", "e"])

    def test_callees(self, complex_graph: GraphMixin) -> None:
        not_co = MatchNot(MatchLabel("CO"))
        self.do_test(complex_graph, not_co, ["b", "d", "e"])
        self.do_parse_test(complex_graph, "[!CO]", ["b", "d", "e"])

        co_callees = MatchCallees(MatchLabel("CO"))
        self.do_test(complex_graph, co_callees, ["b", "c", "d"])
        self.do_parse_test(complex_graph, "[CO:callees]", ["b", "c", "d"])

        not_co_callees = MatchCallees(MatchNot(MatchLabel("CO")))
        self.do_test(complex_graph, not_co_callees, ["c", "e"])
        self.do_parse_test(complex_graph, "[!CO:callees]", ["c", "e"])

        co_candidate = MatchAnd(not_co, co_callees, MatchNot(not_co_callees))
        self.do_test(complex_graph, co_candidate, ["b", "d"])
        self.do_parse_test(complex_graph, "[!CO,CO:callees,![!CO:callees]]", ["b", "d"])

    def test_parsers(self, sample_graph: GraphMixin) -> None:
        self.do_parse_test(sample_graph, "a", ["a"])
        self.do_parse_test(sample_graph, "blah", [])
        self.do_parse_test(sample_graph, "[]", ["a", "b", "f(int, float)", "func_a", "l1", "l2", "l12"])
        self.do_parse_test(sample_graph, "[L1,L2]", ["l12"])
        self.do_parse_test(sample_graph, "[L1|L2]", ["l1", "l2", "l12"])
        self.do_parse_test(sample_graph, "![L1|L2]", ["a", "b", "f(int, float)", "func_a"])
        self.do_parse_test(sample_graph, "[!L1,!L2]", ["a", "b", "f(int, float)", "func_a"])
        self.do_parse_test(sample_graph, "/^func_/", ["func_a"])
        self.do_parse_test(sample_graph, '[/^f/,!"func_a"]', ["f(int, float)"])
        self.do_parse_test(sample_graph, '"f(int, float)"', ["f(int, float)"])

        self.do_parse_test(sample_graph, 'b:callers', ["a"])
        self.do_parse_test(sample_graph, '["b":callers]', ["a"])
        self.do_parse_test(sample_graph, '["b"]:callers', ["a"])

    def test_spaces(self, sample_graph: GraphMixin) -> None:
        self.do_parse_test(sample_graph, " [L1,L2]", ["l12"])
        self.do_parse_test(sample_graph, "[ L1,L2]", ["l12"])
        self.do_parse_test(sample_graph, "[L1 ,L2]", ["l12"])
        self.do_parse_test(sample_graph, "[L1, L2]", ["l12"])
        self.do_parse_test(sample_graph, "[L1,L2 ]", ["l12"])
        self.do_parse_test(sample_graph, "[L1,L2] ", ["l12"])

        self.do_parse_test(sample_graph, 'b :callers ', ["a"])
        self.do_parse_test(sample_graph, '["b" :callers]', ["a"])
        self.do_parse_test(sample_graph, '["b":callers ]', ["a"])
        self.do_parse_test(sample_graph, '["b"] :callers', ["a"])
        self.do_parse_test(sample_graph, '["b"]:callers ', ["a"])


class TestRegex:
    @staticmethod
    def parse(s: str) -> Automaton[typing.Any]:
        g = PythonGraph()
        return parse_pathspec(g, s).nfa().lazy_dfa()

    def test_one(self) -> None:
        nfa = self.parse("a")
        assert not nfa.matches("")
        assert nfa.matches("a")
        assert not nfa.matches("b")
        assert not nfa.matches("ab")
        assert not nfa.matches("ba")

        nfa = self.parse("foo")
        assert not nfa.matches("foo")
        assert nfa.matches(["foo"])

    def test_sequence(self) -> None:
        nfa = self.parse("a b")
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("b")
        assert nfa.matches("ab")
        assert not nfa.matches("ba")

        nfa = self.parse("a b c")
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("ac")
        assert nfa.matches("abc")
        assert not nfa.matches(["abc"])

        nfa = self.parse("a foo c")
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("ac")
        assert not nfa.matches("afooc")
        assert nfa.matches(["a", "foo", "c"])

    def test_alt(self) -> None:
        nfa = self.parse("a b |c")
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("b")
        assert nfa.matches("ab")
        assert not nfa.matches("ba")
        assert nfa.matches("c")

    def test_star(self) -> None:
        nfa = self.parse("a*")
        assert nfa.matches("")
        assert nfa.matches("a")
        assert nfa.matches("aaaaa")
        assert not nfa.matches("baaaa")
        assert not nfa.matches("aaaab")

    def test_regex(self) -> None:
        nfa = self.parse("/^func_/")
        assert not nfa.matches([])
        assert nfa.matches(["func_a"])
        assert not nfa.matches(["_func_a"])

        nfa = self.parse("a /blah/ c")
        assert not nfa.matches("ablahc")
        assert nfa.matches(["a", "xblahy", "c"])

    def test_any(self) -> None:
        nfa = self.parse("a [] c")
        print(nfa)
        assert not nfa.matches(["a", "c"])
        assert nfa.matches(["a", "b", "c"])
        assert not nfa.matches(["a", "b", "b", "c"])
