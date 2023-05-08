project('vrc', [], version: files('VERSION'),
        default_options: ['optimization=2', 'debug=true', 'cpp_std=gnu++20'])

fs = import('fs')
py_mod = import('python')
py = py_mod.find_installation()
py_dep = py.dependency(required: true)
add_languages('c', 'cpp', 'cython', required: true)
pure = false

srcfiles = [
  'vrc/__init__.py',
  'vrc/__main__.py',
  'vrc/graph.py',
  'vrc/matchers.py',
  'vrc/python_graph.py',
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

subdir('vrc')

# use a loop to emulate preserve_path: true (added in 0.64)
foreach file: srcfiles
  py.install_sources(file, subdir: fs.parent(file), pure: pure)
endforeach

meson.add_postconf_script(find_program('scripts/build-site-packages.py'))
testenv = { 'PYTHONPATH': meson.current_build_dir() / 'site-packages' }
meson.add_devenv(testenv)
subdir('tests')
