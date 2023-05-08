"""Implementation of the commands for the vrc tool."""

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import argparse
from . import serialize_graph
from ..matchers import MatchAnd, MatchLabel, parse_nodespec, parse_pathspec
from ..graph import Graph
from ..loaders import TranslationUnit, get_loaders, default_loader
from collections import defaultdict
from contextlib import contextmanager
import glob
import io
import json
import os
import readline
import subprocess
import sys
import typing

GRAPH = Graph()

VALID_OPTIONS = {
    'timing': 'Show execution time after every command.',
}

if 'scalene' in sys.modules:
    VALID_OPTIONS['profiling'] = 'Enable scalene profiler'

_OPTIONS = {key: False for key in VALID_OPTIONS.keys()}


@contextmanager
def open_unlink_on_error(filename: str) -> typing.Iterator[typing.TextIO]:
    # do not unlink an existing file until it has been opened
    do_unlink = not os.path.exists(filename)
    try:
        with open(filename, "w") as f:
            # and never unlink a non-regular file anyway
            do_unlink = do_unlink or os.path.isfile(filename)
            yield f
    except Exception as e:
        if do_unlink:
            os.unlink(filename)
        raise e


class Completer:
    def try_to_expand(self, text: str) -> str:
        return text

    def get_completions(self, text: str) -> typing.Iterable[str]:
        return []


class FileCompleter(Completer):
    def __init__(self, glob_patterns: list[str] = ['*']) -> None:
        self.glob_patterns = glob_patterns

    def try_to_expand(self, text: str) -> str:
        expanded = text
        if text.startswith('~'):
            expanded = os.path.expanduser(expanded)
        if not expanded.endswith("/") and os.path.isdir(expanded):
            expanded += "/"
        return expanded

    def get_completions(self, text: str) -> typing.Iterable[str]:
        result = glob.glob(text + "*/")
        path = os.path.dirname(text)
        if path:
            path += "/"
        for i in self.glob_patterns:
            expanded = glob.glob(path + i)
            result += (x for x in expanded if not os.path.isdir(x))
        return result


class StringsCompleter(Completer):
    def __init__(self, strings: list[str]) -> None:
        self.strings = strings

    def get_completions(self, text: str) -> typing.Iterable[str]:
        return self.strings


class LabelCompleter(Completer):
    def get_completions(self, text: str) -> typing.Iterable[str]:
        return GRAPH.labels()


class NodeCompleter(Completer):
    def get_completions(self, text: str) -> typing.Iterable[str]:
        return set(GRAPH.nodes_by_username.keys()).union(GRAPH.nodes.keys())


class VRCCommand:

    NAME: typing.Optional[tuple[str, ...]] = None

    @staticmethod
    def eat(*args: list[typing.Any]) -> None:
        pass

    @staticmethod
    def positive_int(value: str) -> int:
        number = int(value)
        if number <= 0:
            raise argparse.ArgumentTypeError(f"Number {value} must be positive.")
        return number

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        """Setup argument parser"""
        pass

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return Completer()

    def run(self, args: argparse.Namespace) -> None:
        pass

    def execute(self, args: argparse.Namespace) -> None:
        from resource import getrusage, RUSAGE_SELF
        import time

        r1 = getrusage(RUSAGE_SELF)
        t1 = time.monotonic()
        if _OPTIONS.get('profiling', False):
            from scalene import scalene_profiler             # type: ignore
            scalene_profiler.start()
        try:
            self.run(args)
        finally:
            if _OPTIONS.get('profiling', False):
                from scalene import scalene_profiler
                scalene_profiler.stop()
            r2 = getrusage(RUSAGE_SELF)
            t2 = time.monotonic()
            if _OPTIONS['timing']:
                print('wall {:.3f}s  user {:.3f}s   sys {:.3f}s'
                      .format(t2 - t1, r2.ru_utime - r1.ru_utime, r2.ru_stime - r1.ru_stime))


class ChdirCommand(VRCCommand):
    """Change current directory."""
    NAME = ("cd",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("dir", metavar="DIR",
                            help="New current directory")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        # complete by directory only
        return FileCompleter([]) if nwords == 1 else Completer()

    def run(self, args: argparse.Namespace) -> None:
        os.chdir(os.path.expanduser(args.dir))


class PwdCommand(VRCCommand):
    """Print current directory."""
    NAME = ("pwd",)

    def run(self, args: argparse.Namespace) -> None:
        print(os.getcwd())


class HistoryCommand(VRCCommand):
    """Print command history."""
    NAME = ("history",)

    def run(self, args: argparse.Namespace) -> None:
        # TODO: limit history to N entries
        for i in range(1, readline.get_current_history_length() + 1):
            print('{:7} {}'.format(i, readline.get_history_item(i)))


class CompdbCommand(VRCCommand):
    """Loads a compile_commands.json file."""
    NAME = ("compdb",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--verbose", action="store_const",
                            const=print, default=VRCCommand.eat,
                            help="Report progress while parsing")
        parser.add_argument("file", metavar="FILE",
                            help="JSON file to be loaded")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return FileCompleter(["*.json"]) if nwords == 1 else Completer()

    def run(self, args: argparse.Namespace) -> None:
        with open(args.file, 'r') as f:
            for entry in json.load(f):
                tu = TranslationUnit.from_compile_commands_json(entry)
                args.verbose(f"Added {tu.object_file}")
                COMPDB[tu.object_file] = tu


COMPDB: dict[str, TranslationUnit] = dict()


class LoadCommand(VRCCommand):
    """Loads a GCC RTL output (.expand, generated by -fdump-rtl-expand)."""
    NAME = ("load",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--verbose", action="store_const",
                            const=print, default=VRCCommand.eat,
                            help="Report progress while parsing")
        parser.add_argument("--force", action="store_true",
                            help="Do not use cached result")
        parser.add_argument("--loader", default=default_loader(),
                            help="Pick how to analyze the translation unit")
        parser.add_argument("files", metavar="FILE", nargs="+",
                            help="Dump or object file to be loaded")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return FileCompleter(["*.o", "*r.expand"])

    def run(self, args: argparse.Namespace) -> None:
        def expand_glob(s: str) -> list[str]:
            return glob.glob(s) or [s]

        try:
            loader_class = get_loaders()[args.loader]
        except KeyError:
            print(f"invalid loader {args.loader} (supported loaders: "
                  + f"{', '.join(get_loaders().keys())})", file=sys.stderr)
            return

        loader = loader_class(GRAPH, args.verbose, COMPDB, args.force)

        cwd = os.getcwd()
        files = []
        for pattern in args.files:
            files += expand_glob(os.path.join(cwd, os.path.expanduser(pattern)))
        loader.load(files)


class NodeCommand(VRCCommand):
    """Creates a new node for a symbol."""
    NAME = ("node",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--external", action="store_true",
                            help="Make the symbol external.")
        parser.add_argument("name", metavar="NAME",
                            help="Name for the new node")
        parser.add_argument("file", metavar="FILE", nargs="?",
                            help="File in which the new node is defined")

    def run(self, args: argparse.Namespace) -> None:
        if args.external and args.file:
            raise argparse.ArgumentError(None, "file not allowed for external symbols")
        if args.external:
            GRAPH.add_external_node(args.name)
        else:
            GRAPH.add_node(args.name, file=args.file)


class EdgeCommand(VRCCommand):
    """Creates a new edge.  The caller must exist already."""
    NAME = ("edge",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("caller", metavar="CALLER",
                            help="Source node for the new edge")
        parser.add_argument("callee", metavar="CALLEE",
                            help="Target node for the new edge")
        parser.add_argument("type", metavar="TYPE", nargs="?",
                            help="Type of the new edge (call or ref)",
                            choices=["call", "ref"], default="call")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        if nwords < 3:
            return NodeCompleter()
        if nwords == 3:
            return StringsCompleter(["call", "ref"])
        return Completer()

    def run(self, args: argparse.Namespace) -> None:
        if not GRAPH.has_node(args.caller):
            raise argparse.ArgumentError(None, f"caller not found in graph: {args.caller}")
        if GRAPH.is_node_external(args.caller):
            raise argparse.ArgumentError(None, f"cannot add edge from external node: {args.caller}")
        GRAPH.add_edge(args.caller, args.callee, args.type)


class OmitCommand(VRCCommand):
    """Removes a node, and optionally its callers and/or callees, from
       the graph that is generated by "output", "dotty", or "xdot"."""
    NAME = ("omit",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--callers", action="store_true",
                            help="Omit all callers, recursively.")
        parser.add_argument("--callees", action="store_true",
                            help="Omit all callees, recursively.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return NodeCompleter()

    def run(self, args: argparse.Namespace) -> None:
        matcher = parse_nodespec(" ".join(args.funcs))
        for f in matcher.match_nodes_in_graph(GRAPH):
            if not args.callers and not args.callees:
                GRAPH.omit_node(f)
                continue
            if args.callers:
                for caller in GRAPH.all_callers(f):
                    GRAPH.omit_callers(caller)
            if args.callees:
                for callee in GRAPH.all_callees(f):
                    GRAPH.omit_callees(callee)


class KeepCommand(VRCCommand):
    """Undoes the effect of "omit" on a node, and optionally
       its callers and/or callees."""
    NAME = ("keep",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--callers", action="store_true",
                            help="Keep all callers, recursively.")
        parser.add_argument("--callees", action="store_true",
                            help="Keep all callees, recursively.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return NodeCompleter()

    def run(self, args: argparse.Namespace) -> None:
        matcher = parse_nodespec(" ".join(args.funcs))
        for f in matcher.match_nodes_in_graph(GRAPH):
            GRAPH.keep_node(f)
            if args.callers:
                for caller in GRAPH.all_callers(f):
                    GRAPH.keep_node(caller)
            if args.callees:
                for callee in GRAPH.all_callees(f):
                    GRAPH.keep_node(callee)


class OnlyCommand(VRCCommand):
    """Limits the graph that is generated by "output", "dotty", or "xdot"
       to a node, and optionally its callers and/or callees.
       If invoked multiple times, the filters are ORed.  Nodes
       added by "keep" are included too."""
    NAME = ("only",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--callers", action="store_true",
                            help="Keep all callers, recursively.")
        parser.add_argument("--callees", action="store_true",
                            help="Keep all callees, recursively.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    def run(self, args: argparse.Namespace) -> None:
        matcher = parse_nodespec(" ".join(args.funcs))
        GRAPH.filter_default = False
        for f in matcher.match_nodes_in_graph(GRAPH):
            GRAPH.keep_node(f)
            if args.callers:
                for caller in GRAPH.all_callers(f):
                    GRAPH.keep_node(caller)
            if args.callees:
                for callee in GRAPH.all_callees(f):
                    GRAPH.keep_node(callee)


class LabelCommand(VRCCommand):
    """Applies or queries labels to nodes."""
    NAME = ("label",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("label", metavar="LABEL",
                            help="The label to operate on")
        parser.add_argument("funcs", metavar="FUNCS", nargs="*",
                            help="The functions to be labeled, print currently labeled functions if absent")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return LabelCompleter() if nwords == 1 else NodeCompleter()

    def run(self, args: argparse.Namespace) -> None:
        if args.funcs:
            matcher = parse_nodespec(" ".join(args.funcs))
            for f in matcher.match_nodes_in_graph(GRAPH):
                GRAPH.add_label(f, args.label)
        else:
            for f in GRAPH.labeled_nodes(args.label):
                print(f)


class ResetCommand(VRCCommand):
    """Undoes any filtering done by the "keep" or "omit" commands,
       and/or all labeling."""
    NAME = ("reset",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--filters", action="store_true",
                            help="Reset all filters.")
        parser.add_argument("--labels", action="store_true",
                            help="Reset all labels.")

    def run(self, args: argparse.Namespace) -> None:
        reset_all = not args.labels and not args.filters
        if reset_all or args.filters:
            GRAPH.reset_filter()
        if reset_all or args.labels:
            GRAPH.reset_labels()


class CallersCommand(VRCCommand):
    """Prints the caller of all the specified functions."""
    NAME = ("callers",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return NodeCompleter()

    def run(self, args: argparse.Namespace) -> None:
        matcher = parse_nodespec(" ".join(args.funcs))
        result = defaultdict(lambda: list())
        for f in matcher.match_nodes_in_graph(GRAPH):
            for i in GRAPH.callers(f, ref_ok=args.include_ref):
                result[i].append(f)

        for caller, callees in result.items():
            print(f"{', '.join(callees)} <- {caller}")


class CalleesCommand(VRCCommand):
    """Prints the callees of all the specified functions."""
    NAME = ("callees",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--include-external", action="store_true",
                            help="Include external functions.")
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return NodeCompleter()

    def run(self, args: argparse.Namespace) -> None:
        matcher = parse_nodespec(" ".join(args.funcs))
        result = defaultdict(lambda: list())
        for f in matcher.match_nodes_in_graph(GRAPH):
            for i in GRAPH.callees(f, external_ok=args.include_external, ref_ok=args.include_ref):
                result[i].append(f)

        for callee, callers in result.items():
            print(f"{callee} <- {', '.join(callers)}")


class LabelsCommand(VRCCommand):
    """Prints the labels of all the specified functions."""
    NAME = ("labels",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return NodeCompleter()

    def run(self, args: argparse.Namespace) -> None:
        matcher = parse_nodespec(" ".join(args.funcs))
        result = defaultdict(lambda: list())
        for label in sorted(GRAPH.labels()):
            for f in MatchAnd(MatchLabel(label), matcher).match_nodes_in_graph(GRAPH):
                result[f].append(label)

        for func, labels in result.items():
            print(f"{func}: {', '.join(labels)}")


class SaveCommand(VRCCommand):
    """Creates a command file with the callgraph."""
    NAME = ("save", )

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("file", metavar="FILE", nargs="?")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return FileCompleter() if nwords == 1 else Completer()

    def run(self, args: argparse.Namespace) -> None:
        if args.file:
            fn = os.path.expanduser(args.file)
            with open_unlink_on_error(fn) as f:
                serialize_graph(GRAPH, f)
        else:
            serialize_graph(GRAPH, sys.stdout)


class OutputCommand(VRCCommand):
    """Creates a DOT file with the callgraph.  If invoked as "dotty" or "xdot"
       and with no arguments, the graph is laid out and showed in a graphical
       window."""
    NAME = ("output", "dotty", "xdot")

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--files", action="store_true",
                            help="Create box containers for source files.")
        parser.add_argument("--include-external", action="store_true",
                            help="Include external functions.")
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("file", metavar="FILE", nargs="?")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return FileCompleter() if nwords == 1 else Completer()

    def run(self, args: argparse.Namespace) -> None:
        def emit(f: typing.TextIO) -> None:
            print("digraph callgraph {", file=f)
            nodes: set[str] = set()
            for func in GRAPH.all_nodes(False):
                nodes.add(func)

            if args.files:
                i = 0
                for file in GRAPH.nodes_by_file.keys():
                    file_nodes = list(GRAPH.all_nodes_for_file(file))
                    if not file_nodes:
                        continue
                    print(f"subgraph cluster_{i}", "{", file=f)
                    print(f'label = "{file}";', file=f)
                    for func in file_nodes:
                        print(f'"{func}";', file=f)
                    print("}", file=f)
                    i += 1

            connected = set()
            for func in nodes:
                has_edges = False
                for dest in GRAPH.callees(func, external_ok=args.include_external, ref_ok=args.include_ref):
                    print(f'"{func}" -> "{dest}";', file=f)
                    connected.add(dest)
                    has_edges = True
                if has_edges:
                    connected.add(func)

            for func in nodes:
                if func not in connected:
                    print(f'"{func}";', file=f)

            print("}", file=f)

        if args.file:
            fn = os.path.expanduser(args.file)
            with open_unlink_on_error(fn) as f:
                emit(f)
        elif args.cmd in ["dotty", "xdot"]:
            graph = io.StringIO()
            emit(graph)
            proc = subprocess.Popen(f"{args.cmd} -", stdin=subprocess.PIPE, shell=True,
                                    errors="backslashreplace", encoding="ascii")
            proc.communicate(graph.getvalue())
        else:
            emit(sys.stdout)


class PathsCommand(VRCCommand):
    """Queries callgraph paths using a regular expression language."""

    NAME = ('paths', )

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--include-external", action="store_true",
                            help="Include external functions.")
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("--limit", type=VRCCommand.positive_int,
                            help="Number of paths to print.")
        parser.add_argument("expr", metavar="EXPR", nargs="+")

    def run(self, args: argparse.Namespace) -> None:
        result = parse_pathspec(GRAPH, " ".join(args.expr))
        dfa = result.nfa().lazy_dfa()
        try:
            for path in GRAPH.paths(dfa, args.include_external, args.include_ref, args.limit):
                print(" <- ".join(path))
        except KeyboardInterrupt:
            print("Interrupt", file=sys.stderr)
            return


class EnableCommand(VRCCommand):
    """Enable/disable various CLI options.  Without any arguments,
       the state of the options is shown."""

    NAME = ('enable', 'disable', )

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        for k, v in VALID_OPTIONS.items():
            parser.add_argument(f"--{k}", action="store_true", help=v)

    def run(self, args: argparse.Namespace) -> None:
        value = (args.cmd == 'enable')
        n = 0
        for i in VALID_OPTIONS.keys():
            if getattr(args, i):
                _OPTIONS[i] = value
                n += 1
        if not n:
            for k, v in _OPTIONS.items():
                print(f"{k}: {v}")
