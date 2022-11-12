#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from abc import ABCMeta
from .nfa import NFA, Matcher
import dataclasses
import typing


@dataclasses.dataclass
class RegexAST(metaclass=ABCMeta):
    def tack(self, nfa: NFA, initial: int) -> int:
        """Make the ``initial`` state of the NFA accept the
           regex corresponding to ``self``.  Return the
           accepting state."""
        pass

    def nfa(self) -> NFA:
        nfa = NFA()
        final = self.tack(nfa, nfa.add_state())
        nfa.mark_final(final)
        return nfa


@dataclasses.dataclass
class Empty(RegexAST):
    def tack(self, nfa: NFA, initial: int) -> int:
        final = nfa.add_state()
        nfa.add_epsilon_transition(initial, final)
        return final


@dataclasses.dataclass
class One(RegexAST):
    m: Matcher

    def tack(self, nfa: NFA, initial: int) -> int:
        final = nfa.add_state()
        nfa.add_transition(initial, self.m, final)
        return final


@dataclasses.dataclass
class Sequence(RegexAST):
    atoms: typing.Sequence[RegexAST]

    def __init__(self, *atoms: RegexAST):
        self.atoms = atoms or [Empty()]

    def tack(self, nfa: NFA, initial: int) -> int:
        for atom in self.atoms:
            initial = atom.tack(nfa, initial)
        return initial


@dataclasses.dataclass
class Star(RegexAST):
    atom: RegexAST

    def tack(self, nfa: NFA, initial: int) -> int:
        loop = nfa.add_state()
        final = nfa.add_state()
        nfa.add_epsilon_transition(initial, loop)
        nfa.add_epsilon_transition(initial, final)
        nfa.add_epsilon_transition(self.atom.tack(nfa, loop), loop)
        nfa.add_epsilon_transition(loop, final)
        return final


@dataclasses.dataclass
class Alt(RegexAST):
    atoms: typing.Iterable[RegexAST]

    def __init__(self, *atoms: RegexAST):
        self.atoms = atoms or [Empty()]

    def tack(self, nfa: NFA, initial: int) -> int:
        final = nfa.add_state()
        for atom in self.atoms:
            branch = nfa.add_state()
            nfa.add_epsilon_transition(initial, branch)
            nfa.add_epsilon_transition(atom.tack(nfa, branch), final)
        return final
