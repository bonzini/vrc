from libcpp cimport bool as c_bool

cdef extern from "cparser.h":
    void build_graph(const char *filename, const char *const *args, int num_args,
                     const char *out_path, c_bool verbose, char **diagnostic) nogil;
