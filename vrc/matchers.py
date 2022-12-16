"""Matching syntax for nodes and regular paths."""

import abc
import compynator.core         # type: ignore
import dataclasses
import re
import typing

from .automata import nfa, regex
from .graph import GraphMixin


class Matcher(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        pass

    @abc.abstractmethod
    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        pass


@dataclasses.dataclass
class MatchByName(Matcher):
    node: str

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        if g.has_node(self.node):
            yield self.node

    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        return self.node.__eq__


class FuncMatcher(Matcher):
    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        func = self.as_callable(g)
        return (node for node in g.all_nodes(True) if func(node))


@dataclasses.dataclass
class MatchByRegex(FuncMatcher):
    pat: re.Pattern[str]

    def __init__(self, regex: str):
        self.pat = re.compile(regex)

    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        return lambda x: bool(self.pat.search(x))


@dataclasses.dataclass
class MatchWrapper(Matcher):
    matcher: Matcher

    def __new__(cls, matcher: Matcher) -> Matcher:   # type: ignore
        if isinstance(matcher, MatchWrapper):
            assert not isinstance(matcher.matcher, MatchWrapper)
            return matcher.matcher
        else:
            return super().__new__(cls)

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        return self.matcher.match_nodes_in_graph(g)

    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        return self.matcher.as_callable(g)


@dataclasses.dataclass
class MatchAnd(Matcher):
    matchers: typing.Iterable[Matcher]

    def __new__(cls, *matchers: Matcher) -> Matcher:   # type: ignore
        if len(matchers) == 1:
            return MatchWrapper(matchers[0])
        else:
            return super().__new__(cls)

    def __init__(self, *matchers: Matcher):
        self.matchers = matchers

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        i = iter(self.matchers)
        try:
            nodes = set(next(i).match_nodes_in_graph(g))
        except StopIteration:
            yield from g.all_nodes(True)
            return

        for matcher in i:
            nodes = nodes.intersection(matcher.match_nodes_in_graph(g))
        yield from nodes

    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        callables = [matcher.as_callable(g) for matcher in self.matchers]
        return lambda x: all((c(x) for c in callables))


@dataclasses.dataclass
class MatchNot(Matcher):
    matcher: Matcher

    def __new__(cls, matcher: Matcher) -> Matcher:   # type: ignore
        if isinstance(matcher, MatchNot):
            assert not isinstance(matcher.matcher, MatchNot)
            return matcher.matcher
        else:
            return super().__new__(cls)

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        result = set(g.all_nodes(True))
        for node in self.matcher.match_nodes_in_graph(g):
            result.remove(node)
        yield from result

    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        c = self.matcher.as_callable(g)
        return lambda x: not c(x)


@dataclasses.dataclass
class MatchOr(Matcher):
    matchers: typing.Iterable[Matcher]

    def __new__(cls, *matchers: Matcher) -> Matcher:   # type: ignore
        if len(matchers) == 1:
            return MatchWrapper(matchers[0])
        else:
            return super().__new__(cls)

    def __init__(self, *matchers: Matcher):
        self.matchers = matchers

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        i = iter(self.matchers)
        try:
            nodes = set(next(i).match_nodes_in_graph(g))
        except StopIteration:
            return

        for matcher in i:
            nodes.update(matcher.match_nodes_in_graph(g))

        yield from nodes

    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        callables = [matcher.as_callable(g) for matcher in self.matchers]
        return lambda x: any((c(x) for c in callables))


class CachingMatcher(Matcher):
    def as_callable(self, g: GraphMixin) -> nfa.Matcher:
        nodes = list(self.match_nodes_in_graph(g))
        return nodes.__contains__


@dataclasses.dataclass
class MatchLabel(CachingMatcher):
    label: str

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        yield from g.labeled_nodes(self.label)


@dataclasses.dataclass
class MatchCallees(CachingMatcher):
    matcher: Matcher

    def __init__(self, matcher: Matcher):
        self.matcher = matcher

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        # TODO: what to do about external_ok/ref_ok?
        nodes: set[str] = set()
        for n in self.matcher.match_nodes_in_graph(g):
            nodes.update(g.callees(n, False, False))

        yield from nodes


@dataclasses.dataclass
class MatchCallers(CachingMatcher):
    matcher: Matcher

    def __init__(self, matcher: Matcher):
        self.matcher = matcher

    def match_nodes_in_graph(self, g: GraphMixin) -> typing.Iterator[str]:
        # TODO: what to do about ref_ok?
        nodes: set[str] = set()
        for n in self.matcher.match_nodes_in_graph(g):
            nodes.update(g.callers(n, False))

        yield from nodes


Parser = typing.Callable[[str], typing.Union[compynator.core.Success, compynator.core.Failure]]

Space = compynator.core.One.where(str.isspace)
Spaces = Space.repeat(lower=0, reducer=lambda x, y: None)


_T = typing.TypeVar('_T')


def _compose(*args: typing.Callable[[_T], _T]) -> typing.Callable[[_T], _T]:
    def result(x: _T) -> _T:
        for f in args:
            x = f(x)
        return x

    return result


def separated_repeat(node: typing.Any, sep: typing.Optional[typing.Any] = None) -> typing.Any:
    node = Spaces.then(node).value(lambda x: [x])
    sep = Spaces.then(sep) if sep else Spaces
    rest = sep.then(node).repeat(value=[])
    return (node + rest).skip(Spaces)


@typing.no_type_check
def _node_matcher_parser() -> Parser:
    from compynator.core import One, Terminal, Succeed
    from compynator.niceties import Forward                # type: ignore

    WordChar = One.where(lambda c: c.isalnum() or c == '_' or c == '.')
    Word = WordChar.repeat(lower=1)

    Quoted = (One.where(lambda c: c == '\\').then(One.where(lambda c: True))
              | One.where(lambda c: c not in r'\"')).repeat()
    Quoted = Terminal('"').then(Quoted).skip(Terminal('"'))

    Regex = (One.where(lambda c: c == '\\').then(One.where(lambda c: True))
             | One.where(lambda c: c not in r'\/')).repeat()
    Regex = Terminal('/').then(Regex).skip(Terminal('/'))

    Operator = \
        Terminal(':callees').value(lambda x: [MatchCallees]) | \
        Terminal(':callers').value(lambda x: [MatchCallers])
    Operators = Spaces.then(Operator).repeat(value=[]).value(lambda args: _compose(*args))

    Disjunction = Forward()
    Paren = Terminal('[').then(Disjunction).skip(Terminal(']'))
    Common = Quoted.value(MatchByName) | Regex.value(MatchByRegex) | Paren

    Inside = Common | Word.value(MatchLabel) | Succeed(MatchAnd())
    Inside = Terminal('!').then(Inside).value(MatchNot) | Inside
    Inside = Inside.then(Operators, reducer=lambda x, y: y(x))

    Conjunction = separated_repeat(Inside, Terminal(',')).value(lambda args: MatchAnd(*args))
    Disjunction.is_(separated_repeat(Conjunction, Terminal('|')).value(lambda args: MatchOr(*args)))

    Outside = Common | Word.value(MatchByName)
    Outside = Terminal('!').then(Outside).value(MatchNot) | Outside
    Outside = Outside.then(Operators, reducer=lambda x, y: y(x))
    return Spaces.then(Outside)


Node = _node_matcher_parser()
Nodes = separated_repeat(Node).value(lambda args: MatchOr(*args))


@typing.no_type_check
def _path_regex_parser(g: GraphMixin) -> Parser:
    from compynator.core import Terminal
    from compynator.niceties import Forward

    Alt = Forward()
    Paren = Terminal('(').then(Alt).skip(Terminal(')'))
    Atom = Node.value(lambda x: regex.One(x.as_callable(g))) | Paren

    Star = Atom.then(Terminal('*').repeat(lower=0, upper=1), reducer=lambda x, y: x if not y else regex.Star(x))
    Any = Terminal('...').value(regex.Star(regex.One(lambda x: True)))

    Sequence = separated_repeat(Any | Star).value(lambda args: regex.Sequence(*args))
    Alt.is_(separated_repeat(Sequence, Terminal('|')).value(lambda args: regex.Alt(*args)))
    return Alt


Path = _path_regex_parser


class ParseError(Exception):
    @property
    def message(self) -> str:
        return str(self.args[0])


def _compynator_parse(p: Parser, s: str) -> typing.Any:
    results = p(s)
    if not isinstance(results, compynator.core.Success):
        raise ParseError(f"invalid search terms at '{s}'")
    result = next(iter(results))
    if result.remain:
        raise ParseError(f"invalid search terms at '{result.remain}'")
    return result.value


def parse_nodespec(s: str) -> Matcher:
    return _compynator_parse(Nodes, s)  # type: ignore


def parse_pathspec(g: GraphMixin, s: str) -> regex.RegexAST:
    return _compynator_parse(Path(g), s)  # type: ignore
