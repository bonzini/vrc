#! /usr/bin/env python3

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import dataclasses
import os
import typing

from libcpp cimport bool as c_bool
from libc.stdlib cimport free
cimport vrc.cgraph as cgraph


cdef extern from "Python.h":
    char* PyUnicode_AsUTF8(object unicode)

cdef class Iter:
    cdef Graph _graph
    cdef cgraph.Iter *i

    def __dealloc__(self):
        cgraph.iter_delete(self.i)

    def __iter__(self):
        return self

    def __next__(self) -> int:
        n = -1
        if self.i:
            n = cgraph.iter_next(self.i)
            if n == -1:
                cgraph.iter_delete(self.i)
                self.i = NULL
        if n == -1:
            raise StopIteration
        return n


cdef object c_string_decode(char *s):
    result = s.decode("utf-8")
    free(s)
    return result


cdef object c_strings_to_list(char **s, int n):
    result = list()
    for i in range(0, n):
        result.append(s[i].decode("utf-8"))
        free(s[i])
    free(s)
    return result


cdef class Node:
    cdef Graph _graph
    cdef size_t index
    cdef object _name
    cdef object _username
    cdef object _file
    cdef object _line      # integer or None
    cdef c_bool _external

    def __cinit__(self) -> None:
        self._external = True

    @property
    def name(self) -> typing.Optional[str]:
        if self._name is None:
            self._name = c_string_decode(cgraph.graph_name_by_index(NULL, self._graph.g, self.index))
            self._username = c_string_decode(cgraph.graph_username_by_index(NULL, self._graph.g, self.index))
        return self._name or None

    @property
    def username(self) -> typing.Optional[str]:
        if self._name is None:
            self.name
        return self._username or None

    @property
    def file(self) -> typing.Optional[str]:
        cdef ssize_t line
        if self._line is None:
            self._file = c_string_decode(cgraph.graph_location_by_index(NULL, self._graph.g, self.index, &line))
            self._line = line
        return self._file or None

    @property
    def line(self) -> typing.Optional[str]:
        if self._line is None:
            self.file
        return None if self._line == -1 else self._line

    @property
    def external(self) -> bool:
        return self._external

    def format(self, include_location: bool) -> str:
        n = self.username or self.name
        if not include_location or self.file is None:
            return f"{n}"
        file = os.path.relpath(self.file)
        if self.line is None:
            return f"{n} ({file})"
        else:
            return f"{n} ({file}:{self.line})"


cdef class Graph:
    def __cinit__(self) -> None:
        self.g = cgraph.graph_new()
        self.nodes_by_index = []

    def __dealloc__(self):
        cgraph.graph_delete(self.g)

    def add_external_node(self, name: str) -> int:
        cdef char *string = PyUnicode_AsUTF8(name)
        return cgraph.graph_add_external_node(NULL, self.g, string)

    def _add_node(self, i: int, username: typing.Optional[str] = None,
                  file: typing.Optional[str] = None,
                  line: typing.Optional[int] = None) -> None:
        cdef char *string
        cdef Node node
        if cgraph.graph_is_node_external(NULL, self.g, i):
            # This is now a defined node.  It might have a username and a file
            cgraph.graph_set_defined(NULL, self.g, i)
            node = self._node_by_index(i)
            node._external = False
            node.name
            if username:
                node._username = username
                string = PyUnicode_AsUTF8(username)
                cgraph.graph_set_username(NULL, self.g, i, string)
            if file:
                node._file = file
                node._line = -1 if line is None else line
                string = PyUnicode_AsUTF8(file)
                cgraph.graph_set_location(NULL, self.g, i, string, <ssize_t>node._line)

    def _add_edge(self, i: int, j: int, is_call: bool) -> None:
        cgraph.graph_add_edge(NULL, self.g, i, j, is_call)

    def node_count(self) -> int:
        return cgraph.graph_node_count(NULL, self.g)

    def _node_by_index(self, i: int) -> Node:
        cdef Node node
        if len(self.nodes_by_index) <= i:
            if i >= self.node_count():
                raise IndexError
            self.nodes_by_index += [None] * (self.node_count() - len(self.nodes_by_index) + 1)
        if self.nodes_by_index[i] is None:
            node = Node()
            node._graph = self
            node.index = i
            self.nodes_by_index[i] = node
        return self.nodes_by_index[i]

    def _username_by_index(self, i: int) -> str:
        return self._node_by_index(i).username

    def _name_by_index(self, i: int) -> str:
        return self._node_by_index(i).name

    cdef object iter_to_python(self, cgraph.Iter *i):
        it = Iter()
        it._graph = self
        it.i = i
        return it

    def _get_callers(self, i: int) -> typing.Iterable[int]:
        return self.iter_to_python(cgraph.graph_get_callers(NULL, self.g, i))

    def _get_all_callees(self, i: int) -> typing.Iterable[int]:
        yield from self.iter_to_python(cgraph.graph_get_callees(NULL, self.g, i))
        yield from self.iter_to_python(cgraph.graph_get_refs(NULL, self.g, i))

    def _get_callees(self, i: int, ref_ok: bool = True) -> typing.Iterable[int]:
        if ref_ok:
            return self._get_all_callees(i)
        else:
            return self.iter_to_python(cgraph.graph_get_callees(NULL, self.g, i))

    def _get_node(self, name: str) -> typing.Union[typing.Tuple[None, None], typing.Tuple[int, str]]:
        cdef char *string = PyUnicode_AsUTF8(name)
        cdef ssize_t result = cgraph.graph_get_node(NULL, self.g, string)
        if result == -1:
            return None, None

        n = self._node_by_index(result)
        return result, n.username or name

    def _is_node_external(self, i: int) -> bool:
        return cgraph.graph_is_node_external(NULL, self.g, i)

    def _has_edge(self, src: int, dest: int, ref_ok: bool) -> bool:
        return cgraph.graph_has_edge(NULL, self.g, src, dest, ref_ok)

    def _has_call_edge(self, src: int, dest: int) -> bool:
        return cgraph.graph_has_call_edge(NULL, self.g, src, dest)

    def all_files(self) -> typing.Iterable[str]:
        cdef size_t n
        cdef const char **strings = cgraph.graph_all_files(NULL, self.g, &n)
        return c_strings_to_list(strings, n)

    def _all_nodes(self) -> typing.Iterable[int]:
        return range(0, cgraph.graph_node_count(NULL, self.g))

    def _all_nodes_for_file(self, file: str) -> typing.Iterable[int]:
        return self.iter_to_python(cgraph.graph_all_nodes_for_file(NULL, self.g, file.encode("utf-8")))

    def name(self, x: str) -> str:
        cdef char *string = PyUnicode_AsUTF8(x)
        cdef ssize_t result = cgraph.graph_get_node(NULL, self.g, string)
        if result == -1:
            raise KeyError(x)

        n = self._node_by_index(result)
        return n.username or x

    def labels(self) -> typing.Iterable[str]:
        cdef size_t n
        cdef const char **strings = cgraph.graph_all_labels(NULL, self.g, &n)
        return c_strings_to_list(strings, n)

    def _all_nodes_for_label(self, label: str) -> typing.Iterable[int]:
        return self.iter_to_python(cgraph.graph_all_nodes_for_label(NULL, self.g, label.encode("utf-8")))

    def _add_label(self, i: int, label: str) -> None:
        cdef char *string = PyUnicode_AsUTF8(label)
        cgraph.graph_add_label(NULL, self.g, i, string)

    def _has_label(self, i: int, label: str) -> bool:
        cdef char *string = PyUnicode_AsUTF8(label)
        return cgraph.graph_has_label(NULL, self.g, i, string)

    def reset_labels(self) -> None:
        cgraph.graph_reset_labels(self.g)
