conc = declare_dependency(
  link_whole: static_library('conc', 'minircu.cc'),
  include_directories: include_directories('.')
)

cgraph = declare_dependency(
  link_with: shared_library('cgraph', 'cgraph.cc',
                            dependencies: [conc],
                            install: true,
                            install_dir: py.get_install_dir(pure: false, subdir: 'vrc')),
  include_directories: include_directories('.')
)

py.extension_module(
  'cython_graph',
  'cython_graph.pyx',
  dependencies: [cgraph, py_dep],
  subdir: 'vrc',
  install: true,
)

subdir('loaders')
