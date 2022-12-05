subdir('loaders')

conc = declare_dependency(
  link_with: static_library('conc', 'minircu.cc'),
  include_directories: include_directories('.')
)

cgraph = declare_dependency(
  link_with: static_library('cgraph', 'cgraph.cc'),
  dependencies: [conc],
  include_directories: include_directories('.')
)

py.extension_module(
  'cython_graph',
  'cython_graph.pyx',
  dependencies: [cgraph, py_dep],
  subdir: 'vrc',
  install: true,
)
