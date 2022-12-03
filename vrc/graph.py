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
import typing_extensions

from . import python_graph
from .python_graph import Node
from .util import Path
from .automata import Automaton


class GraphMixin(metaclass=abc.ABCMeta):
    keep: typing.Optional[set[str]]
    omitted: set[str]
    omitting_callers: set[str]    # Edges directed to these nodes are ignored
    omitting_callees: set[str]    # Edges starting from these nodes are ignored
    filter_default: bool

    def __init__(self) -> None:
        super().__init__()
        self.reset_filter()

    @abc.abstractmethod
    def add_external_node(self, name: str) -> None:
        pass

    @abc.abstractmethod
    def add_node(self, name: str, username: typing.Optional[str] = None,
                 file: typing.Optional[str] = None,
                 line: typing.Optional[int] = None) -> None:
        pass

    @abc.abstractmethod
    def add_edge(self, caller: str, callee: str, type: str) -> None:
        pass

    @abc.abstractmethod
    def _get_node(self, name: str) -> typing.Union[typing.Tuple[None, None], typing.Tuple[Node, str]]:
        pass

    @abc.abstractmethod
    def get_node(self, name: str) -> typing.Optional[Node]:
        pass

    @abc.abstractmethod
    def is_node_external(self, name: str) -> bool:
        pass

    @abc.abstractmethod
    def edge_type(self, src: str, dest: str) -> str:
        pass

    @abc.abstractmethod
    def all_files(self) -> typing.Iterator[str]:
        pass

    @abc.abstractmethod
    def _all_nodes(self) -> typing.Iterator[str]:
        pass

    @abc.abstractmethod
    def _all_nodes_for_file(self, file: str) -> typing.Iterator[str]:
        pass

    @abc.abstractmethod
    def name(self, x: str) -> str:
        pass

    @abc.abstractmethod
    def labels(self) -> typing.Iterable[str]:
        pass

    @abc.abstractmethod
    def labeled_nodes(self, label: str) -> typing.Iterable[str]:
        pass

    @abc.abstractmethod
    def add_label(self, node: str, label: str) -> None:
        pass

    @abc.abstractmethod
    def has_label(self, node: str, label: str) -> bool:
        pass

    @abc.abstractmethod
    def reset_labels(self) -> None:
        pass

    def _visit(self, start: str, targets: typing.Callable[[Node], typing.Iterable[str]]) -> typing.Iterator[str]:
        visited = set()

        def visit(n: Node) -> typing.Iterator[str]:
            for caller in targets(n):
                target, name = self._get_node(caller)
                if target and target.name not in visited:
                    assert name is not None
                    visited.add(target.name)
                    yield name
                    yield from visit(target)

        n, name = self._get_node(start)
        if not n:
            return iter({})
        assert name is not None
        yield name
        yield from visit(n)

    def all_callers(self, callee: str) -> typing.Iterator[str]:
        return self._visit(callee, Node._get_caller_names)

    def all_callees(self, caller: str) -> typing.Iterator[str]:
        return self._visit(caller, Node._get_callee_names)

    def callers(self, callee: str, ref_ok: bool) -> typing.Iterator[str]:
        n, _ = self._get_node(callee)
        if not n:
            return iter([])
        return (
            self.name(caller)
            for caller in n._get_caller_names()
            if self.filter_node(caller, True) and self.filter_edge(caller, callee, ref_ok))

    def callees(self, caller: str, external_ok: bool, ref_ok: bool) -> typing.Iterator[str]:
        n, _ = self._get_node(caller)
        if not n:
            return iter([])
        return (self.name(callee)
                for callee in n._get_callee_names()
                if self.filter_node(callee, external_ok) and self.filter_edge(caller, callee, ref_ok))

    def has_node(self, name: str) -> bool:
        return bool(self.get_node(name))

    def all_nodes(self, external_ok: bool) -> typing.Iterator[str]:
        return (self.name(x)
                for x in self._all_nodes()
                if self.filter_node(x, external_ok))

    def all_nodes_for_file(self, file: str) -> typing.Iterator[str]:
        return (self.name(x)
                for x in self._all_nodes_for_file(file))

    def _filter_node(self, n: Node, external_ok: bool) -> bool:
        if not external_ok and n.external:
            return False
        if self.keep is not None and n.name in self.keep:
            return True
        if n.name in self.omitted:
            return False
        return self.filter_default

    def filter_node(self, x: str, external_ok: bool) -> bool:
        n, _ = self._get_node(x)
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
        caller_node, _ = self._get_node(caller)
        callee_node, _ = self._get_node(callee)
        if not caller_node or not callee_node:
            return False
        return self._filter_edge(caller_node, callee_node, ref_ok)

    def omit_node(self, name: str) -> None:
        n, _ = self._get_node(name)
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
        n, _ = self._get_node(name)
        name = n.name if n else name

        self.omitting_callers.add(name)
        self._check_node_visibility(name)
        if n:
            for caller in n._get_caller_names():
                self._check_node_visibility(caller)

    def omit_callees(self, name: str) -> None:
        n, _ = self._get_node(name)
        name = n.name if n else name

        self.omitting_callees.add(name)
        self._check_node_visibility(name)
        if n:
            for callee in n._get_callee_names():
                self._check_node_visibility(callee)

    def keep_node(self, name: str) -> None:
        if self.keep is None:
            self.keep = set()

        n, _ = self._get_node(name)
        name = n.name if n else name

        self.keep.add(name)
        if name in self.omitted:
            self.omitted.remove(name)

    def paths(self, a: Automaton[typing.Any], external_ok: bool,
              ref_ok: bool) -> typing.Iterable[typing.Iterable[str]]:
        visited: set[Node] = set()
        valid: set[Node] = set()
        path = Path()

        def visit(caller: typing.Optional[Node], nodes: typing.Iterable[str],
                  state: typing.Any) -> typing.Iterable[typing.Iterable[str]]:
            for target in nodes:
                node, name = self._get_node(target)
                assert node is not None and name is not None
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

                next_state = a.advance(state, name)
                if not a.is_failure(next_state):
                    path.append(name)
                    if a.is_final(next_state):
                        yield path
                    yield from visit(node, node._get_callee_names(), next_state)
                    path.pop()
                visited.remove(node)

        yield from visit(None, self.all_nodes(external_ok), a.initial())

    def reset_filter(self) -> None:
        self.omitted = set()
        self.omitting_callers = set()
        self.omitting_callees = set()
        self.keep = None
        self.filter_default = True

    def __getitem__(self, name: str) -> Node:
        """Like get_node(), but fails if no such node exists."""
        node = self.get_node(name)
        if node is None:
            raise IndexError
        return node


class PythonGraph(python_graph.Graph, GraphMixin):
    pass


Graph: typing_extensions.TypeAlias = PythonGraph
