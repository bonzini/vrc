import typing
import unittest
from vrc.automata.nfa import NFA
from vrc.automata import Automaton
from vrc.automata.regex import Empty, One, Sequence, Star, Alt


class NFATest(unittest.TestCase):
    @staticmethod
    def sample_nfa() -> NFA:
        """Return an NFA for ``(A.)*|B``."""
        nfa = NFA()
        s1 = nfa.add_state()
        s2 = nfa.add_state()
        s3 = nfa.add_state()
        nfa.add_epsilon_transition(s1, s2)
        nfa.add_epsilon_transition(s1, s3)
        s4 = nfa.add_state()
        s41 = nfa.add_state()
        s5 = nfa.add_state()
        nfa.mark_final(s5)
        nfa.add_transition(s2, "A".__eq__, s4)
        nfa.add_transition(s4, lambda x: True, s41)
        nfa.add_epsilon_transition(s41, s2)
        nfa.add_epsilon_transition(s41, s5)
        nfa.add_transition(s3, "B".__eq__, s5)
        return nfa

    def sample_visit(self, a: Automaton[typing.Any]) -> None:
        v = a.visit()
        self.assertFalse(v.success())
        v.visit("A")
        self.assertFalse(v.success())
        v.visit("X")
        self.assertTrue(v.success())
        v.visit("A")
        self.assertFalse(v.success())
        v.visit("Y")
        self.assertTrue(v.success())
        v = a.visit()
        v.visit("B")
        self.assertTrue(v.success())
        v.visit("A")
        self.assertFalse(v.success())

    def test_empty(self) -> None:
        a = NFA()
        v = a.visit()
        self.assertFalse(v.success())
        v.visit("A")
        self.assertFalse(v.success())

    def test_nfa(self) -> None:
        nfa = self.sample_nfa()
        self.sample_visit(nfa)

    def test_matches(self) -> None:
        nfa = self.sample_nfa()
        self.assertTrue(nfa.matches("AXAY"))
        self.assertTrue(nfa.matches(["A", "foo"]))
        self.assertTrue(nfa.matches(["B"]))
        self.assertFalse(nfa.matches(["foo"]))
        self.assertFalse(nfa.matches(["B", "A"]))

    def test_lazy_dfa(self) -> None:
        dfa = self.sample_nfa().lazy_dfa()
        self.sample_visit(dfa)

    def test_empty_lazy_dfa(self) -> None:
        a = NFA().lazy_dfa()
        v = a.visit()
        self.assertFalse(v.success())
        v.visit("A")
        self.assertFalse(v.success())


class RegexTest(unittest.TestCase):
    def test_empty(self) -> None:
        nfa = Empty().nfa()
        self.assertTrue(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))

    def test_one(self) -> None:
        nfa = One("a".__eq__).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertFalse(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

    def test_sequence(self) -> None:
        nfa = Sequence().nfa()
        self.assertTrue(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))

        nfa = Sequence(One("a".__eq__)).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertFalse(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

        nfa = Sequence(One("a".__eq__), Empty()).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertFalse(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

        nfa = Sequence(One("a".__eq__), One("b".__eq__)).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertTrue(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

        nfa = Sequence(Empty(), One("a".__eq__), One("b".__eq__)).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("b"))
        self.assertTrue(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

        nfa = Sequence(One("a".__eq__), One(lambda x: True), One("c".__eq__)).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertFalse(nfa.matches("a"))
        self.assertFalse(nfa.matches("ac"))
        self.assertTrue(nfa.matches("abc"))
        self.assertTrue(nfa.matches(["a", "foo", "c"]))

    def test_alt(self) -> None:
        nfa = Alt(One("a".__eq__), One("b".__eq__)).nfa()
        self.assertFalse(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertTrue(nfa.matches("b"))
        self.assertFalse(nfa.matches("ab"))
        self.assertFalse(nfa.matches("ba"))

    def test_star(self) -> None:
        nfa = Star(One("a".__eq__)).nfa()
        self.assertTrue(nfa.matches(""))
        self.assertTrue(nfa.matches("a"))
        self.assertTrue(nfa.matches("aaaaa"))
        self.assertFalse(nfa.matches("baaaa"))
        self.assertFalse(nfa.matches("aaaab"))
