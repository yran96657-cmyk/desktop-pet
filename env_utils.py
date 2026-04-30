import os
import sys
from pathlib import Path


def load_env_file(filename: str = ".env") -> None:
    candidates = []

    env_path = os.environ.get("DESKTOP_PET_ENV_FILE")
    if env_path:
        candidates.append(Path(env_path))

    bundle_dir = getattr(sys, "_MEIPASS", "")
    if bundle_dir:
        candidates.append(Path(bundle_dir) / filename)
    candidates.append(Path.cwd() / filename)
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / filename)
    candidates.append(Path(__file__).resolve().parent / filename)

    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.exists() or not resolved.is_file():
            continue
        seen.add(resolved)

        for raw_line in resolved.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

        break
