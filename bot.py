"""Telegram bot entrypoint. Run from project root: python3 bot.py"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def ensure_dependencies():
    try:
        import aiogram  # noqa: F401
    except ImportError:
        venv_python = ROOT_DIR / ".venv" / "bin" / "python"
        if venv_python.exists():
            os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit(
            "Missing dependencies. Install them first:\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/pip install -r requirements.txt\n"
            "  python3 bot.py"
        ) from None


ensure_dependencies()

from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env", override=True)

import asyncio

from bot.main import main

if __name__ == "__main__":
    asyncio.run(main())
