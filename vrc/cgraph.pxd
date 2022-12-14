"""Cython description of graph.h."""

from libcpp cimport bool as c_bool

cdef extern from "cgraph.h":
    ctypedef struct RCUThread:
        pass

    ctypedef struct Graph:
        pass

    ctypedef struct Iter:
        pass

    Graph *graph_new() nogil;
    void graph_delete(Graph *g);

    size_t graph_add_external_node(RCUThread *rcu, Graph *g, const char *name);
    void graph_set_defined(RCUThread *rcu, Graph *g, size_t i);
    void graph_set_username(RCUThread *rcu, Graph *g, size_t i, const char *username);
    void graph_set_location(RCUThread *rcu, Graph *g, size_t i, const char *file, ssize_t line);
    void graph_add_edge(RCUThread *rcu, Graph *g, size_t caller, size_t callee, c_bool is_call);

    size_t graph_node_count(RCUThread *rcu, Graph *g);
    char *graph_name_by_index(RCUThread *rcu, Graph *g, size_t i);
    char *graph_location_by_index(RCUThread *rcu, Graph *g, size_t i, ssize_t *line);
    char *graph_username_by_index(RCUThread *rcu, Graph *g, size_t i);
    ptrdiff_t graph_get_node(RCUThread *rcu, Graph *g, const char *name);
    c_bool graph_is_node_external(RCUThread *rcu, Graph *g, size_t i);
    c_bool graph_has_edge(RCUThread *rcu, Graph *g, size_t src, size_t dest, c_bool ref_ok);
    c_bool graph_has_call_edge(RCUThread *rcu, Graph *g, size_t src, size_t dest);

    Iter *graph_get_callers(RCUThread *rcu, Graph *g, size_t i);
    Iter *graph_get_callees(RCUThread *rcu, Graph *g, size_t i);
    Iter *graph_get_refs(RCUThread *rcu, Graph *g, size_t i);
    Iter *graph_all_nodes_for_file(RCUThread *rcu, Graph *g, const char *str);
    Iter *graph_all_nodes_for_label(RCUThread *rcu, Graph *g, const char *str);

    void graph_add_label(RCUThread *rcu, Graph *g, size_t i, const char *label);
    c_bool graph_has_label(RCUThread *rcu, Graph *g, size_t i, const char *label);

    const char **graph_all_files(RCUThread *rcu, Graph *g, size_t *n);
    const char **graph_all_labels(RCUThread *rcu, Graph *g, size_t *n);

    void graph_reset_labels(Graph *g);

    void iter_delete(Iter *i);
    ptrdiff_t iter_next(Iter *i);
