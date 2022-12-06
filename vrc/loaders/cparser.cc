#include "cparser.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include <clang-c/Index.h>

typedef struct VisitorState {
    const char *filename;
    FILE *outf;
    bool verbose;
    CXString current_function;
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
    fprintf(state->outf, "node --external %s\n", clang_getCString(state->current_function));
}

void add_node(VisitorState *state)
{
    fprintf(state->outf, "node %s\n", clang_getCString(state->current_function));
}

void add_edge(VisitorState *state, CXCursor target, bool is_call)
{
    CXString target_str = clang_getCursorSpelling(target);

    verbose_print(state, "found %s to %s",
                  is_call ? "call" : "reference",
                  clang_getCString(target_str));

    fprintf(state->outf, "edge %s %s %s\n",
            clang_getCString(state->current_function),
            clang_getCString(target_str),
            is_call ? "call" : "ref");

    clang_disposeString(target_str);
}

void add_label(VisitorState *state, CXCursor attr)
{
    CXString attr_str = clang_getCursorSpelling(attr);

    verbose_print(state, "found annotation %s", clang_getCString(attr_str));
    fprintf(state->outf, "label %s %s\n",
            clang_getCString(attr_str),
            clang_getCString(state->current_function));

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
        add_external_node(state);
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
                add_node(state);
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
		 const char *out_path, bool verbose, char **diagnostic)
{
    CXIndex idx;
    CXTranslationUnit tu;

    create_parser(tu, idx, filename, args, num_args, diagnostic);
    if (!tu) {
        return;
    }

    FILE *outf = fopen(out_path, "w");
    if (outf) {
        VisitorState state = {
            .filename = filename,
            .outf = outf,
            .verbose = verbose,
        };
        visit(&state, clang_getTranslationUnitCursor(tu), visit_clang_tu);

        if (ferror(outf)) {
            *diagnostic = strdup("error writing output file");
        }
    } else {
        *diagnostic = strdup("error opening output file");
    }

    fclose(outf);
    clang_disposeTranslationUnit(tu);
    clang_disposeIndex(idx);
}