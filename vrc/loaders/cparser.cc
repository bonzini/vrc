#include "cparser.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include <clang-c/Index.h>

#include "minircu.h"
#include "cgraph.h"

typedef struct VisitorState {
    VisitorState(Graph *g_, const char *filename_, bool verbose_) :
        g(g_), filename(filename_), verbose(verbose_) {}
    Graph *g;
    const char *filename;
    bool verbose;
    CXString current_function{NULL};
    RCUThread t{};
} VisitorState;

typedef enum CXChildVisitResult VisitorFunc(CXCursor cursor, CXCursor parent, VisitorState *state);

#define verbose_print(s, fmt, ...) do {                                     \
    if ((s)->verbose) {                                                     \
        fprintf(stderr, "%s%s%s: " fmt "\n",                                \
		(s)->filename,                                              \
                (s)->filename ? ": " : "",                                  \
                clang_getCString((s)->current_function), ## __VA_ARGS__);   \
    }                                                                       \
} while (0)

void add_external_node(VisitorState *state)
{
    std::lock_guard guard{state->t};

    graph_add_external_node(&state->t, state->g,
                            clang_getCString(state->current_function));
}

void add_node(VisitorState *state, CXCursor c)
{
    std::lock_guard guard{state->t};

    size_t i = graph_add_external_node(&state->t, state->g,
                                       clang_getCString(state->current_function));
    graph_set_defined(&state->t, state->g, i);

    CXSourceLocation loc = clang_getCursorLocation(c);
    CXFile file;
    unsigned int line;
    clang_getSpellingLocation(loc, &file, &line, NULL, NULL);

    CXString file_name = clang_getFileName(file);
    graph_set_location(&state->t, state->g, i, clang_getCString(file_name), line);
    clang_disposeString(file_name);
}

void add_edge(VisitorState *state, CXCursor target, bool is_call)
{
    std::lock_guard guard{state->t};

    CXString target_str = clang_getCursorSpelling(target);

    verbose_print(state, "found %s to %s",
                  is_call ? "call" : "reference",
                  clang_getCString(target_str));

    size_t src = graph_add_external_node(&state->t, state->g,
                                         clang_getCString(state->current_function));
    size_t dest = graph_add_external_node(&state->t, state->g,
                                          clang_getCString(target_str));
    graph_add_edge(&state->t, state->g, src, dest, is_call);
    clang_disposeString(target_str);
}

void add_label(VisitorState *state, CXCursor attr)
{
    CXString attr_str = clang_getCursorSpelling(attr);

    verbose_print(state, "found annotation %s", clang_getCString(attr_str));

    size_t func = graph_add_external_node(&state->t, state->g,
                                          clang_getCString(state->current_function));
    graph_add_label(&state->t, state->g, func, clang_getCString(attr_str));
    clang_disposeString(attr_str);
}

static enum CXChildVisitResult visit(VisitorState *state,
                                     CXCursor c,
                                     VisitorFunc *func)
{
    unsigned result = clang_visitChildren(c, (CXCursorVisitor) func, state);
    return result ? CXChildVisit_Break : CXChildVisit_Continue;
}

enum CXChildVisitResult visit_function_decl(CXCursor c, CXCursor parent, VisitorState *state)
{
    enum CXChildVisitResult result = CXChildVisit_Recurse;

    switch (c.kind) {
    case CXCursor_AnnotateAttr:
        add_label(state, c);
        break;

    default:
        break;
    }
    return result;
}

enum CXChildVisitResult visit_function_body(CXCursor c, CXCursor parent, VisitorState *state)
{
    enum CXChildVisitResult result = CXChildVisit_Recurse;

    switch (c.kind) {
    case CXCursor_AnnotateAttr:
        result = visit_function_decl(c, parent, state);

    case CXCursor_CallExpr:
        {
            CXCursor target = clang_getCursorReferenced(c);
            if (!clang_isInvalid(target.kind)) {
                add_edge(state, target, true);
            }
        }
        break;

    case CXCursor_FunctionDecl:
        {
            CXCursor target = clang_getCursorReferenced(c);
            if (!clang_isInvalid(target.kind)) {
                add_edge(state, target, false);
            }
        }
        break;

    default:
        break;
    }
    return result;
}

enum CXChildVisitResult visit_clang_tu(CXCursor c, CXCursor parent, VisitorState *state)
{
    enum CXChildVisitResult result = CXChildVisit_Recurse;

    switch (c.kind) {
    case CXCursor_FunctionDecl:
        {
            CXString save_current_function = state->current_function;
            state->current_function = clang_getCursorSpelling(c);
            CXSourceLocation loc = clang_getCursorLocation(c);
            if (clang_isCursorDefinition(c) && !clang_Location_isInSystemHeader(loc)) {
                verbose_print(state, "found function definition");
                add_node(state, c);
                result = visit(state, c, visit_function_body);
            } else {
                verbose_print(state, "found function declaration");
                result = visit(state, c, visit_function_decl);
            }
            clang_disposeString(state->current_function);
            state->current_function = save_current_function;
            break;
        }

    default:
        break;
    }
    return result;
}

static void create_parser(CXTranslationUnit &tu, CXIndex &idx,
                          const char *filename, const char *const *args, int num_args,
                          char **diagnostic)
{
    idx = clang_createIndex(1, 1);
    tu = clang_createTranslationUnitFromSourceFile(
        idx, NULL, num_args, args, 0, NULL);

    if (!tu) {
        *diagnostic = strdup("could not create translation unit");
        clang_disposeIndex(idx);
        return;
    }

    CXDiagnosticSet diags = clang_getDiagnosticSetFromTU(tu);
    int num_diag = clang_getNumDiagnosticsInSet(diags);
    for (int i = 0; i < num_diag; i++) {
        CXDiagnostic diag = clang_getDiagnosticInSet(diags, i);
        enum CXDiagnosticSeverity sev = clang_getDiagnosticSeverity(diag);
        clang_disposeDiagnostic(diag);
        if (sev >= CXDiagnostic_Error) {
            *diagnostic = strdup("error parsing C file");
            break;
        }
    }

    clang_disposeDiagnosticSet(diags);
}

void build_graph(const char *filename, const char *const *args, int num_args,
                 Graph *g, bool verbose, char **diagnostic)
{
    CXIndex idx;
    CXTranslationUnit tu;

    create_parser(tu, idx, filename, args, num_args, diagnostic);
    if (!tu) {
        return;
    }

    VisitorState state{g, filename, verbose};
    visit(&state, clang_getTranslationUnitCursor(tu), visit_clang_tu);

    clang_disposeTranslationUnit(tu);
    clang_disposeIndex(idx);
}
