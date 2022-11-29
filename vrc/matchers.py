"""Matching syntax for individual nodes."""

import abc
import compynator.core         # type: ignore
import dataclasses
import re
import typing

from .automata import nfa
from .graph import Graph


class Matcher(metaclass=abc.ABCMeta):
    def match_nodes_in_graph(self, g: Graph) -> typing.Iterator[str]:
        func = self.as_callable(g)
        return (node for node in g.all_nodes(True) if func(node))

    @abc.abstractmethod
    def as_callable(self, g: Graph) -> nfa.Matcher:
        pass


@dataclasses.dataclass
class MatchByName(Matcher):
    node: str

    def match_nodes_in_graph(self, g: Graph) -> typing.Iterator[str]:
        if g.has_node(self.node):
            yield self.node

    def as_callable(self, g: Graph) -> nfa.Matcher:
        return self.node.__eq__


@dataclasses.dataclass
class MatchByRegex(Matcher):
    pat: re.Pattern[str]

    def __init__(self, regex: str):
        self.pat = re.compile(regex)

    def as_callable(self, g: Graph) -> nfa.Matcher:
        return lambda x: bool(self.pat.search(x))


@dataclasses.dataclass
class MatchLabel(Matcher):
    label: str

    def match_nodes_in_graph(self, g: Graph) -> typing.Iterator[str]:
        yield from g.labeled_nodes(self.label)

    def as_callable(self, g: Graph) -> nfa.Matcher:
        return lambda x: x in g.labeled_nodes(self.label)


@dataclasses.dataclass
class MatchAnd(Matcher):
    matchers: typing.Iterable[Matcher]

    def __init__(self, *matchers: Matcher):
        self.matchers = matchers

    def match_nodes_in_graph(self, g: Graph) -> typing.Iterator[str]:
        i = iter(self.matchers)
        try:
            nodes = set(next(i).match_nodes_in_graph(g))
        except StopIteration:
            yield from g.all_nodes(True)
            return

        for matcher in i:
            nodes = nodes.intersection(matcher.match_nodes_in_graph(g))
        yield from nodes

    def as_callable(self, g: Graph) -> nfa.Matcher:
        callables = [matcher.as_callable(g) for matcher in self.matchers]
        return lambda x: all((c(x) for c in callables))


@dataclasses.dataclass
class MatchNot(Matcher):
    matcher: Matcher

    def match_nodes_in_graph(self, g: Graph) -> typing.Iterator[str]:
        result = set(g.all_nodes(True))
        for node in self.matcher.match_nodes_in_graph(g):
            result.remove(node)
        yield from result

    def as_callable(self, g: Graph) -> nfa.Matcher:
        c = self.matcher.as_callable(g)
        return lambda x: not c(x)


@dataclasses.dataclass
class MatchOr(Matcher):
    matchers: typing.Iterable[Matcher]

    def __init__(self, *matchers: Matcher):
        self.matchers = matchers

    def match_nodes_in_graph(self, g: Graph) -> typing.Iterator[str]:
        i = iter(self.matchers)
        try:
            nodes = set(next(i).match_nodes_in_graph(g))
        except StopIteration:
            return

        for matcher in i:
            nodes.update(matcher.match_nodes_in_graph(g))

        yield from nodes

    def as_callable(self, g: Graph) -> nfa.Matcher:
        callables = [matcher.as_callable(g) for matcher in self.matchers]
        return lambda x: any((c(x) for c in callables))


Parser = typing.Callable[[str], typing.Union[compynator.core.Success, compynator.core.Failure]]

Space = compynator.core.One.where(str.isspace)
Spaces = Space.repeat(lower=0, reducer=lambda x, y: None)


def separated_repeat(node: typing.Any, sep: typing.Optional[typing.Any] = None) -> typing.Any:
    node = node.value(lambda x: [x])
    sep = Spaces.then(sep) if sep else Spaces
    rest = sep.then(node).repeat(value=[])
    return Spaces.then(node + rest).skip(Spaces)


@typing.no_type_check
def _node_matcher_parser() -> Parser:
    from compynator.core import One, Terminal, Succeed

    WordChar = One.where(lambda c: c.isalnum() or c == '_' or c == '.')
    Word = WordChar.repeat(lower=1)

    Quoted = (One.where(lambda c: c == '\\').then(One.where(lambda c: True))
              | One.where(lambda c: c not in r'\"')).repeat()
    Quoted = Terminal('"').then(Quoted).skip(Terminal('"'))

    Regex = (One.where(lambda c: c == '\\').then(One.where(lambda c: True))
             | One.where(lambda c: c not in r'\/')).repeat()
    Regex = Terminal('/').then(Regex).skip(Terminal('/'))

    Inside = Word.value(MatchLabel)
    Inside = separated_repeat(Inside, Terminal(','))

    AllLabels = Terminal('[').then(Inside.value(lambda args: MatchAnd(*args)) | Succeed(MatchAnd())).skip(Terminal(']'))
    NoLabels = Terminal('![').then(Inside.value(lambda args: MatchNot(MatchOr(*args)))).skip(Terminal(']'))

    return AllLabels | NoLabels | Regex.value(MatchByRegex) | (Word | Quoted).value(MatchByName)


Node = _node_matcher_parser()
