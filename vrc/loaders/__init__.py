"""Abstract classes for loading the call graph."""

import abc
import concurrent.futures as conc
import dataclasses
import os
import re
import shlex
import subprocess
import sys
import typing

from ..cli import source
from ..graph import Graph


@dataclasses.dataclass
class TranslationUnit:
    absolute_path: str
    build_working_dir: str
    build_command: typing.Sequence[str]
    object_file: str

    @classmethod
    def from_compile_commands_json(cls, cmd: dict[str, str]) -> 'TranslationUnit':
        return cls(
            absolute_path=os.path.abspath(os.path.join(cmd["directory"], cmd["file"])),
            build_working_dir=cmd["directory"],
            build_command=shlex.split(cmd["command"]),
            object_file=os.path.abspath(os.path.join(cmd["directory"], cmd["output"])))


class ResolutionError(Exception):
    @property
    def message(self) -> str:
        return str(self.args[0])


@dataclasses.dataclass
class Loader(metaclass=abc.ABCMeta):
    target: Graph
    verbose_print: typing.Callable[[str], None]
    compdb: typing.Mapping[str, TranslationUnit]
    force: bool = False

    def load(self, files: list[str]) -> None:
        executor = self.get_executor()
        futures: set[conc.Future[typing.Tuple[str, str]]] = set()
        for fn in files:
            future = executor.submit(lambda x: (x, self.resolve(x)), fn)
            futures.add(future)

        while futures:
            done, futures = conc.wait(futures, return_when=conc.FIRST_COMPLETED)
            for future in done:
                try:
                    fn, resolved_fn = future.result()
                except ResolutionError as e:
                    print(f"{fn}: {e.message}", file=sys.stderr)
                    continue

                self.verbose_print(f"Reading {resolved_fn}")
                self.parse(resolved_fn)

    def _get_translation_unit(self, fn: str) -> TranslationUnit:
        try:
            return self.compdb[fn]
        except KeyError:
            raise ResolutionError(f"Could not find '{fn}' in compile_commands.json")

    @abc.abstractmethod
    def get_executor(self) -> conc.Executor:
        pass

    @abc.abstractmethod
    def parse(self, fn: str) -> None:
        pass

    @abc.abstractmethod
    def resolve(self, fn: str) -> str:
        pass


class ClangLoader(Loader, metaclass=abc.ABCMeta):
    @staticmethod
    def get_clang_system_include_paths() -> typing.Sequence[str]:
        # libclang does not automatically include clang's standard system include
        # paths, so we ask clang what they are and include them ourselves.
        result = subprocess.run(
            ["clang", "-E", "-", "-v"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # decode output using default encoding
            check=True,
        )

        pattern = (
            r"#include <...> search starts here:\n"
            r"((?: \S*\n)+)"
            r"End of search list."
        )

        match = re.search(pattern, result.stderr, re.MULTILINE)
        assert match is not None
        return [line[1:] for line in match.group(1).splitlines()]

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.system_include_paths = ClangLoader.get_clang_system_include_paths()

    def resolve(self, fn: str) -> str:
        def build_libclang_command_line(tu: TranslationUnit) -> list[str]:
            command = tu.build_command
            return [
                # keep the original compilation command name
                command[0],
                # ignore unknown GCC warning options
                "-Wno-unknown-warning-option",
                # keep all other arguments but the last, which is the file name
                *command[1:-1],
                # add clang system include paths
                *(
                    arg
                    for path in self.system_include_paths
                    for arg in ("-isystem", path)
                ),
                # replace relative path to get absolute location information
                tu.absolute_path,
            ]

        tu = self._get_translation_unit(fn)
        vrc_path = fn + ".vrc"
        if self.force or not os.path.exists(vrc_path):
            args = build_libclang_command_line(tu)
            print(f"Parsing {tu.absolute_path}")
            self.save_graph(fn, args, vrc_path)

        return vrc_path

    @abc.abstractmethod
    def save_graph(self, fn: str, args: list[str], outf: str) -> None:
        pass

    def parse(self, fn: str) -> None:
        with open(fn, "r") as f:
            source(f, False)


def get_loaders() -> typing.Mapping[str, typing.Type[Loader]]:
    from .registry import LOADERS
    return LOADERS
