#include "cgraph.h"
#include "conc_array.h"
#include "conc_set.h"
#include "conc_map.h"

#include <unistd.h>
#include <cassert>
#include <memory>
#include <string>

// simple integer iterator type

struct Iter {
    // TODO: iterator invalidation
    Iter () : begin(nullptr), end(nullptr) {}
    Iter (const std::atomic<size_t> *begin_, const std::atomic<size_t> *end_) : begin(begin_), end(end_) {}
    Iter (const size_t *begin_, const size_t *end_) :
        begin(reinterpret_cast<const std::atomic<size_t> *> (begin_)),
        end(reinterpret_cast<const std::atomic<size_t> *> (end_)) {}

    const std::atomic<size_t> *begin;
    const std::atomic<size_t> *end;
};

ptrdiff_t iter_next(Iter *i)
{
    while (i->begin < i->end) {
        auto value = i->begin->load(std::memory_order_relaxed);
        i->begin++;
        if (value != (size_t)-1) {
            return value;
        }
    }
    return -1;
}

void iter_delete(Iter *i)
{
    delete i;
}

// a pretty straightforward conversion of python_graph.py

struct Node
{
    Node(std::string name_) : name(name_) {}

    std::string name{};
    std::string username{};
    std::string file{};
    size_t line{(size_t)-1};
    ConcurrentHashSet<size_t> callers{};
    ConcurrentHashSet<size_t> calls{};
    ConcurrentHashSet<size_t> refs{};
    bool external{true};
};

struct Graph
{
    Graph() :
        node_labels(new ConcurrentStringMap<std::unique_ptr<ConcurrentHashSet<size_t>>>) {}
    ~Graph() {
        delete node_labels;
    }

    ConcurrentList<std::unique_ptr<Node>> nodes_by_index{};
    ConcurrentStringMap<size_t> nodes{};
    ConcurrentStringMap<size_t> nodes_by_username{};
    ConcurrentStringMap<std::unique_ptr<ConcurrentList<size_t>>> nodes_by_file{};
    ConcurrentStringMap<std::unique_ptr<ConcurrentHashSet<size_t>>> *node_labels{};
};

Graph *graph_new()
{
    return new Graph;
}

void graph_delete(Graph *g)
{
    delete g;
}

#define GET_RCU() \
    auto guard = rcu ? std::unique_lock{*rcu} : std::unique_lock{gil_rcu}

size_t graph_add_external_node(RCUThread *rcu, Graph *g, const char *name)
{
    GET_RCU();

    std::string s(name);
    ptrdiff_t i = g->nodes_by_username.get(guard, s, -1);
    if (i != -1) {
        return i;
    }

    i = g->nodes.get(guard, s, -1);
    if (i != -1) {
        return i;
    }

    // Might be inaccessible if there are concurrent adds, but the memory
    // is reclaimed when the graph is destroyed
    i = g->nodes_by_index.add(guard, std::unique_ptr<Node>(new Node(s)));
    return g->nodes.add(guard, s, i);
}

void graph_set_defined(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();

    g->nodes_by_index[i]->external = false;
}

void graph_set_username(RCUThread *rcu, Graph *g, size_t i, const char *username)
{
    GET_RCU();

    if (!g->nodes_by_index[i]->file.empty()) {
        assert(username == g->nodes_by_index[i]->username);
        return;
    }

    std::string s(username);
    g->nodes_by_index[i]->username = s;
    g->nodes_by_username.add(guard, s, i);
}

void graph_set_location(RCUThread *rcu, Graph *g, size_t i, const char *file, ssize_t line)
{
    GET_RCU();

    if (!g->nodes_by_index[i]->file.empty()) {
        return;
    }

    std::string s(file);
    g->nodes_by_index[i]->file = s;
    g->nodes_by_index[i]->line = line;

    auto nodes = g->nodes_by_file.add(guard, s);
    nodes->add(guard, i);
}

void graph_add_edge(RCUThread *rcu, Graph *g, size_t caller, size_t callee, bool is_call)
{
    GET_RCU();

    g->nodes_by_index[callee]->callers.add(guard, caller);
    if (is_call) {
        g->nodes_by_index[caller]->calls.add(guard, callee);
    } else {
        g->nodes_by_index[caller]->refs.add(guard, callee);
    }
}

size_t graph_node_count(RCUThread *rcu, Graph *g)
{
    return g->nodes_by_index.size();
}

char *graph_username_by_index(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();

    const char *username = g->nodes_by_index[i]->username.c_str();
    return strdup(username);
}

char *graph_name_by_index(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();
    return strdup(g->nodes_by_index[i]->name.c_str());
}

char *graph_location_by_index(RCUThread *rcu, Graph *g, size_t i, ssize_t *line)
{
    GET_RCU();
    auto node = g->nodes_by_index[i];
    *line = node->line;
    return strdup(node->file.c_str());
}

ssize_t graph_get_node(RCUThread *rcu, Graph *g, const char *name)
{
    GET_RCU();
    ssize_t i = g->nodes_by_username.get(guard, name, -1);
    if (i != -1)
        return i;

    return g->nodes.get(guard, name, -1);
}

bool graph_is_node_external(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();

    return g->nodes_by_index[i]->external;
}

bool graph_has_edge(RCUThread *rcu, Graph *g, size_t src, size_t dest, bool ref_ok)
{
    GET_RCU();

    if (g->nodes_by_index[src]->calls.includes(guard, dest)) {
        return true;
    }
    if (g->nodes_by_index[dest]->external) {
        return false;
    }
    return ref_ok && g->nodes_by_index[src]->refs.includes(guard, dest);
}

bool graph_has_call_edge(RCUThread *rcu, Graph *g, size_t src, size_t dest)
{
    GET_RCU();

    return g->nodes_by_index[src]->calls.includes(guard, dest);
}


Iter *graph_get_callers(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();

    const auto &nodes = g->nodes_by_index[i]->callers;
    return new Iter(nodes.begin(), nodes.end());
}

Iter *graph_get_callees(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();

    const auto &nodes = g->nodes_by_index[i]->calls;
    return new Iter(nodes.begin(), nodes.end());
}

Iter *graph_get_refs(RCUThread *rcu, Graph *g, size_t i)
{
    GET_RCU();

    const auto &nodes = g->nodes_by_index[i]->refs;
    return new Iter(nodes.begin(), nodes.end());
}

Iter *graph_all_nodes_for_file(RCUThread *rcu, Graph *g, const char *file)
{
    GET_RCU();

    std::string s(file);
    // TODO: check if present
    auto nodes = g->nodes_by_file.get(guard, s, NULL);
    if (!nodes) {
        return new Iter();
    }
    return new Iter(nodes->begin(), nodes->end());
}

Iter *graph_all_nodes_for_label(RCUThread *rcu, Graph *g, const char *label)
{
    GET_RCU();

    std::string s(label);
    // TODO: check if present
    auto nodes = g->node_labels->get(guard, s, NULL);
    if (!nodes) {
        return new Iter();
    }
    return new Iter(nodes->begin(), nodes->end());
}

void graph_add_label(RCUThread *rcu, Graph *g, size_t i, const char *label)
{
    GET_RCU();

    std::string s(label);
    auto nodes = g->node_labels->add(guard, s);
    nodes->add(guard, i);
}

bool graph_has_label(RCUThread *rcu, Graph *g, size_t i, const char *label)
{
    GET_RCU();

    std::string s(label);
    auto nodes = g->node_labels->get(guard, s, NULL);
    return nodes && nodes->includes(guard, i);
}

char **graph_all_files(RCUThread *rcu, Graph *g, size_t *n)
{
    GET_RCU();

    size_t count = g->nodes_by_file.size();
    char **array = (char **) calloc(sizeof(char *), count);
    auto begin = g->nodes_by_file.begin();
    auto end = g->nodes_by_file.end();
    *n = 0;
    for (char **p = array; count-- && begin != end; ++(*n), ++begin, ++p) {
        *p = strdup((*begin).c_str());
    }
    return array;
}

char **graph_all_labels(RCUThread *rcu, Graph *g, size_t *n)
{
    GET_RCU();

    size_t count = g->node_labels->size();
    char **array = (char **) calloc(sizeof(char *), count);
    auto begin = g->node_labels->begin();
    auto end = g->node_labels->end();
    *n = 0;
    for (char **p = array; count-- && begin != end; ++(*n), ++begin, ++p) {
        *p = strdup((*begin).c_str());
    }
    return array;
}

void graph_reset_labels(Graph *g)
{
    auto old = g->node_labels;
    g->node_labels = new ConcurrentStringMap<std::unique_ptr<ConcurrentHashSet<size_t>>>();
    synchronize_rcu();
    delete old;
}
