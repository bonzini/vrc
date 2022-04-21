# vrc

vrc is a tool to read the call graph from GCC RTL dumps.  It is inspired
by the `[egypt]` tool ("egypt" is rot13 for "rtlcg" aka RTL call graph),
with a lot of new functionality:

- interactive mode with readline + completion

- query call graph in addition to generating DOT file

- consult `compile_commands.json` to find/build dumps automatically

- virtual (manually created) nodes and edges

The name is unfortunately not rot13 anymore.  It stands for "visit RTL
callgraph".

## Installation

`pip install --user .` will install an executable called `vrc`.
