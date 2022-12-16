#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import dataclasses
import sys
import typing

_dataclass_args = {} \
    if sys.version_info < (3, 10) \
    else {'slots': True}


@dataclasses.dataclass(**_dataclass_args)
class PathElement:
    value: str
    next: typing.Optional['PathElement'] = None


@dataclasses.dataclass(**_dataclass_args)
class PathIterator(typing.Iterator[str]):
    curr: typing.Optional[PathElement]

    def __next__(self) -> str:
        if self.curr is None:
            raise StopIteration
        value = self.curr.value
        self.curr = self.curr.next
        return value


@dataclasses.dataclass(**_dataclass_args)
class Path:
    first: typing.Optional[PathElement] = None

    def append(self, value: str) -> typing.Optional[PathElement]:
        old = self.first
        self.first = PathElement(value, old)
        return old

    def __iter__(self) -> typing.Iterator[str]:
        return PathIterator(self.first)
