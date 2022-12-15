tests = [
  'conftest.py',
  'graph.py',
  'graph_lowlevel.py',
  'matchers.py',
  'nfa.py',
]

if py_dep.found()
  tests += ['cython.py']
endif

pyfiles = srcfiles
foreach t: tests
  run_command('ln', '-sf', files(t), meson.current_build_dir(), check: true)
  pyfiles += ['tests' / t]
endforeach

# not required because anyway "python -m build" does not run tests
pytest = find_program('pytest', required: false)
if pytest.found()
  if get_option('pytest_tap')
    test('pytest', pytest, args: [ '--benchmark-disable', '--tap-stream' ],
         env: testenv, protocol: 'tap',
         workdir: meson.project_build_root() / 'tests')
  else
    test('pytest', pytest, args: ['--benchmark-disable' ],
         env: testenv,
         workdir: meson.project_build_root() / 'tests')
  endif
  benchmark('pytest', pytest, args: ['--benchmark-only' ],
            verbose: true,
            env: testenv,
            workdir: meson.project_build_root() / 'tests')
endif

flake8 = find_program('flake8', required: false)
if flake8.found()
  test('flake8', flake8, args: pyfiles,
       env: testenv,
       workdir: meson.project_source_root())
endif

mypy = find_program('flake8', required: false)
if mypy.found()
  test('mypy', mypy, args: [ '-p', 'vrc', '-p', 'tests' ],
       env: testenv,
       workdir: meson.project_source_root())
endif

cpptests = [
  'conc_array_test',
  'conc_set_test',
  'conc_map_test',
]

foreach t: cpptests
  test(t, executable(t, t + '.cc', dependencies: conc))
endforeach
