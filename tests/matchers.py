import typing
import unittest
from vrc.automata import regex, Automaton
from vrc.graph import Graph
from vrc.matchers import Matcher, MatchByName, MatchByRegex, MatchLabel, MatchAnd, MatchOr, MatchNot, Node, Path


class MatcherTest(unittest.TestCase):
    @staticmethod
    def sample_graph() -> Graph:
        g = Graph()
        g.add_node("a")
        g.add_node("b")
        g.add_node("func_a")
        g.add_node("l1")
        g.add_node("l2")
        g.add_node("l12")
        g.add_node("f(int, float)")

        g.add_label("l1", "L1")
        g.add_label("l2", "L2")
        g.add_label("l12", "L1")
        g.add_label("l12", "L2")
        return g

    def do_test(self, m: Matcher, results: list[str]) -> None:
        g = MatcherTest.sample_graph()
        self.assertEqual(sorted(list(m.match_nodes_in_graph(g))), sorted(results))

        c = m.as_callable(g)
        for node in ["a", "b", "func_a", "l1", "l2", "l12"]:
            self.assertEqual(c(node), node in results)

    def do_parse_test(self, s: str, results: list[str]) -> None:
        parse_result = next(iter(Node(s)))
        self.do_test(parse_result.value, results)

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


class RegexTest(unittest.TestCase):
    @staticmethod
    def parse(s: str) -> Automaton[typing.Any]:
        g = Graph()
        result: regex.RegexAST = next(iter(Path(g)(s))).value
        return result.nfa().lazy_dfa()

    def test_one(self) -> None:
        nfa = self.parse("a")
        self.assertFalse(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertFalse(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

        nfa = self.parse("foo")
        self.assertFalse(nfa.matches("foo"))
        self.assertTrue(nfa.matches(["foo"]))

    def test_sequence(self) -> None:
        nfa = self.parse("a b")
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertTrue(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

        nfa = self.parse("a b c")
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("ac"))
        self.assertTrue(nfa.matches("abc"))
        self.assertFalse(nfa.matches(["abc"]))

        nfa = self.parse("a foo c")
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("ac"))
        self.assertFalse(nfa.matches("afooc"))
        self.assertTrue(nfa.matches(["a", "foo", "c"]))

    def test_alt(self) -> None:
        nfa = self.parse("a b |c")
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertTrue(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))
        self.assertTrue(nfa.matches("c"))

    def test_star(self) -> None:
        nfa = self.parse("a*")
        self.assertTrue(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertTrue(nfa.matches("aaaaa"))
        self.assertFalse(nfa.matches("baaaa"))
        self.assertFalse(nfa.matches("aaaab"))

    def test_regex(self) -> None:
        nfa = self.parse("/^func_/")
        self.assertFalse(nfa.matches([]))
        self.assertTrue(nfa.matches(["func_a"]))
        self.assertFalse(nfa.matches(["_func_a"]))

        nfa = self.parse("a /blah/ c")
        self.assertFalse(nfa.matches("ablahc"))
        self.assertTrue(nfa.matches(["a", "xblahy", "c"]))

    def test_any(self) -> None:
        nfa = self.parse("a [] c")
        print(nfa)
        self.assertFalse(nfa.matches(["a", "c"]))
        self.assertTrue(nfa.matches(["a", "b", "c"]))
        self.assertFalse(nfa.matches(["a", "b", "b", "c"]))
