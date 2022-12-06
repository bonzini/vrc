"""Loader that uses cparser.c to convert the call graph to a VRC script
   stored in a file."""

import concurrent.futures as conc
import os

cimport vrc.cython_graph as cython_graph
cimport vrc.loaders.cparser as cparser
cimport vrc.cgraph as cgraph
from libc.stdio cimport puts
from libc.stdlib cimport malloc, free

from . import ClangLoader, ResolutionError
from vrc.cli.commands import GRAPH


cdef extern from "Python.h":
    char* PyUnicode_AsUTF8(object unicode)


cdef char **to_cstring_array(list list_str) except NULL:
    cdef char **ret = <char **>malloc(len(list_str) * sizeof(char *))
    if ret == NULL:
        raise MemoryError()
    for i in xrange(len(list_str)):
        if not isinstance(list_str[i], str):
            free(ret)
            raise TypeError("expected str")
        ret[i] = PyUnicode_AsUTF8(list_str[i])
    return ret


# Export it to Python for testcases.
cpdef int build_graph(str filename, list args, cython_graph.Graph graph, bint verbose) except -1:
    if graph is None:
        raise TypeError("expected CythonGraph")

    cdef char *diagnostic = NULL
    cdef char *c_filename = PyUnicode_AsUTF8(filename) if filename else NULL
    cdef char **c_args = to_cstring_array(args)
    cdef int n_args = len(args)
    cdef cgraph.Graph *g = <cgraph.Graph *> graph.g
    with nogil:
        cparser.build_graph(c_filename, c_args, n_args,
                            g, verbose, &diagnostic)
    free(c_args)
    if diagnostic:
        try:
            raise ResolutionError(diagnostic.decode())
        finally:
            free(diagnostic)

class LibclangLoader(ClangLoader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.force = True

    def get_executor(self):
        # Because build_graph can drop the GIL, a ThreadPoolExecutor can
        # process the files in parallel.
        ncpus = os.cpu_count() or 1
        ntasks = max(2, ncpus) - 1
        return conc.ThreadPoolExecutor(max_workers=ntasks)

    def save_graph(self, filename, args, out_path):
        with open(out_path, 'w') as f:
            print('# using clang loader', file=f)
            build_graph(filename, args, GRAPH,
                        self.verbose_print is print)
