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

pytest = find_program('pytest')
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

test('flake8', find_program('flake8'), args: pyfiles,
     env: testenv,
     workdir: meson.project_source_root())
test('mypy', find_program('mypy'), args: [ '-p', 'vrc', '-p', 'tests' ],
     env: testenv,
     workdir: meson.project_source_root())

cpptests = [
  'conc_array_test',
  'conc_set_test',
  'conc_map_test',
]

foreach t: cpptests
  test(t, executable(t, t + '.cc', dependencies: conc))
endforeach
