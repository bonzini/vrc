import unittest
from vrc.automata.nfa import NFA


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

    def test_nfa(self) -> None:
        nfa = self.sample_nfa()
        v = nfa.visit()
        self.assertFalse(v.success())
        v.visit("A")
        self.assertFalse(v.success())
        v.visit("X")
        self.assertTrue(v.success())
        v.visit("A")
        self.assertFalse(v.success())
        v.visit("Y")
        self.assertTrue(v.success())
        v = nfa.visit()
        v.visit("B")
        self.assertTrue(v.success())
        v.visit("A")
        self.assertFalse(v.success())

    def test_matches(self) -> None:
        nfa = self.sample_nfa()
        self.assertTrue(nfa.matches("AXAY"))
        self.assertTrue(nfa.matches(["A", "foo"]))
        self.assertTrue(nfa.matches(["B"]))
        self.assertFalse(nfa.matches(["foo"]))
        self.assertFalse(nfa.matches(["B", "A"]))
