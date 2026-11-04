"""Load only the two supported settings from an ignored, local configuration file."""
import os
from pathlib import Path


def load_local_env(path=".env"):
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise ValueError("Invalid local configuration: expected NAME=value")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name not in ("OPENAI_API_KEY", "OPENAI_MODEL"):
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value and value != "PASTE_YOUR_KEY_HERE" and not os.environ.get(name):
            os.environ[name] = value
