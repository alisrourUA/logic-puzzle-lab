"""Settings. Change the model here or with environment variables / a .env file."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Tiny .env loader (KEY=VALUE lines) so we don't need extra packages."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()

MODEL = os.getenv("PUZZLE_MODEL", "gpt-4o-mini")
# "openai" for real runs, "mock" for offline testing without an API key
BACKEND = os.getenv("PUZZLE_BACKEND", "openai" if os.getenv("OPENAI_API_KEY") else "mock")
MAX_REPAIR_ROUNDS = int(os.getenv("PUZZLE_MAX_REPAIR", "4"))
