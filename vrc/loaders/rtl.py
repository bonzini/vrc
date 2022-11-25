import glob
import re
import shlex
import subprocess
import typing

from . import Loader, ResolutionError, TranslationUnit


class RTLLoader(Loader):
    def resolve(self, fn: str) -> str:
        def build_gcc_S_command_line(tu: TranslationUnit, outfile: str) -> list[str]:
            out = []
            was_o = False
            for i in tu.build_command:
                if was_o:
                    i = '/dev/null'
                    was_o = False
                elif i == '-c':
                    i = '-S'
                elif i == '-o':
                    was_o = True
                out.append(i)
            return out + ['-fdump-rtl-expand', '-dumpbase', outfile]

        if not fn.endswith(".o"):
            return fn

        tu = self._get_translation_unit(fn)
        dumps = glob.glob(fn + ".*r.expand")
        if not dumps:
            cmdline = build_gcc_S_command_line(tu, fn)
            self.verbose_print(f"Launching {shlex.join(cmdline)}")
            try:
                result = subprocess.run(cmdline,
                                        stdin=subprocess.DEVNULL)
            except KeyboardInterrupt:
                raise ResolutionError("Interrupt")
            if result.returncode != 0:
                raise ResolutionError(f"Compiler exited with return code {result.returncode}")
            dumps = glob.glob(fn + ".*r.expand")
            if not dumps:
                raise ResolutionError("Compiler did not produce dump file")

        if len(dumps) > 1:
            raise ResolutionError(f"Found more than one dump file: {', '.join(dumps)}")

        return dumps[0]

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
