import concurrent.futures as conc
import os

cimport vrc.loaders.cparser as cparser
from libc.stdio cimport puts
from libc.stdlib cimport malloc, free

from . import ClangLoader, ResolutionError
from vrc.cli.commands import VRCCommand


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


cpdef int build_graph(str filename, list args, str out_path, bint verbose) except -1:
    if not out_path:
        raise TypeError("expected str")

    cdef char *diagnostic = NULL
    cdef char *c_filename = PyUnicode_AsUTF8(filename) if filename else NULL
    cdef char **c_args = to_cstring_array(args)
    cdef int n_args = len(args)
    cdef char *c_out_path = PyUnicode_AsUTF8(out_path)
    with nogil:
        cparser.build_graph(c_filename, c_args, n_args,
                            c_out_path, verbose, &diagnostic)
    free(c_args)
    if diagnostic:
        try:
            raise ResolutionError(diagnostic.decode())
        finally:
            free(diagnostic)

class LibclangLoader(ClangLoader):
    def get_executor(self):
        ntasks = (os.cpu_count() or 2) - 1
        return conc.ThreadPoolExecutor(max_workers=ntasks)

    def save_graph(self, filename, args, out_path):
        build_graph(filename, args, out_path,
                    self.verbose_print is VRCCommand.print_stderr)
