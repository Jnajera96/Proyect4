"""Entry point loaded by the unmodified, signed CPython interpreter."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys._ai_swe_bundle = Path(__file__).resolve().parent

from ai_swe.launcher import main  # noqa: E402 -- installed paths precede Settings imports

if __name__ == "__main__":
    raise SystemExit(main())
