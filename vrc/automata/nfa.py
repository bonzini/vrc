#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from . import Automaton
from abc import ABCMeta
import dataclasses
import typing


Matcher = typing.Callable[[str], bool]


class StateSet(typing.Protocol, typing.Sized, typing.Iterable[int], metaclass=ABCMeta):
    pass


class LazyDFA(Automaton[typing.Optional[int]]):
    nfa: 'NFA'
    nfa_states: list[frozenset[int]]
    transition: list[dict[str, typing.Optional[int]]]
    statemap: dict[frozenset[int], int]
    final: set[int]

    def __init__(self, nfa: 'NFA'):
        self.nfa = nfa
        self.nfa_states = list()
        self.transition = list()
        self.statemap = dict()
        self.final = set()

    def _dfa_state(self, states: StateSet) -> typing.Optional[int]:
        """Return the DFA state corresponding to the given set of NFA states."""
        if not states:
            return None

        states = frozenset(states)
        dfa_state = self.statemap.get(states)
        if dfa_state is None:
            dfa_state = self.statemap[states] = len(self.statemap)
            self.nfa_states.append(states)
            self.transition.append(dict())
            if self.nfa.is_final(states):
                self.final.add(dfa_state)

        return dfa_state

    def initial(self) -> typing.Optional[int]:
        if not self.nfa.transition:
            return None
        return self._dfa_state(self.nfa.initial())

    def advance(self, source: typing.Optional[int], symbol: str) -> typing.Optional[int]:
        """Advance the automaton based on the transitions labeled
           with the symbol ``symbol``."""
        if source is None:
            return None

        trans = self.transition[source]
        if symbol not in trans:
            trans[symbol] = self._dfa_state(self.nfa.advance(self.nfa_states[source], symbol))
        return trans[symbol]

    def is_failure(self, state: typing.Optional[int]) -> bool:
        return state is None

    def is_final(self, state: typing.Optional[int]) -> bool:
        return state is not None and state in self.final


@dataclasses.dataclass
class NFA(Automaton[StateSet]):
    transition: list[list[typing.Tuple[Matcher, int]]]
    epsilon: list[list[int]]
    final: set[int]

    def __init__(self) -> None:
        super().__init__()
        self.transition = []
        self.epsilon = []
        self.final = set()
        self.epsilon_closure_cache: typing.Optional[dict[int, StateSet]] = None

    def add_state(self) -> int:
        """Add a state to the automaton and return its integer identifier."""
        self.transition.append(list())
        self.epsilon.append([])
        return len(self.transition) - 1

    def mark_final(self, state: int) -> None:
        """Mark a state as final.  A visit that terminates on the state
           will be considered successful."""
        assert state >= 0 and state < len(self.transition)
        self.final.add(state)

    def add_epsilon_transition(self, source: int, dest: int) -> None:
        """Add an epsilon transition, i.e. a transition that can
           happen nondeterministically as soon as the automaton
           reaches the source state."""
        self.epsilon[source].append(dest)
        self.epsilon_closure_cache = None

    def add_transition(self, source: int, m: Matcher, dest: int) -> None:
        """Add a transition from a source node ``source`` to a
           destination node ``dest``.  The transition happens for a
           symbol ``sym`` if ``m(sym)`` is True."""
        self.transition[source].append((m, dest))

    def _epsilon_closure(self, state: int) -> StateSet:
        epsilon = self.epsilon
        curr: StateSet = {}
        states = {state}
        while True:
            prev = curr
            curr = frozenset(states)
            for state in curr:
                if state not in prev:
                    states.update(epsilon[state])
            if len(states) == len(curr):
                return curr

    def epsilon_closure(self, state: int) -> StateSet:
        """Return the epsilon closure of the given state, i.e.
           the states from which the automaton can advance on the
           next transition."""
        if not self.epsilon_closure_cache:
            self.epsilon_closure_cache = dict()
        if state not in self.epsilon_closure_cache:
            self.epsilon_closure_cache[state] = self._epsilon_closure(state)
        return self.epsilon_closure_cache[state]

    def initial(self) -> StateSet:
        """Return the initial state of a visit on the NFA."""
        return self.epsilon_closure(0)

    def advance(self, source: StateSet, symbol: str) -> StateSet:
        """Return the states reached by the NFA when fed the given symbol
           from the current state of the visit."""
        # collect all transitions
        dest: set[int] = set()
        transition = self.transition
        for state in source:
            for m, transition_dest in transition[state]:
                if m(symbol):
                    dest.update(self.epsilon_closure(transition_dest))

        return dest

    def is_failure(self, states: StateSet) -> bool:
        return not states

    def is_final(self, states: StateSet) -> bool:
        final = self.final
        for state in states:
            if state in final:
                return True
        return False

    def lazy_dfa(self) -> LazyDFA:
        """Return an object that will perform a visit on the NFA using
           lazy DFA construction."""
        return LazyDFA(self)
