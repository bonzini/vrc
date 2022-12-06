"""Cython description of the cython_graph.Graph class.
   This is needed to access the graph from vrc.loaders.cython_loader"""

# Copyright (C) 2022 Paolo Bonzini

cimport vrc.cgraph as cgraph

cdef class Graph:
    cdef cgraph.Graph *g
    cdef list nodes_by_index
