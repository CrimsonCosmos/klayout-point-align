#!/usr/bin/env python3
"""
console_runner.py - Minimal console wrapper for running Python scripts from PyInstaller bundle.

This exists solely to provide a proper Python interpreter for spawned subprocesses
when the main app is frozen with PyInstaller in windowed mode (console=False).
"""
import sys
import runpy

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: console_runner.py <script.py> [args...]", file=sys.stderr)
        sys.exit(1)

    script_path = sys.argv[1]
    sys.argv = sys.argv[1:]  # Remove console_runner.py from argv

    # Run the target script as __main__
    runpy.run_path(script_path, run_name="__main__")
