#ifndef GRAPH_H
#define GRAPH_H 1

#include <stddef.h>
#include <stdbool.h>
#include <unistd.h>

typedef struct Graph Graph;
typedef struct Iter Iter;
typedef struct RCUThread RCUThread;

#ifdef __cplusplus
extern "C" {
#endif

Graph *graph_new();
void graph_delete(Graph *g);

size_t graph_add_external_node(RCUThread *rcu, Graph *g, const char *name);
void graph_set_defined(RCUThread *rcu, Graph *g, size_t i);
void graph_set_username(RCUThread *rcu, Graph *g, size_t i, const char *username);
void graph_set_location(RCUThread *rcu, Graph *g, size_t i, const char *username, ssize_t line);
void graph_add_edge(RCUThread *rcu, Graph *g, size_t caller, size_t callee, bool is_call);
size_t graph_node_count(RCUThread *rcu, Graph *g);
char *graph_username_by_index(RCUThread *rcu, Graph *g, size_t i);
char *graph_name_by_index(RCUThread *rcu, Graph *g, size_t i);
char *graph_location_by_index(RCUThread *rcu, Graph *g, size_t i, ssize_t *line);
ptrdiff_t graph_get_node(RCUThread *rcu, Graph *g, const char *name);
bool graph_is_node_external(RCUThread *rcu, Graph *g, size_t i);
bool graph_has_edge(RCUThread *rcu, Graph *g, size_t src, size_t dest, bool ref_ok);
bool graph_has_call_edge(RCUThread *rcu, Graph *g, size_t src, size_t dest);

Iter *graph_get_callers(RCUThread *rcu, Graph *g, size_t i);
Iter *graph_get_callees(RCUThread *rcu, Graph *g, size_t i);
Iter *graph_get_refs(RCUThread *rcu, Graph *g, size_t i);
Iter *graph_all_nodes_for_file(RCUThread *rcu, Graph *g, const char *str);
Iter *graph_all_nodes_for_label(RCUThread *rcu, Graph *g, const char *str);

void graph_add_label(RCUThread *rcu, Graph *g, size_t i, const char *label);
bool graph_has_label(RCUThread *rcu, Graph *g, size_t i, const char *label);

char **graph_all_files(RCUThread *rcu, Graph *g, size_t *n);
char **graph_all_labels(RCUThread *rcu, Graph *g, size_t *n);

void graph_reset_labels(Graph *g);

void iter_delete(Iter *i);
ptrdiff_t iter_next(Iter *i);


#ifdef __cplusplus
}
#endif

#endif
