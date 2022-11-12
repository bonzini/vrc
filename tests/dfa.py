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

    def sample_visit(self, dfa: DFA) -> None:
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

    def test_dfa(self) -> None:
        dfa = self.sample_dfa()
        self.sample_visit(dfa)

    def test_matches(self) -> None:
        dfa = self.sample_dfa()
        assert dfa.matches("A")
        assert dfa.matches(["A", "X"])
        assert not dfa.matches(["A", "foo"])
        assert dfa.matches("B")
        assert not dfa.matches("BA")

    def test_reverse(self) -> None:
        dfa = self.sample_dfa().reverse()
        v = dfa.visit()
        self.assertFalse(v.success())
        v.visit("X")
        self.assertFalse(v.success())
        v.visit("X")
        self.assertFalse(v.success())
        v.visit("A")
        self.assertTrue(v.success())
        v.visit("X")
        self.assertFalse(v.success())
        v = dfa.visit()
        v.visit("B")
        self.assertTrue(v.success())
        v.visit("B")
        self.assertFalse(v.success())
        v = dfa.visit()
        v.visit("A")
        self.assertTrue(v.success())
        v.visit("B")
        self.assertFalse(v.success())

    def test_minimal(self) -> None:
        from vrc.automata.regex import Alt, Sequence, Star, One
        zero = One("0".__eq__)
        one = One("1".__eq__)
        # build an automaton that recognizes the multiples of three
        # it has very nice minimal DFA representation using only
        # three states, one for each remainder.  The transitions are
        # s_i -> 0 -> s_(2i mod 3) and s_i -> 1 -> s_(2i+1 mod 3).
        r = Star(Alt(zero,
                     Star(Sequence(one,
                                   Star(Sequence(zero,
                                                 Star(one),
                                                 Star(Sequence(zero, zero)),
                                                 zero)),
                                   one))))
        dfa = r.nfa().dfa(["0", "1"])
        self.assertTrue(dfa.matches(""))
        self.assertTrue(dfa.matches("0"))
        self.assertTrue(dfa.matches("11"))
        self.assertTrue(dfa.matches("110"))
        self.assertTrue(dfa.matches("1001"))
        self.assertTrue(dfa.matches("1100"))
        self.assertTrue(dfa.matches("1111"))
        self.assertTrue(dfa.matches("10010"))
        dfa = dfa.minimal()
        self.assertTrue(dfa.matches(""))
        self.assertTrue(dfa.matches("0"))
        self.assertTrue(dfa.matches("11"))
        self.assertTrue(dfa.matches("110"))
        self.assertTrue(dfa.matches("1001"))
        self.assertTrue(dfa.matches("1100"))
        self.assertTrue(dfa.matches("1111"))
        self.assertTrue(dfa.matches("10010"))
        self.assertEqual(dfa.add_state(), 3)
