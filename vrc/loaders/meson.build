# C++ is needed to lookup libclang, otherwise LLVM is not found
if not add_languages('cpp', required: false)
  subdir_done()
endif

clang = dependency('Clang', method: 'cmake',
  modules : ['libclang'],
  required: false)
if not clang.found()
  subdir_done()
endif

py.extension_module(
  'cython_loader',
  'cython_loader.pyx',
  'cparser.cc',
  dependencies : [clang, cgraph, py_dep],
  subdir: 'vrc/loaders',
  install: true,
)
