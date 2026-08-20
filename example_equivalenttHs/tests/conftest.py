"""Pytest configuration: helper to import the numbered task scripts (e.g. `00_fetch_spectra.py`)
as modules, since their filenames are not valid Python identifiers for a plain `import`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def import_task_script(module_filename: str) -> ModuleType:
    """Import a numbered task script (e.g. "00_fetch_spectra.py") as a Python module.

    Args:
        module_filename: The script's filename, relative to the project root.

    Returns:
        The imported module object.
    """
    script_path = PROJECT_ROOT / module_filename
    assert script_path.exists(), f"Task script not found: {script_path}"
    module_name = script_path.stem
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None, f"Could not create spec for {script_path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
