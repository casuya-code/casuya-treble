import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent


def load_service_router(service_folder: str, module: str = "router") -> ModuleType:
    path = ROOT / service_folder / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"{service_folder}.{module}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded
