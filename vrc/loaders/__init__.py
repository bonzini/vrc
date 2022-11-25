import abc
import dataclasses
import typing

from vrc.graph import Graph


@dataclasses.dataclass
class Loader(metaclass=abc.ABCMeta):
    target: Graph
    verbose_print: typing.Callable[[str], None]

    @abc.abstractmethod
    def parse(self, fn: str) -> None:
        pass
