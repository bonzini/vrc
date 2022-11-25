project('vrc', [], version: files('VERSION'))

fs = import('fs')
py_mod = import('python')
py = py_mod.find_installation()

srcfiles = [
  'vrc/__init__.py',
  'vrc/__main__.py',
  'vrc/graph.py',
  'vrc/util.py',
  'vrc/automata/__init__.py',
  'vrc/automata/nfa.py',
  'vrc/automata/regex.py',
  'vrc/cli/commands.py',
  'vrc/cli/__init__.py',
  'vrc/cli/main.py',
  'vrc/loaders/clang.py',
  'vrc/loaders/__init__.py',
  'vrc/loaders/registry.py',
  'vrc/loaders/rtl.py',
]

# use a loop to emulate preserve_path: true (added in 0.64)
foreach file: srcfiles
  py.install_sources(file, subdir: fs.parent(file))
endforeach