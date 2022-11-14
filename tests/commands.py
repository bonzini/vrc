import typing
import unittest
from vrc.automata import regex, Automaton
from vrc.cli.commands import PathsCommand


class RegexTest(unittest.TestCase):
    @staticmethod
    def parse(s: str) -> Automaton[typing.Any]:
        result: regex.RegexAST = next(iter(PathsCommand.PARSER(s))).value
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
