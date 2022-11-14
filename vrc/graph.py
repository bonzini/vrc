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
import re
import typing

from .util import Path
from .automata import Automaton


@dataclasses.dataclass
class Node:
    name: str
    callers: set[str]
    callees: dict[str, str]
    username: typing.Optional[str] = None
    external: bool = True

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.callers = set()
        self.callees = dict()

    def __hash__(self) -> int:
        return id(self)

    def __getitem__(self, callee: str) -> str:
        return self.callees[callee]

    def __setitem__(self, callee: str, type: str) -> None:
        # A "ref" edge does not override a "call" edge
        if type == "call" or callee not in self.callees:
            self.callees[callee] = type


class Graph:
    nodes: dict[str, Node]
    nodes_by_username: dict[str, Node]
    nodes_by_file: dict[str, list[str]]
    keep: typing.Optional[set[str]]
    omitted: set[str]
    omitting_callers: set[str]    # Edges directed to these nodes are ignored
    omitting_callees: set[str]    # Edges starting from these nodes are ignored
    node_labels: dict[str, set[str]]
    filter_default: bool

    def __init__(self) -> None:
        self.nodes = {}
        self.nodes_by_username = {}
        self.nodes_by_file = defaultdict(lambda: list())

        self.reset_filter()
        self.reset_labels()

    def parse(self, fn: str, lines: typing.Iterator[str], verbose_print: typing.Callable[[str], None]) -> None:
        RE_FUNC1 = re.compile(r"^;; Function (\S+)\s*$")
        RE_FUNC2 = re.compile(r"^;; Function (.*)\s+\((\S+)(,.*)?\).*$")
        RE_SYMBOL_REF = re.compile(r'\(symbol_ref [^(]* \( "([^"]*)"', flags=re.X)
        curfunc = None
        for line in lines:
            if line.startswith(";; Function "):
                m = RE_FUNC1.search(line)
                if m:
                    curfunc = m.group(1)
                    self.add_node(m.group(1), file=fn)
                    verbose_print(f"{fn}: found function {m.group(1)}")
                    continue
                m = RE_FUNC2.search(line)
                if m:
                    curfunc = m.group(2)
                    self.add_node(m.group(2), username=m.group(1), file=fn)
                    verbose_print(f"{fn}: found function {m.group(1)} ({m.group(2)})")
                    continue
            elif curfunc:
                m = RE_SYMBOL_REF.search(line)
                if m:
                    type = "call" if "(call" in line else "ref"
                    verbose_print(f"{fn}: found {type} edge {curfunc} -> {m.group(1)}")
                    self.add_edge(curfunc, m.group(1), type)

    def add_external_node(self, name: str) -> None:
        if name not in self.nodes:
            self.nodes[name] = Node(name=name)

    def add_node(self, name: str, username: typing.Optional[str] = None,
                 file: typing.Optional[str] = None) -> None:
        self.add_external_node(name)
        if self.nodes[name].external:
            # This is now a defined node.  It might have a username and a file
            self.nodes[name].external = False
            if username:
                self.nodes[name].username = username
                self.nodes_by_username[username] = self.nodes[name]
            if file:
                self.nodes_by_file[file].append(name)

    def add_edge(self, caller: str, callee: str, type: str) -> None:
        # The caller must exist, but the callee could be external.
        self.add_external_node(callee)
        self.nodes[caller][callee] = type
        self.nodes[callee].callers.add(caller)

    def _get_node(self, name: str) -> typing.Optional[Node]:
        if name in self.nodes_by_username:
            return self.nodes_by_username[name]
        elif name in self.nodes:
            return self.nodes[name]
        else:
            return None

    def has_node(self, name: str) -> bool:
        return bool(self._get_node(name))

    def is_node_external(self, name: str) -> bool:
        node = self._get_node(name)
        return bool(node and node.external)

    def edge_type(self, src: str, dest: str) -> str:
        node = self._get_node(src)
        assert node
        return node[dest]

    def _visit(self, start: str, targets: typing.Callable[[Node], typing.Iterable[str]]) -> typing.Iterator[str]:
        visited = set()

        def visit(n: Node) -> typing.Iterator[str]:
            if n.name in visited:
                return
            visited.add(n.name)
            yield n.username or n.name
            for caller in targets(n):
                target = self._get_node(caller)
                if target:
                    yield from visit(target)

        n = self._get_node(start)
        if not n:
            return iter({})
        yield from visit(n)

    def all_callers(self, callee: str) -> typing.Iterator[str]:
        return self._visit(callee, lambda n: n.callers)

    def all_callees(self, caller: str) -> typing.Iterator[str]:
        return self._visit(caller, lambda n: n.callees.keys())

    def callers(self, callee: str, ref_ok: bool) -> typing.Iterator[str]:
        n = self._get_node(callee)
        if not n:
            return iter([])
        return (
            self.name(caller)
            for caller in n.callers
            if self.filter_node(caller, True) and self.filter_edge(caller, callee, ref_ok))

    def callees(self, caller: str, external_ok: bool, ref_ok: bool) -> typing.Iterator[str]:
        n = self._get_node(caller)
        if not n:
            return iter([])
        return (self.name(callee)
                for callee in n.callees.keys()
                if self.filter_node(callee, external_ok) and self.filter_edge(caller, callee, ref_ok))

    def all_files(self) -> typing.Iterator[str]:
        return iter(self.nodes_by_file.keys())

    def all_nodes(self, external_ok: bool) -> typing.Iterator[str]:
        return (self.name(x)
                for x in self.nodes.keys()
                if self.filter_node(x, external_ok))

    def all_nodes_for_file(self, file: str) -> typing.Iterator[str]:
        return (self.name(x)
                for x in self.nodes_by_file[file]
                if self.filter_node(x, False))

    def name(self, x: str) -> str:
        n = self.nodes[x]
        return n.username or x

    def _filter_node(self, n: Node, external_ok: bool) -> bool:
        if not external_ok and n.external:
            return False
        if self.keep is not None and n.name in self.keep:
            return True
        if n.name in self.omitted:
            return False
        return self.filter_default

    def filter_node(self, x: str, external_ok: bool) -> bool:
        n = self._get_node(x)
        if not n:
            return False
        return self._filter_node(n, external_ok)

    def _filter_edge(self, caller_node: Node, callee_node: Node, ref_ok: bool) -> bool:
        if caller_node.name in self.omitting_callees:
            return False
        if callee_node.name in self.omitting_callers:
            return False
        return caller_node[callee_node.name] == "call" or (ref_ok and not callee_node.external)

    def filter_edge(self, caller: str, callee: str, ref_ok: bool) -> bool:
        caller_node = self._get_node(caller)
        callee_node = self._get_node(callee)
        if not caller_node or not callee_node:
            return False
        return self._filter_edge(caller_node, callee_node, ref_ok)

    def omit_node(self, name: str) -> None:
        n = self._get_node(name)
        name = n.name if n else name

        self.omitted.add(name)
        if self.keep is not None and name in self.keep:
            self.keep.remove(name)

    def _check_node_visibility(self, name: str) -> None:
        callers = self.callers(name, True)
        if next(callers, None) is not None:
            return

        callees = self.callees(name, True, True)
        if next(callees, None) is not None:
            return

        self.omit_node(name)

    def omit_callers(self, name: str) -> None:
        n = self._get_node(name)
        name = n.name if n else name

        self.omitting_callers.add(name)
        self._check_node_visibility(name)
        if n:
            for caller in n.callers:
                self._check_node_visibility(caller)

    def omit_callees(self, name: str) -> None:
        n = self._get_node(name)
        name = n.name if n else name

        self.omitting_callees.add(name)
        self._check_node_visibility(name)
        if n:
            for callee in n.callees:
                self._check_node_visibility(callee)

    def keep_node(self, name: str) -> None:
        if self.keep is None:
            self.keep = set()

        n = self._get_node(name)
        name = n.name if n else name

        self.keep.add(name)
        if name in self.omitted:
            self.omitted.remove(name)

    def labels(self) -> set[str]:
        return set(self.node_labels.keys())

    def labeled_nodes(self, label: str) -> set[str]:
        return self.node_labels[label]

    def add_label(self, node: str, label: str) -> None:
        self.node_labels[label].add(node)

    def has_label(self, node: str, label: str) -> bool:
        # check label first to avoid associating the key with an empty set
        return (label in self.node_labels) and (node in self.node_labels[label])

    def reset_labels(self) -> None:
        self.node_labels = defaultdict(lambda: set())

    def paths(self, a: Automaton[typing.Any], external_ok: bool,
              ref_ok: bool) -> typing.Iterable[typing.Iterable[str]]:
        visited: set[Node] = set()
        valid: set[Node] = set()
        path = Path()

        def visit(caller: typing.Optional[Node], nodes: typing.Iterable[str],
                  state: typing.Any) -> typing.Iterable[typing.Iterable[str]]:
            for target in nodes:
                node = self._get_node(target)
                assert node is not None
                if node in visited:
                    continue
                if caller and not self._filter_edge(caller, node, ref_ok):
                    continue

                visited.add(node)
                if node not in valid:
                    if not self._filter_node(node, external_ok):
                        # do not remove to prune quickly on subsequent paths.
                        # this makes failure of this test rare, so do it last
                        continue
                    valid.add(node)

                name = node.username or node.name
                next_state = a.advance(state, name)
                if not a.is_failure(next_state):
                    path.append(name)
                    if a.is_final(next_state):
                        yield path
                    yield from visit(node, node.callees.keys(), next_state)
                    path.pop()
                visited.remove(node)

        yield from visit(None, self.nodes.keys(), a.initial())

    def reset_filter(self) -> None:
        self.omitted = set()
        self.omitting_callers = set()
        self.omitting_callees = set()
        self.keep = None
        self.filter_default = True
