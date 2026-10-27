"""PyInstaller entry point (no source-tree path manipulation at runtime)."""

from ai_swe.launcher import main

if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())
