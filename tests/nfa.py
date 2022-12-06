import typing

from vrc.automata.nfa import NFA
from vrc.automata import Automaton
from vrc.automata.regex import Empty, One, Sequence, Star, Alt


class TestNFA:
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
        assert not v.success()
        v.visit("A")
        assert not v.success()
        v.visit("X")
        assert v.success()
        v.visit("A")
        assert not v.success()
        v.visit("Y")
        assert v.success()
        v = a.visit()
        v.visit("B")
        assert v.success()
        v.visit("A")
        assert not v.success()

    def test_empty(self) -> None:
        a = NFA()
        v = a.visit()
        assert not v.success()
        v.visit("A")
        assert not v.success()

    def test_nfa(self) -> None:
        nfa = self.sample_nfa()
        self.sample_visit(nfa)

    def test_matches(self) -> None:
        nfa = self.sample_nfa()
        assert nfa.matches("AXAY")
        assert nfa.matches(["A", "foo"])
        assert nfa.matches(["B"])
        assert not nfa.matches(["foo"])
        assert not nfa.matches(["B", "A"])

    def test_lazy_dfa(self) -> None:
        dfa = self.sample_nfa().lazy_dfa()
        self.sample_visit(dfa)

    def test_empty_lazy_dfa(self) -> None:
        a = NFA().lazy_dfa()
        v = a.visit()
        assert not v.success()
        v.visit("A")
        assert not v.success()


class TestRegex:
    def test_empty(self) -> None:
        nfa = Empty().nfa()
        assert nfa.matches("")
        assert not nfa.matches("a")

    def test_one(self) -> None:
        nfa = One("a".__eq__).nfa()
        assert not nfa.matches("")
        assert nfa.matches("a")
        assert not nfa.matches("b")
        assert not nfa.matches("ab")
        assert not nfa.matches("ba")

    def test_sequence(self) -> None:
        nfa = Sequence().nfa()
        assert nfa.matches("")
        assert not nfa.matches("a")

        nfa = Sequence(One("a".__eq__)).nfa()
        assert not nfa.matches("")
        assert nfa.matches("a")
        assert not nfa.matches("b")
        assert not nfa.matches("ab")
        assert not nfa.matches("ba")

        nfa = Sequence(One("a".__eq__), Empty()).nfa()
        assert not nfa.matches("")
        assert nfa.matches("a")
        assert not nfa.matches("b")
        assert not nfa.matches("ab")
        assert not nfa.matches("ba")

        nfa = Sequence(One("a".__eq__), One("b".__eq__)).nfa()
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("b")
        assert nfa.matches("ab")
        assert not nfa.matches("ba")

        nfa = Sequence(Empty(), One("a".__eq__), One("b".__eq__)).nfa()
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("b")
        assert nfa.matches("ab")
        assert not nfa.matches("ba")

        nfa = Sequence(One("a".__eq__), One(lambda x: True), One("c".__eq__)).nfa()
        assert not nfa.matches("")
        assert not nfa.matches("a")
        assert not nfa.matches("ac")
        assert nfa.matches("abc")
        assert nfa.matches(["a", "foo", "c"])

    def test_alt(self) -> None:
        nfa = Alt(One("a".__eq__), One("b".__eq__)).nfa()
        assert not nfa.matches("")
        assert nfa.matches("a")
        assert nfa.matches("b")
        assert not nfa.matches("ab")
        assert not nfa.matches("ba")

    def test_star(self) -> None:
        nfa = Star(One("a".__eq__)).nfa()
        assert nfa.matches("")
        assert nfa.matches("a")
        assert nfa.matches("aaaaa")
        assert not nfa.matches("baaaa")
        assert not nfa.matches("aaaab")
