#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from . import Automaton
from collections import defaultdict
import dataclasses
import typing


@dataclasses.dataclass
class DFA(Automaton[typing.Optional[int]]):
    transition: list[dict[str, int]]
    final: set[int]

    def __init__(self) -> None:
        super().__init__()
        self.transition = []
        self.final = set()

    def add_state(self) -> int:
        """Add a state to the automaton and return its integer identifier."""
        self.transition.append(dict())
        return len(self.transition) - 1

    def mark_final(self, state: int) -> None:
        """Mark a state as final.  A visit that terminates on the state
           will be considered successful."""
        assert state >= 0 and state < len(self.transition)
        self.final.add(state)

    def add_transition(self, source: int, symbol: str, dest: int) -> None:
        """Add a transition for the given symbol from a source node
           ``source`` to a destination node ``dest``.  The transition
           replaces previous transitions with the given source and
           symbol."""
        self.transition[source][symbol] = dest

    def initial(self) -> typing.Optional[int]:
        """Return the initial state of a visit on the NFA."""
        return 0 if self.transition else None

    def advance(self, source: typing.Optional[int], symbol: str) -> typing.Optional[int]:
        """Advance the automaton through the transition labeled
           with the symbol ``symbol``."""
        if source is None:
            return None
        return self.transition[source].get(symbol, None)

    def is_failure(self, state: typing.Optional[int]) -> bool:
        return state is None

    def is_final(self, state: typing.Optional[int]) -> bool:
        return state is not None and state in self.final

    def reverse(self) -> 'DFA':
        """Return a DFA that matches the reflections of the strings
           matched by ``self``."""

        # build the reverse NFA.  self.final is the initial state
        # (see below), 0 is the final state.  What's left is the
        # transition table.
        transition: list[dict[str, list[int]]] = \
            [defaultdict(lambda: list()) for _ in self.transition]

        for source, direct in enumerate(self.transition):
            for sym, target in direct.items():
                transition[target][sym].append(source)

        # This is mostly the same as NFA.nfa_to_dfa but, unlike it,
        # it does not need an alphabet because there the reverse NFA
        # only matches a given symbol for each edge of the transition
        # table.  Also, all of the reverse NFA's epsilon transitions are
        # from a dummy initial state to self.final, so they can be
        # hardcoded here and ignored in the loop below.
        result = DFA()
        initial = frozenset(self.final)
        statemap: dict[frozenset[int], int] = dict()
        statemap[initial] = result.add_state()

        # set of reverse NFA statesets for which a DFA state has been
        # created, but transitions have not been filled
        queue = set([initial])
        while queue:
            sources = queue.pop()
            revsource = statemap[sources]
            if 0 in sources:
                result.mark_final(revsource)

            symbols: set[str] = set().union(*[
                transition[source].keys()
                for source in sources])

            # build a DFA transition for each symbol by looking up
            # the DFA state corresponding to the next NFA state
            for sym in symbols:
                dest: frozenset[int] = frozenset().union(*[
                    transition[source][sym]
                    for source in sources
                    if sym in transition[source]])

                s = statemap.get(dest)
                if s is None:
                    # create new DFA state
                    s = result.add_state()
                    statemap[dest] = s
                    queue.add(dest)

                result.add_transition(revsource, sym, s)

        return result

    def minimal(self) -> 'DFA':
        """Return a DFA that is equivalent to ``self`` but has a minimal
           number of states."""
        return self.reverse().reverse()
