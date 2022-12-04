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
    def add_external_node(self, name: str) -> int:
        pass

    @abc.abstractmethod
    def _add_node(self, i: int, username: typing.Optional[str] = None,
                  file: typing.Optional[str] = None,
                  line: typing.Optional[int] = None) -> None:
        pass

    @abc.abstractmethod
    def _add_edge(self, i: int, j: int, is_call: bool) -> None:
        pass

    @abc.abstractmethod
    def node_count(self) -> int:
        pass

    @abc.abstractmethod
    def _node_by_index(self, i: int) -> Node:
        pass

    @abc.abstractmethod
    def _name_by_index(self, i: int) -> str:
        pass

    @abc.abstractmethod
    def _get_callers(self, i: int) -> typing.Iterable[int]:
        pass

    @abc.abstractmethod
    def _get_callees(self, i: int) -> typing.Iterable[int]:
        pass

    @abc.abstractmethod
    def _get_node(self, name: str) -> typing.Union[typing.Tuple[None, None], typing.Tuple[int, str]]:
        pass

    @abc.abstractmethod
    def _is_node_external(self, i: int) -> bool:
        pass

    @abc.abstractmethod
    def _has_edge(self, src: int, dest: int, ref_ok: bool) -> bool:
        pass

    @abc.abstractmethod
    def _has_call_edge(self, src: int, dest: int) -> bool:
        pass

    @abc.abstractmethod
    def all_files(self) -> typing.Iterable[str]:
        pass

    @abc.abstractmethod
    def _all_nodes(self) -> typing.Iterable[int]:
        pass

    @abc.abstractmethod
    def _all_nodes_for_file(self, file: str) -> typing.Iterable[int]:
        pass

    @abc.abstractmethod
    def name(self, x: str) -> str:
        pass

    @abc.abstractmethod
    def labels(self) -> typing.Iterable[str]:
        pass

    @abc.abstractmethod
    def _all_nodes_for_label(self, label: str) -> typing.Iterable[int]:
        pass

    @abc.abstractmethod
    def _add_label(self, i: int, label: str) -> None:
        pass

    @abc.abstractmethod
    def _has_label(self, i: int, label: str) -> bool:
        pass

    @abc.abstractmethod
    def reset_labels(self) -> None:
        pass

    def add_node(self, name: str, username: typing.Optional[str] = None,
                 file: typing.Optional[str] = None,
                 line: typing.Optional[int] = None) -> None:
        i = self.add_external_node(name)
        self._add_node(i, username, file, line)

    def add_edge(self, caller: str, callee: str, type: str) -> None:
        # The caller must exist, but the callee could be external.
        i, _ = self._get_node(caller)
        assert i is not None
        j = self.add_external_node(callee)
        self._add_edge(i, j, type == "call")

    def get_node(self, name: str) -> typing.Optional[Node]:
        n, _ = self._get_node(name)
        if n is None:
            return None
        return self._node_by_index(n)

    def is_node_external(self, name: str) -> bool:
        i, _ = self._get_node(name)
        return i is not None and self._is_node_external(i)

    def _visit(self, start: str, targets: typing.Callable[[int], typing.Iterable[int]]) -> typing.Iterator[str]:
        visited: set[int] = set()

        def visit(n: int) -> typing.Iterator[str]:
            for target in targets(n):
                if target is not None and target not in visited:
                    visited.add(target)
                    yield self._name_by_index(target)
                    yield from visit(target)

        i, name = self._get_node(start)
        if i is None:
            return iter({})
        assert name is not None
        yield name
        yield from visit(i)

    def all_callers(self, callee: str) -> typing.Iterator[str]:
        return self._visit(callee, self._get_callers)

    def all_callees(self, caller: str) -> typing.Iterator[str]:
        return self._visit(caller, self._get_callees)

    def _callers(self, i: int, ref_ok: bool) -> typing.Iterator[str]:
        return (
            self._name_by_index(caller)
            for caller in self._get_callers(i)
            if self._filter_node(caller, True) and self._filter_edge(caller, i, ref_ok))

    def callers(self, callee: str, ref_ok: bool) -> typing.Iterator[str]:
        i, _ = self._get_node(callee)
        if i is None:
            return iter([])
        return self._callers(i, ref_ok)

    def _callees(self, i: int, external_ok: bool, ref_ok: bool) -> typing.Iterator[str]:
        return (self._name_by_index(callee)
                for callee in self._get_callees(i)
                if self._filter_node(callee, external_ok) and self._filter_edge(i, callee, ref_ok))

    def callees(self, caller: str, external_ok: bool, ref_ok: bool) -> typing.Iterator[str]:
        i, _ = self._get_node(caller)
        if i is None:
            return iter([])
        return self._callees(i, external_ok, ref_ok)

    def has_node(self, name: str) -> bool:
        i, _ = self._get_node(name)
        return i is not None

    def all_nodes(self, external_ok: bool) -> typing.Iterator[str]:
        return (self._name_by_index(i)
                for i in self._all_nodes()
                if self._filter_node(i, external_ok))

    def all_nodes_for_file(self, file: str) -> typing.Iterator[str]:
        return (self._name_by_index(i)
                for i in self._all_nodes_for_file(file))

    def _filter_node(self, n: int, external_ok: bool) -> bool:
        if not external_ok and self._is_node_external(n):
            return False
        name = self._name_by_index(n)
        if self.keep is not None and name in self.keep:
            return True
        if name in self.omitted:
            return False
        return self.filter_default

    def filter_node(self, x: str, external_ok: bool) -> bool:
        n, _ = self._get_node(x)
        if n is None:
            return False
        return self._filter_node(n, external_ok)

    def edge_type(self, src: str, dest: str) -> str:
        srcnode, srcname = self._get_node(src)
        dstindex = self.add_external_node(dest)
        assert srcnode is not None
        return "call" if self._has_call_edge(srcnode, dstindex) else "ref"

    def _filter_edge(self, caller_node: int, callee_node: int, ref_ok: bool) -> bool:
        if self._name_by_index(caller_node) in self.omitting_callees:
            return False
        if self._name_by_index(callee_node) in self.omitting_callers:
            return False
        return self._has_edge(caller_node, callee_node, ref_ok)

    def filter_edge(self, caller: str, callee: str, ref_ok: bool) -> bool:
        caller_node, _ = self._get_node(caller)
        callee_node, _ = self._get_node(callee)
        if caller_node is None or callee_node is None:
            return False
        return self._filter_edge(caller_node, callee_node, ref_ok)

    def _omit_node(self, name: str) -> None:
        self.omitted.add(name)
        if self.keep is not None and name in self.keep:
            self.keep.remove(name)

    def omit_node(self, name: str) -> None:
        n, _ = self._get_node(name)
        name = self._name_by_index(n) if n is not None else name
        self._omit_node(name)

    def _check_node_visibility(self, n: int) -> None:
        callers = self._callers(n, True)
        if next(callers, None) is not None:
            return

        callees = self._callees(n, True, True)
        if next(callees, None) is not None:
            return

        self._omit_node(self._name_by_index(n))

    def omit_callers(self, name: str) -> None:
        n, _ = self._get_node(name)
        name = self._name_by_index(n) if n is not None else name

        self.omitting_callers.add(name)
        if n is not None:
            self._check_node_visibility(n)
            for caller in self._get_callers(n):
                self._check_node_visibility(caller)

    def omit_callees(self, name: str) -> None:
        n, _ = self._get_node(name)
        name = self._name_by_index(n) if n is not None else name

        self.omitting_callees.add(name)
        if n is not None:
            self._check_node_visibility(n)
            for callee in self._get_callees(n):
                self._check_node_visibility(callee)

    def _keep_node(self, name: str) -> None:
        if self.keep is None:
            self.keep = set()

        self.keep.add(name)
        if name in self.omitted:
            self.omitted.remove(name)

    def keep_node(self, name: str) -> None:
        n, _ = self._get_node(name)
        name = self._name_by_index(n) if n is not None else name
        self._keep_node(name)

    def paths(self, a: Automaton[typing.Any], external_ok: bool,
              ref_ok: bool) -> typing.Iterable[typing.Iterable[str]]:
        visited: set[int] = set()
        valid: set[int] = set()
        path = Path()

        def visit(node: int, state: typing.Any) -> typing.Iterable[typing.Iterable[str]]:
            visited.add(node)
            if node not in valid:
                if not self._filter_node(node, external_ok):
                    # do not remove from visited to prune quickly on subsequent
                    # paths. this makes failure of this test rare, so do it last
                    return
                valid.add(node)

            name = self._name_by_index(node)
            next_state = a.advance(state, name)
            if not a.is_failure(next_state):
                path.append(name)
                if a.is_final(next_state):
                    yield path
                for callee in self._get_callees(node):
                    if callee not in visited and self._filter_edge(node, callee, ref_ok):
                        yield from visit(callee, next_state)
                path.pop()
            visited.remove(node)

        for node in range(0, self.node_count()):
            yield from visit(node, a.initial())

    def reset_filter(self) -> None:
        self.omitted = set()
        self.omitting_callers = set()
        self.omitting_callees = set()
        self.keep = None
        self.filter_default = True

    def labeled_nodes(self, label: str) -> typing.Iterable[str]:
        return (self._name_by_index(i) for i in self._all_nodes_for_label(label))

    def add_label(self, node: str, label: str) -> None:
        i = self.add_external_node(node)
        self._add_label(i, label)

    def has_label(self, node: str, label: str) -> bool:
        i = self.add_external_node(node)
        return self._has_label(i, label)

    def __getitem__(self, name: str) -> Node:
        """Like get_node(), but fails if no such node exists."""
        n, _ = self._get_node(name)
        if n is None:
            raise KeyError(name)
        return self._node_by_index(n)


class PythonGraph(python_graph.Graph, GraphMixin):
    pass


Graph: typing_extensions.TypeAlias = PythonGraph
if not typing.TYPE_CHECKING:
    try:
        from . import cython_graph

        class CythonGraph(cython_graph.Graph, GraphMixin):
            pass

        Graph = CythonGraph
    except ImportError:
        pass
