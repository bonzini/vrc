import unittest
from vrc.automata.dfa import DFA


class DFATest(unittest.TestCase):
    @staticmethod
    def sample_dfa() -> DFA:
        dfa = DFA()
        s1 = dfa.add_state()
        s2 = dfa.add_state()
        s3 = dfa.add_state()
        dfa.add_transition(s1, "A", s2)
        dfa.add_transition(s2, "X", s2)
        dfa.mark_final(s2)
        dfa.add_transition(s1, "B", s3)
        dfa.mark_final(s3)
        return dfa

    def test_dfa(self) -> None:
        dfa = self.sample_dfa()
        v = dfa.visit()
        self.assertFalse(v.success())
        v.visit("A")
        self.assertTrue(v.success())
        v.visit("X")
        self.assertTrue(v.success())
        v.visit("X")
        self.assertTrue(v.success())
        v = dfa.visit()
        v.visit("B")
        self.assertTrue(v.success())
        v.visit("A")
        self.assertFalse(v.success())

    def test_matches(self) -> None:
        dfa = self.sample_dfa()
        assert dfa.matches("A")
        assert dfa.matches(["A", "X"])
        assert not dfa.matches(["A", "foo"])
        assert dfa.matches("B")
        assert not dfa.matches("BA")
