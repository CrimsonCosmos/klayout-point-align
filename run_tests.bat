@echo off
REM Quick test runner for Point Align

echo Running Point Align Tests...
echo.

python -m pytest tests/ -v

echo.
echo Test run complete.
pause
