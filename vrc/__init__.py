#! /usr/bin/env python3
import argparse
from collections import defaultdict
import dataclasses
import glob
import io
import json
import os
import re
import readline
import shlex
import subprocess
import sys
import typing


@dataclasses.dataclass
class Node:
    name: str
    callers: set[str]
    callees: dict[str, str]
    username: typing.Optional[str] = None
    external: bool = True

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.callers = set()
        self.callees = dict()

    def __getitem__(self, callee: str) -> str:
        return self.callees[callee]

    def __setitem__(self, callee: str, type: str):
        # A "ref" edge does not override a "call" edge
        if type == "call" or callee not in self.callees:
            self.callees[callee] = type


class Graph:
    nodes: dict[str, Node]
    nodes_by_username: dict[str, Node]
    nodes_by_file: dict[str, list[str]]
    keep: typing.Optional[set[str]]
    omit: set[str]
    filter_default: bool

    def __init__(self):
        self.nodes = {}
        self.nodes_by_username = {}
        self.nodes_by_file = defaultdict(lambda: list())

        self.reset_filter()

    def parse(self, fn: str, lines: typing.Iterator[str], verbose_print) -> None:
        RE_FUNC1 = re.compile(r"^;; Function (\S+)\s*$")
        RE_FUNC2 = re.compile(r"^;; Function (.*)\s+\((\S+)(,.*)?\).*$")
        RE_SYMBOL_REF = re.compile(r'\(symbol_ref [^(]* \( "([^"]*)"', flags=re.X)
        curfunc = None
        for line in lines:
            if line.startswith(";; Function "):
                m = RE_FUNC1.search(line)
                if m:
                    curfunc = m.group(1)
                    self.add_node(m.group(1), file=fn)
                    verbose_print(f"{fn}: found function {m.group(1)}")
                    continue
                m = RE_FUNC2.search(line)
                if m:
                    curfunc = m.group(2)
                    self.add_node(m.group(2), username=m.group(1), file=fn)
                    verbose_print(f"{fn}: found function {m.group(1)} ({m.group(2)})")
                    continue
            elif curfunc:
                m = RE_SYMBOL_REF.search(line)
                if m:
                    type = "call" if "(call" in line else "ref"
                    verbose_print(f"{fn}: found {type} edge {curfunc} -> {m.group(1)}")
                    self.add_edge(curfunc, m.group(1), type)

    def add_external_node(self, name: str) -> None:
        if name not in self.nodes:
            self.nodes[name] = Node(name=name)

    def add_node(self, name: str, username: typing.Optional[str] = None,
                 file: typing.Optional[str] = None) -> None:
        self.add_external_node(name)
        if self.nodes[name].external:
            # This is now a defined node.  It might have a username and a file
            self.nodes[name].external = False
            if username:
                self.nodes[name].username = username
                self.nodes_by_username[username] = self.nodes[name]
            if file:
                self.nodes_by_file[file].append(name)

    def add_edge(self, caller: str, callee: str, type: str) -> None:
        # The caller must exist, but the callee could be external.
        self.add_external_node(callee)
        self.nodes[caller][callee] = type
        self.nodes[callee].callers.add(caller)

    def _get_node(self, name: str) -> typing.Optional[Node]:
        if name in self.nodes_by_username:
            return self.nodes_by_username[name]
        elif name in self.nodes:
            return self.nodes[name]
        else:
            return None

    def has_node(self, name: str) -> bool:
        return bool(self._get_node(name))

    def _visit(self, start: str, targets: typing.Callable[[Node], typing.Iterable[str]]) -> typing.Iterator[str]:
        visited = set()

        def visit(n: Node) -> typing.Iterator[str]:
            if n.name in visited:
                return
            visited.add(n.name)
            yield n.username or n.name
            for caller in targets(n):
                target = self._get_node(caller)
                if target:
                    yield from visit(target)

        n = self._get_node(start)
        if not n:
            return iter({})
        yield from visit(n)

    def all_callers(self, callee: str) -> typing.Iterator[str]:
        return self._visit(callee, lambda n: n.callers)

    def all_callees(self, caller: str) -> typing.Iterator[str]:
        return self._visit(caller, lambda n: n.callees.keys())

    def callers(self, callee: str, ref_ok: bool) -> typing.Iterator[str]:
        n = self._get_node(callee)
        if not n:
            return iter([])
        return (
            self.name(caller)
            for caller in n.callers
            if self.filter_node(caller, True) and self.filter_edge(caller, callee, ref_ok))

    def callees(self, caller: str, external_ok: bool, ref_ok: bool) -> typing.Iterator[str]:
        n = self._get_node(caller)
        if not n:
            return iter([])
        return (self.name(callee)
                for callee in n.callees.keys()
                if self.filter_node(callee, external_ok) and self.filter_edge(caller, callee, ref_ok))

    def all_nodes(self) -> typing.Iterator[str]:
        return (self.name(x)
                for x in self.nodes.keys()
                if self.filter_node(x, False))

    def all_nodes_for_file(self, file: str) -> typing.Iterator[str]:
        return (self.name(x)
                for x in self.nodes_by_file[file]
                if self.filter_node(x, False))

    def name(self, x: str) -> str:
        n = self.nodes[x]
        return n.username or x

    def _filter_node(self, n: Node, external_ok: bool) -> bool:
        if not external_ok and n.external:
            return False
        if self.keep is not None and n.name in self.keep:
            return True
        if n.name in self.omit:
            return False
        return self.filter_default

    def filter_node(self, x: str, external_ok: bool) -> bool:
        n = self._get_node(x)
        if not n:
            return False
        return self._filter_node(n, external_ok)

    def filter_edge(self, caller: str, callee: str, ref_ok: bool) -> bool:
        caller_node = self._get_node(caller)
        callee_node = self._get_node(callee)
        if not caller_node or not callee_node:
            return False
        return caller_node[callee_node.name] == "call" or (ref_ok and not callee_node.external)

    def omit_node(self, name: str) -> None:
        n = self._get_node(name)
        name = n.name if n else name

        self.omit.add(name)
        if self.keep is not None and name in self.keep:
            self.keep.remove(name)

    def keep_node(self, name: str) -> None:
        if self.keep is None:
            self.keep = set()

        n = self._get_node(name)
        name = n.name if n else name

        self.keep.add(name)
        if name in self.omit:
            self.omit.remove(name)

    def reset_filter(self) -> None:
        self.omit = set()
        self.keep = None
        self.filter_default = True


GRAPH = Graph()


class NoUsageFormatter(argparse.HelpFormatter):
    def add_usage(self, usage: typing.Optional[str], actions: typing.Iterable[argparse.Action],
                  groups: typing.Iterable[argparse._ArgumentGroup], prefix: typing.Optional[str] = ...) -> None:
        pass


class MyArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(exit_on_error=False, add_help=False, formatter_class=NoUsageFormatter)

    def format_usage(self):
        return ""

    def error(self, message: str):
        raise argparse.ArgumentError(None, f"{self.prog}: error: {message}" "")


PARSER = MyArgumentParser()


class VRCCommand:

    NAME: typing.Optional[tuple[str, ...]] = None

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        """Setup argument parser"""
        pass

    def run(self, args: argparse.Namespace):
        pass


class ChdirCommand(VRCCommand):
    """Change current directory."""
    NAME = ("cd",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("dir", metavar="DIR",
                            help="New current directory")

    def run(self, args: argparse.Namespace):
        os.chdir(os.path.expanduser(args.dir))


class PwdCommand(VRCCommand):
    """Print current directory."""
    NAME = ("pwd",)

    def run(self, args: argparse.Namespace):
        print(os.getcwd())


class HistoryCommand(VRCCommand):
    """Print command history."""
    NAME = ("history",)

    def run(self, args: argparse.Namespace):
        # TODO: limit history to N entries
        for i in range(1, readline.get_current_history_length() + 1):
            print('{:7} {}'.format(i, readline.get_history_item(i)))


class CompdbCommand(VRCCommand):
    """Loads a compile_commands.json file."""
    NAME = ("compdb",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("file", metavar="FILE",
                            help="JSON file to be loaded")

    def run(self, args: argparse.Namespace):
        with open(args.file, 'r') as f:
            for entry in json.load(f):
                key = os.path.abspath(os.path.join(entry["directory"], entry["output"]))
                COMPDB[key] = entry["command"]

COMPDB: dict[str, str] = dict()


class LoadCommand(VRCCommand):
    """Loads a GCC RTL output (.expand, generated by -fdump-rtl-expand)."""
    NAME = ("load",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        def eat(*args: list[typing.Any]) -> None:
            pass

        def print_stderr(*args: list[typing.Any]) -> None:
            print(*args, file=sys.stderr)

        parser.add_argument("--verbose", action="store_const",
                            const=print_stderr, default=eat,
                            help="Report progress while parsing")
        parser.add_argument("files", metavar="FILE", nargs="+",
                            help="Dump or object file to be loaded")

    def run(self, args: argparse.Namespace):
        def build_gcc_S_command_line(cmd, outfile):
            args = shlex.split(cmd)
            out = []
            was_o = False
            for i in args:
                if was_o:
                    i = '/dev/null'
                    was_o = False
                elif i == '-c':
                    i = '-S'
                elif i == '-o':
                    was_o = True
                out.append(i)
            return out + ['-fdump-rtl-expand', '-dumpbase', outfile]

        def expand_glob(s: str) -> list[str]:
            return glob.glob(s) or [s]

        def resolve(files: typing.Iterator[str]) -> typing.Iterator[str]:
            cwd = os.getcwd()
            for pattern in files:
                for fn in expand_glob(os.path.join(cwd, os.path.expanduser(pattern))):
                    if fn.endswith(".o"):
                        if fn not in COMPDB:
                            print(f"Could not find '{fn}' in compile_commands.json", file=sys.stderr)
                            continue

                        dumps = glob.glob(fn + ".*r.expand")
                        if not dumps:
                            cmdline = build_gcc_S_command_line(COMPDB[fn], fn)
                            args.verbose(f"Launching {shlex.join(cmdline)}")
                            try:
                                result = subprocess.run(cmdline,
                                                        stdin=subprocess.DEVNULL)
                            except KeyboardInterrupt as e:
                                print("Interrupt", file=sys.stderr)
                                break
                            if result.returncode != 0:
                                print(f"Compiler exited with return code {result.returncode}", file=sys.stderr)
                                continue
                            dumps = glob.glob(fn + ".*r.expand")
                            if not dumps:
                                print(f"Compiler did not produce dump file", file=sys.stderr)
                                continue

                        if len(dumps) > 1:
                            print(f"Found more than one dump file: {', '.join(dumps)}", file=sys.stderr)
                            continue

                        print(f"Reading {os.path.relpath(dumps[0])}", file=sys.stderr)
                        yield dumps[0]
                    else:
                        args.verbose(f"Reading {os.path.relpath(fn)}")
                        yield fn

        for fn in resolve(args.files):
            with open(fn, "r") as f:
                GRAPH.parse(fn, f, verbose_print=args.verbose)


class NodeCommand(VRCCommand):
    """Creates a new node for a non-external symbol."""
    NAME = ("node",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("name", metavar="NAME",
                            help="Name for the new node")
        parser.add_argument("file", metavar="FILE", nargs="?",
                            help="File in which the new node is defined")

    def run(self, args: argparse.Namespace):
        GRAPH.add_node(args.name, file=args.file)


class EdgeCommand(VRCCommand):
    """Creates a new edge.  The caller must exist already."""
    NAME = ("edge",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("caller", metavar="CALLER",
                            help="Source node for the new edge")
        parser.add_argument("callee", metavar="CALLEE",
                            help="Target node for the new edge")
        parser.add_argument("type", metavar="TYPE", nargs="?",
                            help="Type of the new edge (call or ref)",
                            choices=["call", "ref"], default="call")

    def run(self, args: argparse.Namespace):
        if not GRAPH.has_node(args.caller):
            raise argparse.ArgumentError(None, "caller not found in graph")
        GRAPH.add_edge(args.caller, args.callee, args.type)


class OmitCommand(VRCCommand):
    """Removes a node, and optionally its callers and/or callees, from
       the graph that is generated by "output" or "dotty"."""
    NAME = ("omit",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--callers", action="store_true",
                            help="Omit all callers, recursively.")
        parser.add_argument("--callees", action="store_true",
                            help="Omit all callees, recursively.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    def run(self, args: argparse.Namespace):
        for f in args.funcs:
            GRAPH.omit_node(f)
            if args.callers:
                for caller in GRAPH.all_callers(f):
                    GRAPH.omit_node(caller)
            if args.callees:
                for callee in GRAPH.all_callees(f):
                    GRAPH.omit_node(callee)


class KeepCommand(VRCCommand):
    """Undoes the effect of "omit" on a node, and optionally
       its callers and/or callees."""
    NAME = ("keep",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--callers", action="store_true",
                            help="Keep all callers, recursively.")
        parser.add_argument("--callees", action="store_true",
                            help="Keep all callees, recursively.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    def run(self, args: argparse.Namespace):
        for f in args.funcs:
            GRAPH.keep_node(f)
            if args.callers:
                for caller in GRAPH.all_callers(f):
                    GRAPH.keep_node(caller)
            if args.callees:
                for callee in GRAPH.all_callees(f):
                    GRAPH.keep_node(callee)


class OnlyCommand(VRCCommand):
    """Limits the graph that is generated by "output" or "dotty"
       to a node, and optionally its callers and/or callees.
       If invoked multiple times, the filters are ORed.  Nodes
       added by "keep" are included too."""
    NAME = ("only",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--callers", action="store_true",
                            help="Keep all callers, recursively.")
        parser.add_argument("--callees", action="store_true",
                            help="Keep all callees, recursively.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    def run(self, args: argparse.Namespace):
        GRAPH.filter_default = False
        for f in args.funcs:
            GRAPH.keep_node(f)
            if args.callers:
                for caller in GRAPH.all_callers(f):
                    GRAPH.keep_node(caller)
            if args.callees:
                for callee in GRAPH.all_callees(f):
                    GRAPH.keep_node(callee)


class ResetCommand(VRCCommand):
    """Undoes any filtering done by the "keep" or "omit" commands."""
    NAME = ("reset",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        pass

    def run(self, args: argparse.Namespace):
        GRAPH.reset_filter()


class CallersCommand(VRCCommand):
    """Prints the caller of all the specified functions."""
    NAME = ("callers",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    def run(self, args: argparse.Namespace):
        result = defaultdict(lambda: list())
        for f in args.funcs:
            for i in GRAPH.callers(f, ref_ok=args.include_ref):
                result[i].append(f)

        for caller, callees in result.items():
            print(f"{caller} -> {', '.join(callees)}")


class CalleesCommand(VRCCommand):
    """Prints the callees of all the specified functions."""
    NAME = ("callees",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--include-external", action="store_true",
                            help="Include external functions.")
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("funcs", metavar="FUNC", nargs="+",
                            help="The functions to be filtered")

    def run(self, args: argparse.Namespace):
        result = defaultdict(lambda: list())
        for f in args.funcs:
            for i in GRAPH.callees(f, external_ok=args.include_external, ref_ok=args.include_ref):
                result[i].append(f)

        for callee, callers in result.items():
            print(f"{', '.join(callers)} -> {callee}")


class OutputCommand(VRCCommand):
    """Creates a DOT file with the callgraph.  If invoked as "dotty" and
       with no arguments, the graph is laid out and showed in a graphical
       window."""
    NAME = ("output", "dotty")

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("--files", action="store_true",
                            help="Create box containers for source files.")
        parser.add_argument("--include-external", action="store_true",
                            help="Include external functions.")
        parser.add_argument("--include-ref", action="store_true",
                            help="Include references to functions.")
        parser.add_argument("file", metavar="FILE", nargs="?")

    def run(self, args: argparse.Namespace):
        def emit(f):
            print("digraph callgraph {", file=f)
            nodes = set()
            for func in GRAPH.all_nodes():
                nodes.add(func)

            if args.files:
                i = 0
                for file in GRAPH.nodes_by_file.keys():
                    file_nodes = list(GRAPH.all_nodes_for_file(file))
                    label = re.match(r'(.*?)\.[0-9]*r\.expand', os.path.relpath(file)).group(1)
                    if not file_nodes:
                        continue
                    print(f"subgraph cluster_{i}", "{", file=f)
                    print(f'label = "{label}";', file=f)
                    for func in file_nodes:
                        print(f'"{func}";', file=f)
                    print("}", file=f)
                    i += 1

            connected = set()
            for func in nodes:
                has_edges = False
                for i in GRAPH.callees(func, external_ok=args.include_external, ref_ok=args.include_ref):
                    print(f'"{func}" -> "{i}";', file=f)
                    connected.add(i)
                    has_edges = True
                if has_edges:
                    connected.add(func)

            for func in nodes:
                if func not in connected:
                    print(f'"{func}";', file=f)

            print("}", file=f)

        if args.file:
            fn = os.path.expanduser(args.file)
            # do not unlink an existing file until it has been opened
            do_unlink = not os.path.exists(args.file)
            try:
                with open(fn, "w") as f:
                    # and never unlink a non-regular file anyway
                    do_unlink = do_unlink or os.path.isfile(args.file)
                    emit(f)
            except Exception as e:
                if do_unlink:
                    os.unlink(fn)
                raise e
        elif args.cmd == "dotty":
            graph = io.StringIO()
            emit(graph)
            dotty = subprocess.Popen("dotty -", stdin=subprocess.PIPE, shell=True,
                                     errors="backslashreplace", encoding="ascii")
            dotty.communicate(graph.getvalue())
        else:
            emit(sys.stdout)


class QuitCommand(VRCCommand):
    """Exits VRC."""
    NAME = ("q", "quit")

    @classmethod
    def run(self, args: argparse.Namespace):
        sys.exit(0)


class HelpCommand(VRCCommand):
    """Prints the list of commands, or the syntax of a command."""
    NAME = ("help",)
    PARSERS: dict[str, argparse.ArgumentParser] = {}

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("command", metavar="COMMAND", nargs="?",
                            help="Show help for given command.")

    @classmethod
    def register(self, command: str, parser: argparse.ArgumentParser):
        self.PARSERS[command] = parser

    def run(self, args: argparse.Namespace):
        if args.command and args.command in self.PARSERS:
            self.PARSERS[args.command].print_help()
        else:
            PARSER.print_help()


class SourceCommand(VRCCommand):
    """Processes the commands in a file."""
    NAME = ("source",)

    @classmethod
    def args(self, parser: argparse.ArgumentParser):
        parser.add_argument("file", metavar="FILE")

    def run(self, args: argparse.Namespace):
        with open(args.file, "r") as f:
            self.do_source(f, exit_first=True)

    @staticmethod
    def do_source(inf: io.TextIOWrapper, exit_first: bool):
        while True:
            try:
                line = next(inf)
            except KeyboardInterrupt:
                break
            except StopIteration:
                break

            line = line.strip()
            if line.startswith('#'):
                continue

            argv = line.split()
            if not argv:
                continue
            try:
                args = PARSER.parse_args(argv)
                try:
                    args.cmdclass().run(args)
                except OSError as e:
                    print(e)
                    if exit_first:
                        break
            except argparse.ArgumentError as e:
                print(e, file=sys.stderr)
                if exit_first:
                    break

class ReadlineInput:
    def __init__(self, prompt: str):
        self.prompt = prompt
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.complete)
        readline.set_completer_delims(' \t')
        readline.set_completion_display_matches_hook(self.display_matches)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return input(self.prompt)
        except EOFError:
            print()
            raise StopIteration

    def complete(self, text: str, state: int) -> typing.Optional[str]:
        if state == 0:
            self.matches = self.get_matches(text)
        if state >= len(self.matches):
            return None
        return self.matches[state]

    def get_matches(self, text: str):
        line = readline.get_line_buffer()
        words = line.strip().split()
        nwords = len(words) - (0 if not line or line[-1] in " \t" else 1)

	    # Expand the text that is used for completion
        replacement = self.get_forced_replacement(words, nwords, text)
        if replacement:
            text = replacement

        completions = self.get_completions(words, nwords, text)
        completions = [x for x in completions if x.startswith(text)]
        if len(completions) == 1 \
            and (text != "" or not completions[0].startswith("-")) \
            and not completions[0].endswith("/"):
            return [completions[0] + " "]
        if len(completions) > 1 and replacement:
            return [replacement]
        return completions

    def get_forced_replacement(self, words: list[str], nwords: int, text: str) -> typing.Optional[str]:
        expanded = text
        if words and words[0] in ['load', 'cd', 'compdb', 'output']:
            if text.startswith('~'):
                expanded = os.path.expanduser(expanded)
            if not expanded.endswith("/") and os.path.isdir(expanded):
                expanded += "/"
        return expanded if expanded != text else None

    def get_completions(self, words: list[str], nwords: int, text: str) -> list[str]:
        if nwords == 0:
            return sorted(HelpCommand.PARSERS.keys())

        opts = []
        if text.startswith('--') or text == '' or text == '-':
            # ugly...
            opts = sorted(HelpCommand.PARSERS[words[0]]._option_string_actions.keys())

        args = []
        if words[0] in ['callers', 'callees', 'keep', 'omit', 'edge']:
            # complete by function name
            args = sorted(set(GRAPH.nodes_by_username.keys()).union(GRAPH.nodes.keys()))
        elif words[0] in ['pwd']:
            pass
        elif words[0] in ['cd']:
            # complete by directory only
            args = sorted(glob.glob(text + '*/'))
        elif words[0] in ['load']:
            # complete by RTL dump, object file or directory
            path = os.path.dirname(text)
            args = glob.glob(path + '/*r.expand')
            args += glob.glob(path + '/*.o')
            args += glob.glob(text + '*/')
            args = sorted(args)
        elif words[0] in ['compdb']:
            # complete by json or directory
            path = os.path.dirname(text)
            args = glob.glob(path + '/*.json')
            args += glob.glob(text + '*/')
            args = sorted(args)
        elif words[0] in ['output', 'source']:
            # complete by any file name
            args = sorted(glob.glob(text + '*'))
            args = [x + "/" if os.path.isdir(x) else x for x in args]

        return opts + args

    def display_matches(self, substitution: str, matches: typing.Sequence[str], longest_match_length: int):
        line_buffer = readline.get_line_buffer()
        columns = os.get_terminal_size()[0]

        print()

        length = longest_match_length * 6 // 5 + 2
        buffer = ""
        for match in matches:
            match += " " * (length - len(match))
            if len(buffer + match) > columns:
                print(buffer.rstrip())
                buffer = ""
            buffer += match

        if buffer:
            print(buffer)

        print(self.prompt, end="")
        print(line_buffer, end="")
        sys.stdout.flush()


def main():
    if os.path.exists("compile_commands.json"):
        print("Loading compile_commands.json", file=sys.stderr)
        args = PARSER.parse_args(["compdb", "compile_commands.json"])
        try:
            args.cmdclass().run(args)
        except OSError as e:
            print("Could not load compile_commands.json:", e, file=sys.stderr)

    if os.isatty(0):
        inf = ReadlineInput("(vrc) ")
    else:
        inf = sys.stdin

    SourceCommand.do_source(inf, exit_first=False)


def init_subparsers():
    subparsers = PARSER.add_subparsers(title="subcommands", help=None, parser_class=MyArgumentParser)
    for cls in VRCCommand.__subclasses__():
        for n in cls.NAME:  # type: ignore
            subp = subparsers.add_parser(n, help=cls.__doc__)
            HelpCommand.register(n, subp)
            cls.args(subp)
            subp.set_defaults(cmd=n)
            subp.set_defaults(cmdclass=cls)


init_subparsers()
if __name__ == "__main__":
    main()
