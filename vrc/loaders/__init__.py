import abc
import dataclasses
import sys
import typing

from vrc.graph import Graph


class ResolutionError(Exception):
    @property
    def message(self) -> str:
        return str(self.args[0])


@dataclasses.dataclass
class Loader(metaclass=abc.ABCMeta):
    target: Graph
    verbose_print: typing.Callable[[str], None]
    compiler_cmd: typing.Callable[[str], typing.Sequence[str]]

    def load(self, fn: str, ) -> None:
        resolved_fn = self.resolve(fn)
        if resolved_fn == fn:
            self.verbose_print(f"Reading {fn}")
        else:
            print(f"Reading {resolved_fn}", file=sys.stderr)

        self.parse(resolved_fn)

    def _get_compiler_cmdline(self, fn: str) -> typing.Sequence[str]:
        try:
            return self.compiler_cmd(fn)
        except KeyError:
            raise ResolutionError(f"Could not find '{fn}' in compile_commands.json")

    @abc.abstractmethod
    def parse(self, fn: str) -> None:
        pass

    @abc.abstractmethod
    def resolve(self, fn: str) -> str:
        pass
