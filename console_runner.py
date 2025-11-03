#!/usr/bin/env python3
"""
console_runner.py - Minimal console wrapper for running Python scripts from PyInstaller bundle.

This exists solely to provide a proper Python interpreter for spawned subprocesses
when the main app is frozen with PyInstaller in windowed mode (console=False).
"""
import sys
import os
import runpy

if __name__ == "__main__":
    # Force UTF-8 encoding for stdout/stderr to handle Unicode characters
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    # Also set environment variables as backup
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUTF8'] = '1'

    if len(sys.argv) < 2:
        print("Usage: console_runner.py <script.py> [args...]", file=sys.stderr)
        sys.exit(1)

    script_path = sys.argv[1]
    sys.argv = sys.argv[1:]  # Remove console_runner.py from argv

    # Run the target script as __main__
    runpy.run_path(script_path, run_name="__main__")
