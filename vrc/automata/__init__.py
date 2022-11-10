#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import abc
import typing

T = typing.TypeVar('T')


class Visitor(typing.Generic[T]):
    def __init__(self, automaton: 'Automaton[T]') -> None:
        self.automaton = automaton
        self.state = automaton.initial()

    def visit(self, symbol: str) -> None:
        self.state = self.automaton.advance(self.state, symbol)

    def success(self) -> bool:
        return self.automaton.is_final(self.state)


class Automaton(typing.Generic[T], metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def initial(self) -> T:
        """Return the initial state of a visit of ``self``."""
        pass

    @abc.abstractmethod
    def advance(self, source: T, symbol: str) -> T:
        """Return the state reached by the automaton when fed
           ``symbol`` from the state ``source``."""
        pass

    def is_failure(self, state: T) -> bool:
        """Return True if ``state`` does not accept any string."""
        return False

    @abc.abstractmethod
    def is_final(self, state: T) -> bool:
        """Return True if ``state`` is an accepting state."""
        pass

    def matches(self, feed: typing.Iterable[str]) -> bool:
        """Return True if the automaton matches the sequence
           of symbols in ``feed``."""
        s = self.initial()
        for symbol in feed:
            if self.is_failure(s):
                return False
            s = self.advance(s, symbol)
        return self.is_final(s)

    def visit(self) -> Visitor[T]:
        """Return an object that will perform a visit on the NFA."""
        return Visitor(self)
