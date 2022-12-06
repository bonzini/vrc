"""Cython description of cparser.h."""

from libcpp cimport bool as c_bool
from .. cimport cgraph

cdef extern from "cparser.h":
    void build_graph(const char *filename, const char *const *args, int num_args,
                     cgraph.Graph *g, c_bool verbose, char **diagnostic) nogil;
