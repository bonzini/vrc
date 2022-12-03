"""Load the call graph using the Python bindings to libclang."""

# Authors: Paolo Bonzini <pbonzini@redhat.com>, Alberto Faria <afaria@redhat.com>

import concurrent.futures as conc
import typing

import clang.cindex            # type: ignore

from ctypes import CFUNCTYPE, c_int, py_object
from clang.cindex import (
    Cursor,
    CursorKind,
    conf
)
from enum import Enum

from . import ClangLoader, ResolutionError
from ..cli import serialize_graph
from ..graph import Graph


Cursor.__hash__ = lambda self: self.hash  # so `Cursor`s can be dict keys


class VisitorResult(int, Enum):

    BREAK = 0
    """Terminates the cursor traversal."""

    CONTINUE = 1
    """Continues the cursor traversal with the next sibling of the cursor just
    visited, without visiting its children."""

    RECURSE = 2
    """Recursively traverse the children of this cursor."""


def visit(root: Cursor, visitor: typing.Callable[[Cursor], VisitorResult]) -> bool:
    """
    A simple wrapper around `clang_visitChildren()`.

    The `visitor` callback is called for each visited node, with that node as
    its argument. `root` is NOT visited.

    Unlike a standard `Cursor`, the callback argument will have a `parent` field
    that points to its parent in the AST. The `parent` will also have its own
    `parent` field, and so on, unless it is `root`, in which case its `parent`
    field is `None`. We add this because libclang's `lexical_parent` field is
    almost always `None` for some reason.

    Returns `false` if the visitation was aborted by the callback returning
    `VisitorResult.BREAK`. Returns `true` otherwise.
    """

    exception: typing.Optional[BaseException] = None

    @CFUNCTYPE(c_int, Cursor, Cursor, py_object)  # type: ignore
    def actual_visitor(node: Cursor, parent: Cursor, client_data: Cursor) -> typing.Union[int, bool]:
        try:
            node.parent = client_data

            # several clang.cindex methods need Cursor._tu to be set
            node._tu = client_data._tu
            r = visitor(node)
            if r is VisitorResult.RECURSE:
                return 0 \
                    if conf.lib.clang_visitChildren(node, actual_visitor, node) != 0 \
                    else 1
            else:
                value: typing.Literal[0, 1] = r.value
                return value

        except BaseException as e:
            # Exceptions can't cross into C. Stash it, abort the visitation, and
            # reraise it.
            nonlocal exception
            if exception is None:
                exception = e

            return VisitorResult.BREAK.value

    root.parent = None
    result: int = conf.lib.clang_visitChildren(root, actual_visitor, root)

    if exception is not None:
        raise exception

    return result == 0


class ClangCIndexLoader(ClangLoader):
    def build_graph(self, fn: str, tu_cursor: Cursor) -> Graph:
        file_graph = Graph()
        current_function = ''

        def visit_function_decl(c: Cursor) -> VisitorResult:
            k = c.kind
            if k == CursorKind.ANNOTATE_ATTR:
                self.verbose_print(f"{fn}: {current_function}: found annotation {c.spelling}")
                file_graph.add_external_node(current_function)
                file_graph.add_label(current_function, c.spelling)

            return VisitorResult.RECURSE

        def visit_function_body(c: Cursor) -> VisitorResult:
            k = c.kind
            if k == CursorKind.CALL_EXPR and c.referenced is not None:
                self.verbose_print(f"{fn}: {current_function}: found call to {c.referenced.spelling}")
                file_graph.add_edge(current_function, c.referenced.spelling, type="call")

            if k == CursorKind.FUNCTION_DECL:
                self.verbose_print(f"{fn}: {current_function}: found reference to {c.referenced.spelling}")
                file_graph.add_edge(current_function, c.referenced.spelling, type="ref")

            elif k == CursorKind.ANNOTATE_ATTR:
                self.verbose_print(f"{fn}: {current_function}: found annotation {c.spelling}")
                file_graph.add_label(current_function, c.spelling)

            return VisitorResult.RECURSE

        def visit_clang_tu(c: Cursor) -> VisitorResult:
            k = c.kind
            if k == CursorKind.FUNCTION_DECL:
                nonlocal current_function
                save_current_function = current_function
                current_function = c.spelling
                if c.is_definition():
                    self.verbose_print(f"{fn}: found function definition {current_function}")
                    file_graph.add_node(current_function)
                    visit(c, visit_function_body)
                else:
                    self.verbose_print(f"{fn}: found function declaration {current_function}")
                    visit(c, visit_function_decl)
                current_function = save_current_function
                return VisitorResult.CONTINUE

            return VisitorResult.RECURSE

        visit(tu_cursor, visit_clang_tu)
        return file_graph

    def save_graph(self, fn: str, args: list[str], vrc_path: str) -> None:
        try:
            clang_tu = clang.cindex.TranslationUnit.from_source(
                filename=None, args=args)
        except clang.cindex.TranslationUnitLoadError as e:
            raise ResolutionError(f"Failed to load {fn}") from e

        file_graph = self.build_graph(fn, clang_tu.cursor)
        self.verbose_print(f"Writing {vrc_path}")
        with open(vrc_path, "w") as outf:
            serialize_graph(file_graph, outf)

    def get_executor(self) -> conc.Executor:
        # no parallelism
        return conc.ThreadPoolExecutor(max_workers=1)
