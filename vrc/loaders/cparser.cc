#include "cparser.h"
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include <optional>
#include <utility>

#include <clang-c/Index.h>

#include "minircu.h"
#include "cgraph.h"

typedef struct VisitorState {
    VisitorState(Graph *g_, const char *filename_, bool verbose_) :
        g(g_), filename(filename_), verbose(verbose_) {}
    Graph *g;
    const char *filename;
    bool verbose;
    CXCursor current_function;
    RCUThread t{};
} VisitorState;

#define verbose_print(s, fmt, ...) do {                                     \
    if ((s)->verbose) {                                                     \
        CXString spelling = clang_getCursorSpelling((s)->current_function); \
        fprintf(stderr, "%s%s%s: " fmt "\n",                                \
                (s)->filename,                                              \
                (s)->filename ? ": " : "",                                  \
                clang_getCString(spelling), ## __VA_ARGS__);                \
        clang_disposeString(spelling);                                      \
    }                                                                       \
} while (0)

bool has_function_or_function_pointer_type(CXCursor c)
{
    CXType type = clang_getCursorType(c);
    CXType canonical_type = clang_getCanonicalType(type); // without typedefs

    return canonical_type.kind == CXType_FunctionProto || (
        canonical_type.kind == CXType_Pointer &&
        clang_getPointeeType(canonical_type).kind == CXType_FunctionProto);
}

std::optional<std::string> get_node_name(CXCursor c)
{
    std::optional<std::string> name;

    CXString c_spelling = clang_getCursorSpelling(c);

    switch (c.kind) {
    case CXCursor_FunctionDecl:
        name = clang_getCString(c_spelling);
        break;

    case CXCursor_FieldDecl:
        if (has_function_or_function_pointer_type(c))
        {
            CXCursor parent = clang_getCursorSemanticParent(c);
            CXString struct_spelling = clang_getCursorSpelling(parent);

            name = clang_getCString(struct_spelling) + std::string{"::"}
                + clang_getCString(c_spelling);

            clang_disposeString(struct_spelling);
        }
        break;

    default:
        break;
    }

    clang_disposeString(c_spelling);

    return name;
}

// Crashes if `c` is not a CXCursor_FunctionDecl or CXCursor_FieldDecl.
size_t add_external_node(VisitorState *state, CXCursor c)
{
    auto name = get_node_name(c);
    assert(name);

    return graph_add_external_node(&state->t, state->g, name->c_str());
}

// Crashes if `c` is not a CXCursor_FunctionDecl or CXCursor_FieldDecl.
size_t add_node(VisitorState *state, CXCursor c)
{
    auto name = get_node_name(c);
    assert(name);

    size_t i = graph_add_external_node(&state->t, state->g, name->c_str());
    graph_set_defined(&state->t, state->g, i);

    CXSourceLocation loc = clang_getCursorLocation(c);
    CXFile file;
    unsigned int line;
    clang_getSpellingLocation(loc, &file, &line, NULL, NULL);

    CXString file_name = clang_getFileName(file);
    graph_set_location(&state->t, state->g, i, clang_getCString(file_name), line);
    clang_disposeString(file_name);

    return i;
}

// Only actually adds the edge if `src` and `dst` are CXCursor_FunctionDecl or
// CXCursor_FieldDecl.
void add_edge(VisitorState *state, CXCursor src, CXCursor dst, bool is_call)
{
    auto src_name = get_node_name(src);
    auto dst_name = get_node_name(dst);

    if (src_name && dst_name) {
        verbose_print(state, "found %s from %s to %s",
                      is_call ? "call" : "reference",
                      src_name->c_str(),
                      dst_name->c_str());

        size_t src_i = graph_add_external_node(&state->t, state->g,
                                               src_name->c_str());
        size_t dest_i = graph_add_external_node(&state->t, state->g,
                                                dst_name->c_str());
        graph_add_edge(&state->t, state->g, src_i, dest_i, is_call);
    }
}

// Crashes if `target` is not a CXCursor_FunctionDecl or CXCursor_FieldDecl.
void add_label(VisitorState *state, CXCursor attr, CXCursor target)
{
    CXString attr_str = clang_getCursorSpelling(attr);

    verbose_print(state, "found annotation %s", clang_getCString(attr_str));

    size_t i = add_external_node(state, target);
    graph_add_label(&state->t, state->g, i, clang_getCString(attr_str));
    clang_disposeString(attr_str);
}

// needed because functions cannot be partially specialized
template<typename F, typename... Arg> struct Visitor {
    static enum CXChildVisitResult visit(CXCursor c, F func, Arg&&... arg);
};

template<typename F>
struct Visitor<F>
{
    static enum CXChildVisitResult actual_visitor(CXCursor cursor, CXCursor parent, CXClientData client_data) {
        F *f = (F *)client_data;
        return (*f)(cursor, parent);
    }

    static enum CXChildVisitResult visit(CXCursor c, F func) {
        unsigned result = clang_visitChildren(c, &Visitor<F>::actual_visitor, &func);
        return result ? CXChildVisit_Break : CXChildVisit_Continue;
    }
};

template<typename F, typename T>
struct Visitor<F, T*&>
{
    static enum CXChildVisitResult visit(CXCursor c, F func, T *arg) {
        typedef CXChildVisitResult (*VisitorFunc)(CXCursor, CXCursor, T *);

        unsigned result = clang_visitChildren(c, (CXCursorVisitor) (VisitorFunc) func, arg);
        return result ? CXChildVisit_Break : CXChildVisit_Continue;
    }
};

template<typename F, typename T>
struct Visitor<F, T*>
{
    static enum CXChildVisitResult visit(CXCursor c, F func, T *arg) {
        typedef CXChildVisitResult (*VisitorFunc)(CXCursor, CXCursor, T *);

        unsigned result = clang_visitChildren(c, (CXCursorVisitor) (VisitorFunc) func, arg);
        return result ? CXChildVisit_Break : CXChildVisit_Continue;
    }
};

template<typename F, typename... Arg>
static enum CXChildVisitResult visit(CXCursor c, F func, Arg&&... arg)
{
    return Visitor<F, Arg...>::visit(c, func, std::forward<Arg>(arg)...);
}

// Tries to find the declaration of whatever function or function pointer the
// expression `c` references, even if it is hidden behind
// CXCursor_UnexposedExpr, CXCursor_ParenExpr, or CXCursor_UnaryOperator nodes.
std::optional<CXCursor> find_referenced(CXCursor c)
{
    if (CXCursor ref = clang_getCursorReferenced(c); !clang_Cursor_isNull(ref)) {
        return ref;
    }

    std::optional<CXCursor> referenced;

    visit(c, [&referenced](CXCursor c, CXCursor parent) {
        if (!has_function_or_function_pointer_type(c)) {
            return CXChildVisit_Continue;
        }

        CXCursor ref = clang_getCursorReferenced(c);

        if (clang_Cursor_isNull(ref)) {
            bool traverse = c.kind == CXCursor_UnexposedExpr ||
                            c.kind == CXCursor_ParenExpr ||
                            c.kind == CXCursor_UnaryOperator;
            return traverse ? CXChildVisit_Recurse : CXChildVisit_Continue;
        } else if (!referenced) {
            referenced = ref;
            return CXChildVisit_Continue;
        } else {
            referenced.reset();
            return CXChildVisit_Break;
        }
    });

    return referenced;
}

enum CXChildVisitResult visit_function_body(CXCursor c, CXCursor parent, VisitorState *state)
{
    enum CXChildVisitResult result = CXChildVisit_Recurse;

    switch (c.kind) {
    case CXCursor_CallExpr:
        {
            CXCursor target = clang_getCursorReferenced(c);
            if (!clang_isInvalid(target.kind)) {
                add_edge(state, state->current_function, target, true);
            }
        }
        break;

    case CXCursor_FunctionDecl:
        {
            CXCursor target = clang_getCursorReferenced(c);
            if (!clang_isInvalid(target.kind)) {
                add_edge(state, state->current_function, target, false);
            }
        }
        break;

    default:
        break;
    }
    return result;
}

void retrieve_annotations(VisitorState *state, CXCursor c, CXCursor target)
{
    visit(c, [state, target](CXCursor c, CXCursor parent) {
        if (c.kind == CXCursor_AnnotateAttr) {
            add_label(state, c, target);
        }

        return CXChildVisit_Continue;
    });
}

enum CXChildVisitResult visit_struct(CXCursor c, CXCursor parent, VisitorState *state)
{
    if (c.kind == CXCursor_FieldDecl &&
        has_function_or_function_pointer_type(c)) {
        // found a function pointer field, encode it as a node

        size_t i = add_node(state, c);
        graph_add_label(&state->t, state->g, i, "function_pointer");

        // The field's type is either (1) a typedef, (2) a pointer to a typedef,
        // or (3) a pointer to a non-typedef.

        retrieve_annotations(state, c, c);

        CXType type = clang_getCursorType(c);

        if (type.kind == CXType_Pointer) {
            type = clang_getPointeeType(type);
        }

        if (type.kind == CXType_Typedef) {
            visit(c, [c, state](CXCursor child, CXCursor parent) {
                if (child.kind == CXCursor_TypeRef) {
                    CXCursor typedef_decl = clang_getCursorReferenced(child);
                    retrieve_annotations(state, typedef_decl, c);
                    return CXChildVisit_Break;
                } else {
                    return CXChildVisit_Continue;
                }
            });
        }
    }

    return CXChildVisit_Continue;
}

bool has_empty_spelling(CXCursor c)
{
    CXString spelling = clang_getCursorSpelling(c);
    bool empty = clang_getCString(spelling)[0] == '\0';
    clang_disposeString(spelling);
    return empty;
}

void visit_field_designated_initializer(CXCursor c, VisitorState *state)
{
    std::optional<CXCursor> source;

    visit(c, [state, &source](CXCursor c, CXCursor parent) {
        switch (c.kind)
        {
        case CXCursor_MemberRef:
            if (has_function_or_function_pointer_type(c)) {
                source = clang_getCursorReferenced(c);
                return CXChildVisit_Continue;
            } else {
                return CXChildVisit_Break;
            }

        default:
            if (source && has_function_or_function_pointer_type(c)) {
                if (auto target = find_referenced(c)) {
                    add_edge(state, *source, *target, true);
                }
            }
            return CXChildVisit_Break;
        }
    });
}

enum CXChildVisitResult visit_clang_tu(CXCursor c, CXCursor parent, VisitorState *state)
{
    enum CXChildVisitResult result = CXChildVisit_Recurse;

    switch (c.kind) {
    case CXCursor_FunctionDecl:
        {
            CXCursor save_current_function = state->current_function;
            state->current_function = c;
            CXSourceLocation loc = clang_getCursorLocation(c);
            if (clang_isCursorDefinition(c) && !clang_Location_isInSystemHeader(loc)) {
                verbose_print(state, "found function definition");
                add_node(state, c);
                result = visit(c, visit_function_body, state);
            } else {
                verbose_print(state, "found function declaration");
            }
            retrieve_annotations(state, c, c);
            state->current_function = save_current_function;
            break;
        }

    case CXCursor_StructDecl:
        if (has_empty_spelling(c)) {
            result = CXChildVisit_Continue; // ignore anonymous structs
        } else {
            result = visit(c, visit_struct, state);
        }
        break;

    case CXCursor_InitListExpr:
        // for each field initializer
        visit(c, [state](CXCursor c, CXCursor parent) {
            if (c.kind == CXCursor_UnexposedExpr) {
                // probably a designated initializer
                visit_field_designated_initializer(c, state);
            }
            return CXChildVisit_Continue;
        });
        break;

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
    visit(clang_getTranslationUnitCursor(tu), visit_clang_tu, &state);

    clang_disposeTranslationUnit(tu);
    clang_disposeIndex(idx);
}
