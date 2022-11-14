#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import dataclasses
import typing


@dataclasses.dataclass
class PathElement:
    value: str
    next: typing.Optional['PathElement'] = None


@dataclasses.dataclass
class PathIterator(typing.Iterator[str]):
    curr: typing.Optional[PathElement]

    def __next__(self) -> str:
        if self.curr is None:
            raise StopIteration
        value = self.curr.value
        self.curr = self.curr.next
        return value


class Path:
    first: typing.Optional['PathElement'] = None

    def append(self, value: str) -> None:
        new_element = PathElement(value)
        new_element.next = self.first
        self.first = new_element

    def pop(self) -> None:
        assert self.first is not None
        self.first = self.first.next

    def __iter__(self) -> typing.Iterator[str]:
        return PathIterator(self.first)
