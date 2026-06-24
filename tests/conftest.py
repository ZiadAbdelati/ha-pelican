"""Pytest bootstrap for the HA-free unit tests.

The integration's package ``__init__`` imports Home Assistant, which is
intentionally NOT installed in this dev/test environment — the logic we unit-test
lives in ``api.py`` and has no Home Assistant dependency. Importing
``custom_components.pelican.api`` the normal way would execute that package
``__init__`` (and its ``coordinator``/``const`` imports) and fail with
``ModuleNotFoundError: homeassistant``.

To avoid that, we load ``api.py`` straight from its file and register it in
``sys.modules`` under its real dotted name, without ever executing the package
``__init__``. Tests can then ``from custom_components.pelican.api import ...`` as
usual. At runtime inside Home Assistant the real ``__init__`` is used normally;
this shim only affects the test process.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PKG = "custom_components.pelican"

# Register lightweight namespace packages so importing the api submodule does not
# run custom_components/pelican/__init__.py.
for _name in ("custom_components", _PKG):
    if _name not in sys.modules:
        _module = types.ModuleType(_name)
        _module.__path__ = [str(_ROOT.joinpath(*_name.split(".")))]
        sys.modules[_name] = _module

_spec = importlib.util.spec_from_file_location(
    f"{_PKG}.api", _ROOT / "custom_components" / "pelican" / "api.py"
)
assert _spec is not None and _spec.loader is not None
_api = importlib.util.module_from_spec(_spec)
# Register before exec so @dataclass (which looks up sys.modules[cls.__module__])
# resolves the module while it is still being executed.
sys.modules[f"{_PKG}.api"] = _api
_spec.loader.exec_module(_api)
