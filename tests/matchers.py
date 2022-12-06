import typing

from vrc.automata import Automaton
from vrc.graph import Graph
from vrc.matchers import (
    Matcher, MatchByName, MatchByRegex, MatchLabel, MatchAnd, MatchOr, MatchNot,
    MatchCallers, MatchCallees, parse_nodespec, parse_pathspec
)


def sample_graph() -> Graph:
    g = Graph()
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


class TestMatcher:
    def do_test(self, m: Matcher, results: list[str], g: Graph = sample_graph()) -> None:
        assert sorted(list(m.match_nodes_in_graph(g))) == sorted(results)

        c = m.as_callable(g)
        for node in g.all_nodes(True):
            assert c(node) == (node in results)

    def do_parse_test(self, s: str, results: list[str], g: Graph = sample_graph()) -> None:
        parse_result = parse_nodespec(s)
        self.do_test(parse_result, results, g)

    def test_by_name(self) -> None:
        self.do_test(MatchByName("a"), ["a"])
        self.do_test(MatchByName("blah"), [])
        self.do_test(MatchByName("f(int, float)"), ["f(int, float)"])

    def test_by_regex(self) -> None:
        self.do_test(MatchByRegex("a$"), ["a", "func_a"])
        self.do_test(MatchByRegex("^func_"), ["func_a"])

    def test_label(self) -> None:
        self.do_test(MatchLabel("L1"), ["l1", "l12"])
        self.do_test(MatchLabel("L2"), ["l2", "l12"])
        self.do_test(MatchLabel("L3"), [])

    def test_and(self) -> None:
        self.do_test(MatchAnd(), ["a", "b", "f(int, float)", "func_a", "l1", "l2", "l12"])
        self.do_test(MatchAnd(MatchLabel("L1"), MatchLabel("L2")), ["l12"])

    def test_not(self) -> None:
        self.do_test(MatchNot(MatchAnd()), [])
        self.do_test(MatchNot(MatchLabel("L1")), ["a", "b", "f(int, float)", "func_a", "l2"])
        self.do_test(MatchAnd(MatchNot(MatchLabel("L1")), MatchNot(MatchLabel("L2"))), ["a", "b", "f(int, float)", "func_a"])
        self.do_test(MatchNot(MatchOr(MatchLabel("L1"), MatchLabel("L2"))), ["a", "b", "f(int, float)", "func_a"])

    def test_or(self) -> None:
        self.do_test(MatchOr(), [])
        self.do_test(MatchOr(MatchLabel("L1"), MatchByName("l2")), ["l1", "l2", "l12"])

    def test_callers(self) -> None:
        self.do_test(MatchCallers(MatchByName("b")), ["a"])

    def test_callees(self) -> None:
        g = Graph()
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

        not_co = MatchNot(MatchLabel("CO"))
        self.do_test(not_co, ["b", "d", "e"], g)
        self.do_parse_test("[!CO]", ["b", "d", "e"], g)

        co_callees = MatchCallees(MatchLabel("CO"))
        self.do_test(co_callees, ["b", "c", "d"], g)
        self.do_parse_test("[CO:callees]", ["b", "c", "d"], g)

        not_co_callees = MatchCallees(MatchNot(MatchLabel("CO")))
        self.do_test(not_co_callees, ["c", "e"], g)
        self.do_parse_test("[!CO:callees]", ["c", "e"], g)

        co_candidate = MatchAnd(not_co, co_callees, MatchNot(not_co_callees))
        self.do_test(co_candidate, ["b", "d"], g)
        self.do_parse_test("[!CO,CO:callees,![!CO:callees]]", ["b", "d"], g)

    def test_parsers(self) -> None:
        self.do_parse_test("a", ["a"])
        self.do_parse_test("blah", [])
        self.do_parse_test("[]", ["a", "b", "f(int, float)", "func_a", "l1", "l2", "l12"])
        self.do_parse_test("[L1,L2]", ["l12"])
        self.do_parse_test("[L1|L2]", ["l1", "l2", "l12"])
        self.do_parse_test("![L1|L2]", ["a", "b", "f(int, float)", "func_a"])
        self.do_parse_test("[!L1,!L2]", ["a", "b", "f(int, float)", "func_a"])
        self.do_parse_test("/^func_/", ["func_a"])
        self.do_parse_test('[/^f/,!"func_a"]', ["f(int, float)"])
        self.do_parse_test('"f(int, float)"', ["f(int, float)"])

        self.do_parse_test('b:callers', ["a"])
        self.do_parse_test('["b":callers]', ["a"])
        self.do_parse_test('["b"]:callers', ["a"])

    def test_spaces(self) -> None:
        self.do_parse_test(" [L1,L2]", ["l12"])
        self.do_parse_test("[ L1,L2]", ["l12"])
        self.do_parse_test("[L1 ,L2]", ["l12"])
        self.do_parse_test("[L1, L2]", ["l12"])
        self.do_parse_test("[L1,L2 ]", ["l12"])
        self.do_parse_test("[L1,L2] ", ["l12"])

        self.do_parse_test('b :callers ', ["a"])
        self.do_parse_test('["b" :callers]', ["a"])
        self.do_parse_test('["b":callers ]', ["a"])
        self.do_parse_test('["b"] :callers', ["a"])
        self.do_parse_test('["b"]:callers ', ["a"])


class TestRegex:
    @staticmethod
    def parse(s: str) -> Automaton[typing.Any]:
        g = Graph()
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
