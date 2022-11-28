"""Registry of available methods to load the call graph."""

from . import Loader
from .rtl import RTLLoader
import typing

LOADERS: typing.MutableMapping[str, typing.Type[Loader]] = {}
LOADERS['rtl'] = RTLLoader


def _have_cython_clang() -> bool:
    try:
        from .cython_loader import LibclangLoader  # type: ignore # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _have_clang() -> bool:
    try:
        import clang.cindex           # type: ignore # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


if _have_clang():
    from .clang import ClangCIndexLoader
    LOADERS['clang'] = ClangCIndexLoader
    LOADERS['pyclang'] = ClangCIndexLoader
if _have_cython_clang():
    from .cython_loader import LibclangLoader
    LOADERS['clang'] = LibclangLoader
