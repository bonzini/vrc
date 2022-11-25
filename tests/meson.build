tests = [
  'commands.py',
  'graph.py',
  'nfa.py',
]

pyfiles = srcfiles
foreach t: tests
  run_command('ln', '-sf', files(t), meson.current_build_dir(), check: true)
  pyfiles += ['tests' / t]
endforeach
test('pytest', py, args: [ '-m', 'pytest' ],
     env: testenv,
     workdir: meson.project_build_root() / 'tests')
test('flake8', find_program('flake8'), args: pyfiles,
     env: testenv,
     workdir: meson.project_source_root())
test('mypy', find_program('mypy'), args: [ '-p', 'vrc', '-p', 'tests' ],
     env: testenv,
     workdir: meson.project_source_root())
