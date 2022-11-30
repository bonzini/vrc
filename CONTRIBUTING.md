# Development

`vrc` uses a C extension to parse C source files.  It is possible to
work on the Python code simply by using e.g. `python -m pytest`, but
the C code will not be tested.  `tox` instead will correctly build and
test the C code, but it is slower.

The most efficient development experience is obtained by using `meson`
directly.  `vrc` supports `meson devenv` and `meson test`, so that
tests can be run using `meson test` and the `vrc` tool can be started
using `meson devenv python -m vrc`.

# TODO

* Write documentation
* Change args.verbose_print mechanism to logger
