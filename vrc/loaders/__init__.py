import abc
import dataclasses
import os
import shlex
import sys
import typing

from vrc.graph import Graph


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

    def load(self, fn: str, ) -> None:
        resolved_fn = self.resolve(fn)
        if resolved_fn == fn:
            self.verbose_print(f"Reading {fn}")
        else:
            print(f"Reading {resolved_fn}", file=sys.stderr)

        self.parse(resolved_fn)

    def _get_translation_unit(self, fn: str) -> TranslationUnit:
        try:
            return self.compdb[fn]
        except KeyError:
            raise ResolutionError(f"Could not find '{fn}' in compile_commands.json")

    @abc.abstractmethod
    def parse(self, fn: str) -> None:
        pass

    @abc.abstractmethod
    def resolve(self, fn: str) -> str:
        pass
