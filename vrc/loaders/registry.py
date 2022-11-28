from . import Loader
from .rtl import RTLLoader
import typing

LOADERS: typing.MutableMapping[str, typing.Type[Loader]] = {}
LOADERS['rtl'] = RTLLoader


def _have_clang() -> bool:
    try:
        import clang.cindex    # type: ignore # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


if _have_clang():
    from .clang import ClangCIndexLoader
    LOADERS['clang'] = ClangCIndexLoader
