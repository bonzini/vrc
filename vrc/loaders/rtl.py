import re
import typing

from . import Loader


class RTLLoader(Loader):
    def parse_lines(self, fn: str, lines: typing.Iterator[str]) -> None:
        RE_FUNC1 = re.compile(r"^;; Function (\S+)\s*$")
        RE_FUNC2 = re.compile(r"^;; Function (.*)\s+\((\S+)(,.*)?\).*$")
        RE_SYMBOL_REF = re.compile(r'\(symbol_ref [^(]* \( "([^"]*)"', flags=re.X)
        curfunc = None
        for line in lines:
            if line.startswith(";; Function "):
                m = RE_FUNC1.search(line)
                if m:
                    curfunc = m.group(1)
                    self.target.add_node(m.group(1), file=fn)
                    self.verbose_print(f"{fn}: found function {m.group(1)}")
                    continue
                m = RE_FUNC2.search(line)
                if m:
                    curfunc = m.group(2)
                    self.target.add_node(m.group(2), username=m.group(1), file=fn)
                    self.verbose_print(f"{fn}: found function {m.group(1)} ({m.group(2)})")
                    continue
            elif curfunc:
                m = RE_SYMBOL_REF.search(line)
                if m:
                    type = "call" if "(call" in line else "ref"
                    self.verbose_print(f"{fn}: found {type} edge {curfunc} -> {m.group(1)}")
                    self.target.add_edge(curfunc, m.group(1), type)

    def parse(self, fn: str) -> None:
        with open(fn, "r") as f:
            self.parse_lines(fn, f)
