#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from collections import defaultdict
import dataclasses
import os
import typing


@dataclasses.dataclass
class Node:
    name: str
    callers: set[int]
    callees: set[int]
    refs: set[int]
    username: typing.Optional[str] = None
    file: typing.Optional[str] = None
    line: typing.Optional[int] = None
    external: bool = True

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.callers = set()
        self.callees = set()
        self.refs = set()

    def _all_callees_iter(self) -> typing.Iterable[int]:
        yield from iter(self.callees)
        yield from iter(self.refs)

    def format(self, include_location: bool) -> str:
        n = self.username or self.name
        if not include_location or self.file is None:
            return f"{n}"
        file = os.path.relpath(self.file)
        if self.line is None:
            return f"{n} ({file})"
        else:
            return f"{n} ({file}:{self.line})"


class Graph:
    nodes_by_index: list[Node]
    nodes: dict[str, int]
    nodes_by_username: dict[str, int]
    nodes_by_file: dict[str, list[int]]
    node_labels: dict[str, set[int]]

    def __init__(self) -> None:
        super().__init__()
        self.nodes_by_index = []
        self.nodes = {}
        self.nodes_by_username = {}
        self.nodes_by_file = defaultdict(lambda: list())

        self.reset_labels()

    def add_external_node(self, name: str) -> int:
        i = self.nodes_by_username.get(name, None)
        if i is not None:
            return i

        i = self.nodes.get(name, None)
        if i is not None:
            return i

        i = len(self.nodes_by_index)
        self.nodes[name] = i
        self.nodes_by_index.append(Node(name=name))
        return i

    def _add_node(self, i: int, username: typing.Optional[str] = None,
                  file: typing.Optional[str] = None,
                  line: typing.Optional[int] = None) -> None:
        node = self.nodes_by_index[i]
        if node.external:
            # This is now a defined node.  It might have a username and a file
            node.username = username
            node.file = file
            node.line = line
            node.external = False
            if username:
                self.nodes_by_username[username] = i
            if file:
                self.nodes_by_file[file].append(i)

    def _add_edge(self, i: int, j: int, is_call: bool) -> None:
        src = self.nodes_by_index[i]
        # A "ref" edge does not override a "call" edge
        if is_call:
            if j in src.refs:
                src.refs.remove(j)
            src.callees.add(j)
        elif j not in src.callees:
            src.refs.add(j)

        self.nodes_by_index[j].callers.add(i)

    def node_count(self) -> int:
        return len(self.nodes_by_index)

    def _node_by_index(self, i: int) -> Node:
        return self.nodes_by_index[i]

    def _name_by_index(self, i: int) -> str:
        node = self.nodes_by_index[i]
        return node.username or node.name

    def _get_callers(self, i: int) -> typing.Iterable[int]:
        return self.nodes_by_index[i].callers

    def _get_callees(self, i: int, ref_ok: bool = True) -> typing.Iterable[int]:
        if ref_ok:
            return self.nodes_by_index[i]._all_callees_iter()
        else:
            return iter(self.nodes_by_index[i].callees)

    def _get_node(self, name: str) -> typing.Union[typing.Tuple[None, None], typing.Tuple[int, str]]:
        i = self.nodes_by_username.get(name, None)
        if i is not None:
            return i, name

        i = self.nodes.get(name, None)
        if i is not None:
            node = self.nodes_by_index[i]
            return i, node.username or name
        return None, None

    def _is_node_external(self, i: int) -> bool:
        return self.nodes_by_index[i].external

    def _has_edge(self, src: int, dest: int, ref_ok: bool) -> bool:
        if dest in self.nodes_by_index[src].callees:
            return True
        return ref_ok and not self.nodes_by_index[dest].external and dest in self.nodes_by_index[src].refs

    def _has_call_edge(self, src: int, dest: int) -> bool:
        return dest in self.nodes_by_index[src].callees

    def all_files(self) -> typing.Iterable[str]:
        return iter(self.nodes_by_file.keys())

    def _all_nodes(self) -> typing.Iterable[int]:
        return range(0, self.node_count())

    def _all_nodes_for_file(self, file: str) -> typing.Iterable[int]:
        return self.nodes_by_file[file]

    def name(self, x: str) -> str:
        n = self.nodes_by_index[self.nodes[x]]
        return n.username or x

    def labels(self) -> typing.Iterable[str]:
        return self.node_labels.keys()

    def _all_nodes_for_label(self, label: str) -> typing.Iterable[int]:
        return self.node_labels[label]

    def _add_label(self, i: int, label: str) -> None:
        self.node_labels[label].add(i)

    def _has_label(self, i: int, label: str) -> bool:
        return (label in self.node_labels) and (i in self.node_labels[label])

    def reset_labels(self) -> None:
        self.node_labels = defaultdict(lambda: set())
