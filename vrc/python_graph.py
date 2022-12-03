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
    callers: set[str]
    callees: dict[str, str]
    username: typing.Optional[str] = None
    file: typing.Optional[str] = None
    line: typing.Optional[int] = None
    external: bool = True

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.callers = set()
        self.callees = dict()

    def format(self, include_location: bool) -> str:
        n = self.username or self.name
        if not include_location or self.file is None:
            return f"{n}"
        file = os.path.relpath(self.file)
        if self.line is None:
            return f"{n} ({file})"
        else:
            return f"{n} ({file}:{self.line})"

    def __hash__(self) -> int:
        return id(self)

    def __getitem__(self, callee: str) -> str:
        return self.callees[callee]

    def __setitem__(self, callee: str, type: str) -> None:
        # A "ref" edge does not override a "call" edge
        if type == "call" or callee not in self.callees:
            self.callees[callee] = type

    def _get_caller_names(self) -> typing.Iterable[str]:
        return self.callers

    def _get_callee_names(self) -> typing.Iterable[str]:
        return self.callees.keys()


class Graph:
    nodes: dict[str, Node]
    nodes_by_username: dict[str, Node]
    nodes_by_file: dict[str, list[str]]
    node_labels: dict[str, set[str]]

    def __init__(self) -> None:
        super().__init__()
        self.nodes = {}
        self.nodes_by_username = {}
        self.nodes_by_file = defaultdict(lambda: list())

        self.reset_labels()

    def add_external_node(self, name: str) -> None:
        if name not in self.nodes:
            self.nodes[name] = Node(name=name)

    def add_node(self, name: str, username: typing.Optional[str] = None,
                 file: typing.Optional[str] = None,
                 line: typing.Optional[int] = None) -> None:
        self.add_external_node(name)
        node = self.nodes[name]
        if node.external:
            # This is now a defined node.  It might have a username and a file
            node.username = username
            node.file = file
            node.line = line
            node.external = False
            if username:
                self.nodes_by_username[username] = node
            if file:
                self.nodes_by_file[file].append(name)

    def add_edge(self, caller: str, callee: str, type: str) -> None:
        # The caller must exist, but the callee could be external.
        self.add_external_node(callee)
        self.nodes[caller][callee] = type
        self.nodes[callee].callers.add(caller)

    def _get_node(self, name: str) -> typing.Union[typing.Tuple[None, None], typing.Tuple[Node, str]]:
        if name in self.nodes_by_username:
            return self.nodes_by_username[name], name
        elif name in self.nodes:
            node = self.nodes[name]
            return node, node.username or name
        else:
            return None, None

    def get_node(self, name: str) -> typing.Optional[Node]:
        n, _ = self._get_node(name)
        return n

    def is_node_external(self, name: str) -> bool:
        node, _ = self._get_node(name)
        return bool(node and node.external)

    def edge_type(self, src: str, dest: str) -> str:
        srcnode, srcname = self._get_node(src)
        dstnode, dstname = self._get_node(dest)
        assert srcnode and dstnode
        return srcnode[dstnode.name]

    def all_files(self) -> typing.Iterator[str]:
        return iter(self.nodes_by_file.keys())

    def _all_nodes(self) -> typing.Iterator[str]:
        return iter(self.nodes.keys())

    def _all_nodes_for_file(self, file: str) -> typing.Iterator[str]:
        return iter(self.nodes_by_file[file])

    def name(self, x: str) -> str:
        n = self.nodes[x]
        return n.username or x

    def labels(self) -> typing.Iterable[str]:
        return self.node_labels.keys()

    def labeled_nodes(self, label: str) -> typing.Iterable[str]:
        return self.node_labels[label]

    def add_label(self, node: str, label: str) -> None:
        self.node_labels[label].add(node)

    def has_label(self, node: str, label: str) -> bool:
        # check label first to avoid associating the key with an empty set
        return (label in self.node_labels) and (node in self.node_labels[label])

    def reset_labels(self) -> None:
        self.node_labels = defaultdict(lambda: set())
