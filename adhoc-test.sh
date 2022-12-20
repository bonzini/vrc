#!/usr/bin/env bash

set -o errexit -o pipefail -o nounset

if (( $# != 0 )); then
    >&2 echo "Usage: $0"
    exit 2
fi

temp_dir="$( mktemp -d )"
trap 'rm -fr "${temp_dir}"' EXIT

cat > "${temp_dir}/compile_commands.json" <<EOF
[
  {
    "directory": "${temp_dir}",
    "command": "cc -std=c99 -c test.c",
    "file": "${temp_dir}/test.c",
    "output": "${temp_dir}/test.o"
  }
]
EOF

cat > "${temp_dir}/test.c" <<EOF
#define A __attribute__((__annotate__(("hello"))))
typedef void (T)(void) A;
typedef void (*U)(void) A;
typedef void A V A;

struct S {
    V (*f)(void);
    T *g;
    U h;
    A int (*const j)(int);
};

static void func1(void) {}
static A void func2(void) {}

static struct S MY_S = { .f = func1, .g = &func1, .h = (func1) };

static void func3(struct S *s3) A {
    V (*const f)(void);
    f();

    struct S s1, *s2;

    func3(s3);
    s1.f();
    s2->g();
    (*s1.h)();
    (*s2->j)(42);

    s1.f  =  func2;
    s1.g=&func2;
    (s1.h)
        = (func2);
}
EOF

cat > "${temp_dir}/expected-vrc-file" <<EOF
node func1 ${temp_dir}/test.c
node func2 ${temp_dir}/test.c
node func3 ${temp_dir}/test.c
node S::f ${temp_dir}/test.c
node S::g ${temp_dir}/test.c
node S::h ${temp_dir}/test.c
node S::j ${temp_dir}/test.c
label function_pointer S::f
label function_pointer S::g
label function_pointer S::h
label function_pointer S::j
label hello func2
label hello func3
label hello S::g
label hello S::h
label hello S::j
edge S::f func1 call
edge S::g func1 call
edge S::h func1 call
edge func3 func3 call
edge func3 S::f call
edge func3 S::g call
edge func3 S::h call
edge func3 S::j call
edge S::f func2 call
edge S::g func2 call
edge S::h func2 call
EOF

repo_root="$( dirname "$0" | xargs readlink -e )"
cd "${repo_root}"

meson setup build
meson compile -C build

meson devenv -C build python -m vrc -C "${temp_dir}" <<EOF
load --force --loader clang ${temp_dir}/test.o
save ${temp_dir}/vrc-file
EOF

diff <( sort "${temp_dir}/expected-vrc-file" ) <( sort "${temp_dir}/vrc-file" )
