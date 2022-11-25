tests = [
  'commands.py',
  'graph.py',
  'nfa.py',
]

if py_dep.found()
  tests += ['cython.py']
endif

foreach t: tests
  run_command('ln', '-sf', files(t), meson.current_build_dir(), check: true)
endforeach
test('pytest', py, args: [ '-m', 'pytest' ],
     env: testenv,
     workdir: meson.project_build_root() / 'tests',
     is_parallel: false,
     verbose: true)
