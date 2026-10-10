# SPDX-License-Identifier: LicenseRef-EngCalcs-Proprietary

"""Compatibility import for ``opencalcs.workflows``."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("engcalcs.workflows")
