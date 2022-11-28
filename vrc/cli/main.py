"""Implementation of the REPL for the vrc tool."""

# SPDX-License-Identifier: GPL-3.0-or-later

# Copyright (C) 2022 Paolo Bonzini
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import argparse
import itertools
import os
import readline
import sys
import typing

from .commands import VRCCommand, Completer, FileCompleter


class NoUsageFormatter(argparse.HelpFormatter):
    def add_usage(self, usage: typing.Optional[str], actions: typing.Iterable[argparse.Action],
                  groups: typing.Iterable[argparse._ArgumentGroup], prefix: typing.Optional[str] = ...) -> None:
        pass


class MyArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: list[typing.Any], **kwargs: dict[typing.Any, typing.Any]) -> None:
        super().__init__(exit_on_error=False, add_help=False, formatter_class=NoUsageFormatter)

    def format_usage(self) -> str:
        return ""

    def error(self, message: str) -> typing.NoReturn:
        raise argparse.ArgumentError(None, f"{self.prog}: error: {message}" "")


PARSER = MyArgumentParser()


class QuitCommand(VRCCommand):
    """Exits VRC."""
    NAME = ("q", "quit")

    @classmethod
    def run(self, args: argparse.Namespace) -> None:
        sys.exit(0)


class SourceCommand(VRCCommand):
    """Processes the commands in a file."""
    NAME = ("source", ".")

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("file", metavar="FILE", nargs="+")

    @classmethod
    def get_completer(cls, nwords: int) -> Completer:
        return FileCompleter()

    def run(self, args: argparse.Namespace) -> None:
        for fn in args.file:
            with open(fn, "r") as f:
                self.do_source(f, exit_first=True)

    @staticmethod
    def do_source(inf: typing.Iterator[str], exit_first: bool) -> None:
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


class HelpCommand(VRCCommand):
    """Prints the list of commands, or the syntax of a command."""
    NAME = ("help",)
    PARSERS: dict[str, argparse.ArgumentParser] = {}

    @classmethod
    def args(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("command", metavar="COMMAND", nargs="?",
                            help="Show help for given command.")

    @classmethod
    def register(self, command: str, parser: argparse.ArgumentParser) -> None:
        self.PARSERS[command] = parser

    def run(self, args: argparse.Namespace) -> None:
        if args.command and args.command in self.PARSERS:
            self.PARSERS[args.command].print_help()
        else:
            PARSER.print_help()


class CommandCompleter(Completer):
    def get_completions(self, text: str) -> typing.Iterable[str]:
        return sorted(ReadlineInput.CMDCLASSES.keys())


class ReadlineInput:
    CMDCLASSES: dict[str, typing.Type[VRCCommand]] = {}

    @classmethod
    def register(self, command: str, cls: typing.Type[VRCCommand]) -> None:
        self.CMDCLASSES[command] = cls

    def __init__(self, prompt: str) -> None:
        self.prompt = prompt
        readline.parse_and_bind("tab: complete")
        readline.set_completer(self.complete)
        readline.set_completer_delims(' \t')
        readline.set_completion_display_matches_hook(self.display_matches)

    def __iter__(self) -> typing.Iterator[str]:
        return self

    def __next__(self) -> str:
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

    def get_matches(self, text: str) -> list[str]:
        line = readline.get_line_buffer()
        words = line.strip().split()
        nwords = 0
        for n, word in enumerate(words):
            if n > 0 and word.startswith('-'):
                # do not count options (FIXME: this assumes they're all booleans)
                continue
            if n == len(words) - 1 and line[-1] not in " \t":
                # do not count the final word if it is incomplete
                continue
            nwords += 1

        completer = self.get_completer(words, nwords, text)

        # Expand the text that is used for completion
        expansion = completer.try_to_expand(text)
        did_expand = (text != expansion)
        text = expansion

        opts = []
        if words and text.startswith('--') or text == '' or text == '-':
            # ugly...
            opts = sorted(HelpCommand.PARSERS[words[0]]._option_string_actions.keys())

        args = completer.get_completions(text)
        completions = [x for x in itertools.chain(opts, args) if x.startswith(text)]
        if len(completions) == 1 \
                and (text != "" or not completions[0].startswith("-")) \
                and not completions[0].endswith("/"):
            return [completions[0] + " "]
        if len(completions) > 1 and did_expand:
            return [text]
        return sorted(completions)

    def get_completer(self, words: list[str], nwords: int, text: str) -> Completer:
        if nwords == 0:
            return CommandCompleter()
        elif words[0] not in self.CMDCLASSES:
            return Completer()
        else:
            return self.CMDCLASSES[words[0]].get_completer(nwords)

    def display_matches(self, substitution: str, matches: typing.Sequence[str], longest_match_length: int) -> None:
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


def main() -> None:
    if '--help' in sys.argv:
        print('vrc - Call graph querying tool')
        print('Written by Paolo Bonzini')
        sys.exit(0)

    if os.path.exists("compile_commands.json"):
        print("Loading compile_commands.json", file=sys.stderr)
        args = PARSER.parse_args(["compdb", "compile_commands.json"])
        try:
            args.cmdclass().run(args)
        except OSError as e:
            print("Could not load compile_commands.json:", e, file=sys.stderr)

    inf: typing.Iterator[str]
    if os.isatty(0):
        inf = ReadlineInput("(vrc) ")
    else:
        inf = sys.stdin

    SourceCommand.do_source(inf, exit_first=False)


def init_subparsers() -> None:
    subparsers = PARSER.add_subparsers(title="subcommands", help=None, parser_class=MyArgumentParser)
    for cls in VRCCommand.__subclasses__():
        for n in cls.NAME:  # type: ignore
            subp = subparsers.add_parser(n, help=cls.__doc__)
            HelpCommand.register(n, subp)
            ReadlineInput.register(n, cls)
            cls.args(subp)
            subp.set_defaults(cmd=n)
            subp.set_defaults(cmdclass=cls)


init_subparsers()
