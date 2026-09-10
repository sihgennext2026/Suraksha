"""
Imports the three existing pipelines into one process.

Phase_1 and backend/validation both ship a top-level package literally named
`app`, so putting both on `sys.path` makes the second one unreachable — whichever
lands in `sys.modules` first wins, and the loser's submodules silently resolve
against the winner. That is why this module exists rather than a couple of
`sys.path.insert` calls.

The two are loaded differently because they are written differently:

  * Phase_1 uses relative imports throughout (`from . import config`), so its
    package can be bound under any name. It is loaded as `phase1`, and its
    submodules become `phase1.main`, `phase1.ocr`, and so on.
  * backend/validation uses absolute imports (`from app.extractors import ...`),
    so it must keep the name `app`. It gets the real `sys.path` entry.

Neither repository is modified. This is the whole of the coupling between them.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

#: Repository root — services/screening-api/ssb_screening_api/loader.py
REPO_ROOT = Path(__file__).resolve().parents[3]

PHASE1_ROOT = REPO_ROOT / "Phase_1"
VALIDATION_ROOT = REPO_ROOT / "backend" / "validation"
FACEVERIFY_ROOT = REPO_ROOT / "gowtham-pepline" / "src"
CONTRACTS_ROOT = REPO_ROOT / "contracts" / "python"

#: The name Phase_1's `app` package is rebound to inside this process.
PHASE1_ALIAS = "phase1"


class ModuleUnavailable(RuntimeError):
    """
    A pipeline could not be loaded.

    Raised at import time only. Once the service is running, a module that
    cannot produce evidence is reported through the canonical envelope as
    NOT_AVAILABLE rather than by raising — an absence of evidence is a value in
    this contract, never an exception.
    """


def _ensure_path(path: Path) -> None:
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)


def load_phase1() -> ModuleType:
    """
    Binds `Phase_1/app` as the `phase1` package and returns `phase1.main`.

    Relative imports resolve against `__package__`, which the alias sets, so
    `from .detector import DocumentDetector` inside Phase_1 becomes
    `phase1.detector` and never touches the validation service's `app`.
    """
    if PHASE1_ALIAS not in sys.modules:
        package_dir = PHASE1_ROOT / "app"
        init = package_dir / "__init__.py"
        if not init.is_file():
            raise ModuleUnavailable(f"Phase_1 package not found at {package_dir}")

        spec = importlib.util.spec_from_file_location(
            PHASE1_ALIAS,
            init,
            submodule_search_locations=[str(package_dir)],
        )
        if spec is None or spec.loader is None:
            raise ModuleUnavailable(f"Could not build an import spec for {init}")

        package = importlib.util.module_from_spec(spec)
        # Registered before execution so that a submodule importing its own
        # package during exec_module finds it rather than recursing.
        sys.modules[PHASE1_ALIAS] = package
        try:
            spec.loader.exec_module(package)
        except Exception:
            del sys.modules[PHASE1_ALIAS]
            raise

    return importlib.import_module(f"{PHASE1_ALIAS}.main")


def load_validation() -> tuple[ModuleType, ModuleType, Path]:
    """
    Returns `(get_extractor, DocumentValidator, rules_dir)` from backend/validation.

    The rules directory is passed explicitly rather than left to the validator's
    default, because the default is relative to the validator's own file and
    would silently fall back to an empty rule set if the layout ever moved.
    """
    _ensure_path(VALIDATION_ROOT)
    extractors = importlib.import_module("app.extractors")
    validators = importlib.import_module("app.validators.document_validator")
    rules_dir = VALIDATION_ROOT / "app" / "rules"
    if not rules_dir.is_dir():
        raise ModuleUnavailable(f"Validation rules not found at {rules_dir}")
    return extractors, validators, rules_dir


def load_faceverify() -> ModuleType:
    _ensure_path(FACEVERIFY_ROOT)
    return importlib.import_module("faceverify.pipeline")


def load_contracts() -> ModuleType:
    _ensure_path(CONTRACTS_ROOT)
    return importlib.import_module("ssb_contracts")
