subdir('loaders')

conc = declare_dependency(
  link_with: static_library('conc', 'minircu.cc'),
  include_directories: include_directories('.')
)

py.extension_module(
  'cython_graph',
  'cython_graph.pyx',
  dependencies: [conc, py_dep],
  subdir: 'vrc',
  install: true,
)
